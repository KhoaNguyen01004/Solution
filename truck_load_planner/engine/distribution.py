"""
Fleet-level package distribution across multiple vehicles using
Largest-Vehicle-First strategy.

Extracted from routes.py so it can be reused by the repair optimizer
without circular imports.
"""
from truck_load_planner.engine.package import Package
from truck_load_planner.engine.validation import ValidationMode

from truck_load_planner.engine.candidate_points import (
    tighten_position, generate_floor_anchors, settle_package,
)
from truck_load_planner.engine.placement import Placement
from truck_load_planner.engine.frontier import FrontierTracker
from truck_load_planner.engine.auto_arrange import MAX_POSSIBLE_SCORE
from truck_load_planner.engine.trace_mutations import M


def reassign_load_sequences(placements: list) -> None:
    """Reassign load_sequence based on physical position.

    Sort by: x ascending (deepest first → away from door),
             z ascending (floor first → bottom before stacked),
             y ascending (left to right).

    This ensures the animation shows packages being loaded
    from the deepest point first, working outward toward the door,
    with floor packages before stacked ones.
    """
    indexed = list(enumerate(placements))
    indexed.sort(key=lambda e: (e[1].x, e[1].z, e[1].y))
    for seq, (_, pl) in enumerate(indexed, 1):
        if isinstance(pl, Placement):
            old_seq = pl.load_sequence
            pl.load_sequence = seq
            if old_seq != seq:
                M.log("reassign_load_sequences", pl,
                      (pl.x, pl.y, pl.z, pl.rotation),
                      (pl.x, pl.y, pl.z, pl.rotation),
                      f"load_sequence {old_seq}->{seq}")


MAX_STACK_HEIGHT_MM = 1800


def _has_above(placements, pl):
    """Check if any other placement rests directly on top of *pl*."""
    pkg = pl.package
    if pkg is None:
        return False
    top_z = pl.z + (pkg.height_mm if hasattr(pkg, 'height_mm') else getattr(pkg, 'height', 0))
    pl_l = pkg.length_mm if hasattr(pkg, 'length_mm') else getattr(pkg, 'length', 0)
    pl_w = pkg.width_mm if hasattr(pkg, 'width_mm') else getattr(pkg, 'width', 0)
    if pl.rotation == 90:
        pl_l, pl_w = pl_w, pl_l
    for other in placements:
        if other is pl:
            continue
        op = other.package
        if op is None:
            continue
        if abs(other.z - top_z) > 0.001:
            continue
        ol = op.length_mm if hasattr(op, 'length_mm') else getattr(op, 'length', 0)
        ow = op.width_mm if hasattr(op, 'width_mm') else getattr(op, 'width', 0)
        if other.rotation == 90:
            ol, ow = ow, ol
        if (other.x < pl.x + pl_l and other.x + ol > pl.x and
            other.y < pl.y + pl_w and other.y + ow > pl.y):
            return True
    return False


def compact_placements(planner, passes: int = 2, step: float = 50.0) -> int:
    """Post-placement compaction: push every package as far forward (-X) as possible.

    Iterates all placements in **ascending X order** so that by the time
    package P is settled, every package that could block it has already
    reached its own final position — guaranteeing single-pass convergence
    for the analytical settle path.

    Fast path: ``settle_package`` (analytical O(K) via spatial index).
    Fallback: ``tighten_position`` (step iteration) when the analytical
    result provides no improvement (e.g., Y/Z rearrangement is needed).
    Packages with items stacked on top are skipped; use ``compact_stacks``
    to move whole stack groups.

    Args:
        planner: Planner instance with placements.
        passes: Number of full compaction passes.
        step: Step size for tighten_position fallback (mm).

    Returns:
        Number of packages whose position changed.
    """
    total_moved = 0
    planner._validation_mode = ValidationMode.REPOSITION
    for _ in range(passes):
        moved = 0
        # CRITICAL: ascending X so blockers are already settled before dependents
        placements_sorted = sorted(
            planner.placements,
            key=lambda pl: (pl.x, pl.z, pl.y),
        )
        for pl in placements_sorted:
            pkg = pl.package
            if pkg is None:
                continue
            if _has_above(planner.placements, pl):
                continue

            h_clr = getattr(pkg, 'horizontal_clearance_mm', 10.0)

            # ── Fast path: analytical O(K) settle via spatial index ──
            tx, ty, tz, trot = settle_package(planner, pkg, pl.x, pl.y, pl.z, pl.rotation)

            # ── Fallback: step iteration when analytical gives no gain ──
            # (needed when Y/Z repositioning would unlock further -X movement)
            if abs(tx - pl.x) <= h_clr:
                tx, ty, tz, trot = tighten_position(
                    planner, pkg, pl.x, pl.y, pl.z, pl.rotation, step=step,
                )

            if (abs(tx - pl.x) <= h_clr and abs(ty - pl.y) <= h_clr
                    and abs(tz - pl.z) <= 0.001 and trot == pl.rotation):
                continue

            idx = planner.placements.index(pl)
            pkg_name = pkg.name if pkg else "?"
            old_pos = (pl.x, pl.y, pl.z, pl.rotation)
            planner.state.pop_placement(idx)
            result = planner.place_package(pkg, tx, ty, tz, trot, _trace_reason=f"compact_placements/{pkg_name}")
            if result.valid:
                moved += 1
            else:
                planner.place_package(pkg, pl.x, pl.y, pl.z, pl.rotation, _trace_reason=f"compact_placements_restore/{pkg_name}")
        total_moved += moved
        if moved == 0:
            break
    planner._validation_mode = ValidationMode.INSERTION
    return total_moved


def compact_stacks(planner, step: float = 50.0) -> int:
    """Push entire stack groups forward, rebuilding indices only once.

    Finds all vertical stack groups and tries to shift each group as far
    forward (-X) as possible.  Unlike compact_placements (which skips
    stacked packages), this moves every package in a stack together.

    Uses ``settle_package`` (analytical O(K)) on the bottom of each stack
    to find the maximum -X shift, then validates *all* packages in the
    group at the shifted position before applying.

    All position changes are applied first, then spatial+extreme-point
    indices are rebuilt once — avoiding O(n²) per-package rebuilds.

    Args:
        planner: Planner instance with placements.
        step: Step size for tighten_position fallback (mm).

    Returns:
        Number of packages whose position changed.
    """
    from .geometry import AABB

    if not planner.placements:
        return 0

    planner._validation_mode = ValidationMode.REPOSITION

    # 1. Find stack groups (packages that share an XY footprint)
    groups = []
    assigned_ids = set()
    placements = list(planner.placements)
    for pl in placements:
        if pl.package is None or id(pl) in assigned_ids:
            continue
        group = {id(pl): pl}
        base_top = pl.z + (pl.package.height_mm if pl.package else 0)
        # Gather all packages stacked on this footprint
        for other in placements:
            if other.package is None or other is pl or id(other) in assigned_ids:
                continue
            if abs(other.z - base_top) < 0.001:
                group[id(other)] = other
        assigned_ids.update(group.keys())
        groups.append(list(group.values()))

    moved = 0
    for group in groups:
        bottom = min(group, key=lambda g: g.z)
        pkg = bottom.package
        if pkg is None:
            continue

        h_clr = getattr(pkg, 'horizontal_clearance_mm', 10.0)

        # Fast path: analytical settle for the bottom package
        tx, ty, tz, trot = settle_package(
            planner, pkg, bottom.x, bottom.y, bottom.z, bottom.rotation,
        )
        # Fallback when analytical provides no gain
        if abs(tx - bottom.x) <= h_clr:
            tx, ty, tz, trot = tighten_position(
                planner, pkg, bottom.x, bottom.y, bottom.z, bottom.rotation, step=step,
            )

        dx = tx - bottom.x
        if abs(dx) <= h_clr:
            continue

        # Validate EVERY package in the group at its shifted position.
        # The analytical shift is derived from the bottom package's blockers;
        # upper packages may have different Y/Z footprints that further
        # constrain the valid shift — so all must pass.
        ok = True
        for g in group:
            g_pkg = g.package
            if g_pkg is None:
                continue
            nx = g.x + dx
            if nx < 0:
                ok = False
                break
            if not planner.validate_position(g_pkg, nx, g.y, g.z, g.rotation).valid:
                ok = False
                break
        if not ok:
            continue

        # Apply position updates directly (no per-package rebuilds)
        for g in group:
            old_x = g.x
            g.x += dx
            M.log_direct_x("compact_stacks", g, old_x, g.x, f"dx={dx:.1f}")
            moved += 1

    # Single rebuild of all indices
    if moved > 0:
        planner.state._rebuild_extreme_points()
        planner.state._spatial.clear()
        for pl in planner.placements:
            if pl.package is None:
                continue
            h_clr = getattr(pl.package, 'horizontal_clearance_mm', 10.0)
            v_clr = getattr(pl.package, 'vertical_clearance_mm', 0.0)
            aabb = AABB.from_dimensions(
                pl.x, pl.y, pl.z,
                pl.package.length_mm, pl.package.width_mm, pl.package.height_mm,
                pl.rotation, clearance_xy=h_clr, clearance_z=v_clr,
            )
            planner.state._spatial.insert(pl, aabb)

    planner._validation_mode = ValidationMode.INSERTION
    return moved


def fill_interior_gaps(planner, passes: int = 1) -> int:
    """Close mid-container holes by analytically re-settling all packages.

    After compaction, isolated empty regions may remain between packages
    when the initial placement left gaps that ``compact_placements`` could
    not close because of ordering (a package behind a gap was settled first
    against the stale gap boundary rather than the front wall).

    This function performs one forward sweep in ascending X order — the
    same convergence guarantee as ``compact_placements`` — but uses
    ``settle_package`` exclusively (no step-iteration fallback) and runs
    in REPOSITION mode so support/door checks are skipped.

    Complexity: O(N log N) sort + O(N·K) settle where K = spatial
    query result size (typically much smaller than N).

    Args:
        planner: Planner instance.
        passes: Number of sweep passes (1 usually suffices).

    Returns:
        Number of packages that moved.
    """
    total_moved = 0
    planner._validation_mode = ValidationMode.REPOSITION

    for _ in range(passes):
        moved = 0
        # Ascending X: blockers are settled before dependents
        placements_sorted = sorted(planner.placements, key=lambda pl: pl.x)

        for pl in placements_sorted:
            pkg = pl.package
            if pkg is None:
                continue

            tx, ty, tz, trot = settle_package(planner, pkg, pl.x, pl.y, pl.z, pl.rotation)
            h_clr = getattr(pkg, 'horizontal_clearance_mm', 10.0)

            if abs(tx - pl.x) <= h_clr:
                continue

            idx = next((i for i, p in enumerate(planner.placements) if p is pl), None)
            if idx is None:
                continue
            pkg_name = pkg.name if pkg else "?"
            planner.state.pop_placement(idx)
            result = planner.place_package(pkg, tx, ty, tz, trot, _trace_reason=f"fill_interior_gaps/{pkg_name}")
            if result.valid:
                moved += 1
            else:
                planner.place_package(pkg, pl.x, pl.y, pl.z, pl.rotation, _trace_reason=f"fill_interior_gaps_restore/{pkg_name}")

        total_moved += moved
        if moved == 0:
            break

    planner._validation_mode = ValidationMode.INSERTION
    return total_moved


def fill_frontier_gaps(planner, frontier: FrontierTracker) -> int:
    """Close gaps behind the frontier by analytically re-settling packages.

    Processes place-ments in ascending X order.  For each package whose
    xmin is behind the frontier at its Y position, calls
    ``settle_package`` (analytical O(K) via spatial index) to push it
    as far forward as possible.  Updates the frontier immediately on
    each move so downstream packages benefit from the tighter boundary.

    Unlike ``fill_interior_gaps`` which blindly settles every package,
    this function only touches packages that are demonstrably gapped,
    reducing unnecessary moves and index rebuilds.

    Falls back to ``tighten_position`` when the analytical settle
    provides no improvement (rare — only when Y/Z rearrangement is
    needed).

    Args:
        planner: Planner instance.
        frontier: FrontierTracker initialised from current placements.

    Returns:
        Number of packages that moved.
    """
    total_moved = 0
    planner._validation_mode = ValidationMode.REPOSITION

    placements_sorted = sorted(planner.placements, key=lambda pl: pl.x)
    for pl in placements_sorted:
        pkg = pl.package
        if pkg is None:
            continue
        if pl.z > 0.001:
            frontier.update_from_placement(pl)
            continue

        h_clr = getattr(pkg, 'horizontal_clearance_mm', 10.0)

        # ── INSTRUMENTATION: detect base-package movement with stack above ──
        has_stack_above = _has_above(planner.placements, pl)
        if has_stack_above:
            pl_above = [other for other in planner.placements if other is not pl and abs(other.z - (pl.z + (pl.package.height_mm if pl.package else 0))) < 0.001]
            print(f"  *** INSTRUMENT: {pl.package.name} (uid={getattr(pl,'_uid',-1)}) HAS {len(pl_above)} package(s) stacked on top at z={pl.z + (pl.package.height_mm if pl.package else 0):.1f}")

        if pl.rotation in (90, 270):
            dy = pkg.length_mm
        else:
            dy = pkg.width_mm

        # Always try analytical settle — the gap-distance check alone
        # misses packages slightly ahead of frontier that can still slide
        tx, ty, tz, trot = settle_package(planner, pkg, pl.x, pl.y, pl.z, pl.rotation)

        # Fallback when analytical gives no gain (needs Y/Z movement)
        if abs(tx - pl.x) <= 1.0:
            tx, ty, tz, trot = tighten_position(
                planner, pkg, pl.x, pl.y, pl.z, pl.rotation, step=50.0,
            )

        # Re-place only when we gained meaningful forward movement
        if tx >= pl.x - 1.0:
            if has_stack_above:
                print(f"  *** INSTRUMENT: {pl.package.name} (uid={getattr(pl,'_uid',-1)}) SKIPPED (no forward gain)")
            frontier.update_from_placement(pl)
            continue

        # Safe removal: find by identity, not index
        idx = next((i for i, p in enumerate(planner.placements) if p is pl), None)
        if idx is None:
            frontier.update_from_placement(pl)
            continue
        pkg_name = pkg.name if pkg else "?"

        # ── DETECT: moving a base package that has packages stacked on top ──
        if has_stack_above:
            print(f"  >>>>>> BUG DETECTED: fill_frontier_gaps moves base package '{pkg_name}' (uid={getattr(pl,'_uid',-1)}) which has {len(pl_above)} package(s) stacked on top!")
            print(f"  >>>>>> Position change: ({pl.x:.1f},{pl.y:.1f},{pl.z:.1f},r{pl.rotation}) -> ({tx:.1f},{ty:.1f},{tz:.1f},r{trot})")
            import traceback
            traceback.print_stack(limit=10)

        planner.state.pop_placement(idx)
        result = planner.place_package(pkg, tx, ty, tz, trot, _trace_reason=f"fill_frontier_gaps/{pkg_name}")
        if result.valid:
            total_moved += 1
            frontier.update_from_placement(planner.placements[-1])
        else:
            planner.place_package(pkg, pl.x, pl.y, pl.z, pl.rotation, _trace_reason=f"fill_frontier_gaps_restore/{pkg_name}")
            frontier.update_from_placement(pl)

    planner._validation_mode = ValidationMode.INSERTION
    return total_moved


def expand_candidates(base_candidates, allow_rotation):
    """Expand (x,y,z) tuples with rotation variants."""
    expanded = []
    seen = set()
    for pos in base_candidates:
        if isinstance(pos, dict):
            x, y, z = pos.get("x", 0), pos.get("y", 0), pos.get("z", 0)
        else:
            x, y, z = pos[0], pos[1], pos[2]
        key0 = (x, y, z, 0)
        if key0 not in seen:
            seen.add(key0)
            expanded.append({"x": x, "y": y, "z": z, "rotation": 0})
        if allow_rotation:
            key90 = (x, y, z, 90)
            if key90 not in seen:
                seen.add(key90)
                expanded.append({"x": x, "y": y, "z": z, "rotation": 90})
    return expanded


def candidate_priority(pkg, pos, container):
    """Lightweight priority score for a candidate placement position.

    Higher = more promising. Used to rank candidates before expensive
    validation so that good placements are found and accepted earlier.
    """
    x, y, z = pos["x"], pos["y"], pos["z"]
    rot = pos["rotation"]

    if rot == 0:
        dx, dy, dz = pkg.length_mm, pkg.width_mm, pkg.height_mm
    else:
        dx, dy, dz = pkg.width_mm, pkg.length_mm, pkg.height_mm

    touches = 0
    if x == 0:                    touches += 1
    if x + dx == container.length: touches += 1
    if y == 0:                    touches += 1
    if y + dy == container.width:  touches += 1
    if z == 0:                    touches += 1
    if z + dz == container.height: touches += 1
    touch_score = touches * 10.0

    z_score = (1.0 - z / container.height) * 15.0 if container.height > 0 else 0.0

    contact = 0.0
    if x == 0:                    contact += dy * dz
    if x + dx == container.length: contact += dy * dz
    if y == 0:                    contact += dx * dz
    if y + dy == container.width:  contact += dx * dz
    if z == 0:                    contact += dx * dy
    if z + dz == container.height: contact += dx * dy
    max_contact = 2 * (dx * dy + dy * dz + dx * dz)
    wall_score = (contact / max_contact * 15.0) if max_contact > 0 else 0.0

    back_score = (1.0 - x / container.length) * 20.0 if container.length > 0 else 0.0

    fc_dist = (x**2 + (y - container.width / 2)**2 + z**2) ** 0.5
    max_fc = (container.length**2 + (container.width / 2)**2 + container.height**2) ** 0.5
    front_center_score = (1.0 - fc_dist / max_fc) * 10.0 if max_fc > 0 else 0.0

    return touch_score + z_score + wall_score + back_score + front_center_score


def find_best_for_pkg(pkg, vinfo, session, remaining_pkgs=None,
                      frontier: FrontierTracker = None):
    """Return (best_score, best_pos) or (None, None) if no valid position."""
    best_score = float("-inf")
    best_pos = None
    planner = session._planner
    container = planner.state.container
    candidates = list(planner.get_candidate_points())

    h_clr = getattr(pkg, 'horizontal_clearance_mm', 10.0)
    right_y = container.width - pkg.width_mm - h_clr
    if right_y > h_clr:
        right_candidate = (0, right_y, 0)
        if right_candidate not in candidates:
            candidates.insert(0, right_candidate)

    floor_anchors = generate_floor_anchors(
        planner.placements, container, pkg, max_regions=2,
    )
    for anchor in floor_anchors:
        if anchor not in candidates:
            candidates.append(anchor)

    expanded = expand_candidates(candidates, pkg.allow_rotation)

    scored = []
    for pos in expanded:
        tx, ty, tz, trot = tighten_position(
            planner, pkg, pos["x"], pos["y"], pos["z"], pos["rotation"],
        )
        vresult = planner.validate_position(pkg, tx, ty, tz, trot)
        if not vresult.valid:
            continue

        # Gap penalty: penalise floor candidates behind frontier
        gap_penalty = 0.0
        if tz < 0.001 and frontier is not None:
            if trot in (90, 270):
                gdy = pkg.length_mm
            else:
                gdy = pkg.width_mm
            gd = frontier.gap_distance(tx, ty, gdy)
            gr = frontier.gap_ratio(tx, ty, gdy)
            if gd > 0:
                gap_penalty = -min(gd * (0.5 + gr * 0.5), 500.0)

        score = planner.evaluate_position(
            pkg, tx, ty, tz, trot,
            remaining_packages=remaining_pkgs,
        )
        adjusted = score.total + gap_penalty
        scored.append((adjusted, {"x": tx, "y": ty, "z": tz, "rotation": trot}))

    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        # Prefer floor (z=0), then low stacks (< max height), then any
        floor_cands = [s for s in scored if s[1]["z"] < 0.001]
        stack_cands = [s for s in scored if 0.001 <= s[1]["z"] <= MAX_STACK_HEIGHT_MM]
        if floor_cands:
            best_score, best_pos = floor_cands[0][0], floor_cands[0][1]
        elif stack_cands:
            best_score, best_pos = stack_cands[0][0], stack_cands[0][1]
        else:
            best_score, best_pos = scored[0][0], scored[0][1]

    if best_pos is None:
        from truck_load_planner.engine.candidate_points import generate_slide_candidates
        slide_cands = generate_slide_candidates(candidates, pkg, container)
        for pos in slide_cands:
            tx, ty, tz, trot = tighten_position(
                planner, pkg, pos["x"], pos["y"], pos["z"], pos["rotation"],
            )
            vresult = planner.validate_position(pkg, tx, ty, tz, trot)
            if not vresult.valid:
                continue
            score = planner.evaluate_position(
                pkg, tx, ty, tz, trot,
                remaining_packages=remaining_pkgs,
            )
            tight_pos = {"x": tx, "y": ty, "z": tz, "rotation": trot}
            if score.total > best_score:
                best_score = score.total
                best_pos = tight_pos
                if best_score >= MAX_POSSIBLE_SCORE - 0.01:
                    break

    return best_score, best_pos


def _snapshot_placements(planner):
    """Save current placements as durable dicts for later restoration."""
    return [
        {
            "package_id": pl.package_id,
            "x": pl.x, "y": pl.y, "z": pl.z,
            "rotation": pl.rotation,
            "load_sequence": pl.load_sequence,
            "_package": pl.package.to_dict() if pl.package else None,
        }
        for pl in planner.placements
    ]


def _restore_placements(planner, snapshot):
    """Restore placements from a snapshot, rebuilding spatial + extreme-point indices."""
    planner.state.import_placements(snapshot)


def _find_blocking_floor_packages(placements, pkg, x, y, rotation):
    """Find floor packages whose 2D footprint (including clearance) overlaps pkg at (x,y,rot)."""
    h_clr = getattr(pkg, 'horizontal_clearance_mm', 10.0)
    pkg_l = pkg.length_mm if rotation == 0 else pkg.width_mm
    pkg_w = pkg.width_mm if rotation == 0 else pkg.length_mm

    x_min = x - h_clr
    x_max = x + pkg_l + h_clr
    y_min = y - h_clr
    y_max = y + pkg_w + h_clr

    blockers = []
    for pl in placements:
        if pl.z > 0.001 or pl.package is None:
            continue
        bp = pl.package
        pl_h_clr = getattr(bp, 'horizontal_clearance_mm', 10.0)
        bl = bp.length_mm if pl.rotation == 0 else bp.width_mm
        bw = bp.width_mm if pl.rotation == 0 else bp.length_mm

        pl_x_min = pl.x - pl_h_clr
        pl_x_max = pl.x + bl + pl_h_clr
        pl_y_min = pl.y - pl_h_clr
        pl_y_max = pl.y + bw + pl_h_clr

        if (x_min < pl_x_max and x_max > pl_x_min and
                y_min < pl_y_max and y_max > pl_y_min):
            blockers.append(pl)
    return blockers


def _best_floor_candidate(planner, pkg, container, remaining_pkgs):
    """Find and score the best valid floor candidate for pkg in the current state.

    Returns a position dict with tightened coords, or None.
    """
    candidates = list(planner.get_candidate_points())
    anchors = generate_floor_anchors(planner.placements, container, pkg, max_regions=2)
    for a in anchors:
        if a not in candidates:
            candidates.append(a)
    expanded = expand_candidates(candidates, pkg.allow_rotation)

    best = None
    best_score = float("-inf")
    for pos in expanded:
        if pos["z"] > 0.001:
            continue
        if not planner.validate_position(pkg, pos["x"], pos["y"], 0, pos["rotation"]).valid:
            continue
        tx, ty, tz, trot = tighten_position(
            planner, pkg, pos["x"], pos["y"], 0, pos["rotation"],
        )
        if not planner.validate_position(pkg, tx, ty, tz, trot).valid:
            tx, ty, tz, trot = pos["x"], pos["y"], 0, pos["rotation"]
        score = planner.evaluate_position(
            pkg, tx, ty, tz, trot,
            remaining_packages=remaining_pkgs,
        )
        if score.total > best_score:
            best_score = score.total
            best = {"x": tx, "y": ty, "z": tz, "rotation": trot}
    return best


def _try_local_rearrangement(planner, pkg, container, remaining_pkgs, stack_score, max_remove=3):
    """Try to place *pkg* on the floor by removing blocking floor packages.

    When the only feasible candidates for *pkg* are stacks, this function
    identifies which floor packages block the preferred floor positions,
    removes up to *max_remove* of them, places *pkg* on the newly-freed
    floor, and re-places the removed packages around it.

    Only accepts the rearrangement if the floor placement scores strictly
    higher than *stack_score* (the score of the stack candidate from the
    main pipeline).

    Returns True on success (planner is modified — *pkg* and the blockers
    are all on the floor).  Returns False on failure (planner is restored
    to its original state).

    The search is bounded: at most *max_remove* packages are displaced,
    and at most one candidate is attempted before reverting.
    """
    snapshot = _snapshot_placements(planner)

    # Generate and prioritise floor candidates
    candidates = list(planner.get_candidate_points())
    anchors = generate_floor_anchors(planner.placements, container, pkg, max_regions=2)
    for a in anchors:
        if a not in candidates:
            candidates.append(a)
    expanded = expand_candidates(candidates, pkg.allow_rotation)
    floor_candidates = [c for c in expanded if c["z"] < 0.001]

    # Sort by candidate_priority (cheap heuristic) to try promising spots first
    scored_candidates = []
    for c in floor_candidates:
        prio = candidate_priority(pkg, c, container)
        scored_candidates.append((prio, c))
    scored_candidates.sort(key=lambda x: -x[0])

    for _, candidate in scored_candidates:
        # Already a valid floor candidate? No rearrangement needed.
        if planner.validate_position(pkg, candidate["x"], candidate["y"],
                                     0, candidate["rotation"]).valid:
            return False

        blockers = _find_blocking_floor_packages(
            planner.placements, pkg,
            candidate["x"], candidate["y"], candidate["rotation"],
        )

        if len(blockers) == 0 or len(blockers) > max_remove:
            continue

        # Remove blockers (reverse-index order to preserve indices)
        indices = sorted(
            [planner.placements.index(pl) for pl in blockers],
            reverse=True,
        )
        for idx in indices:
            bl_pl = planner.state.pop_placement(idx)
            if bl_pl:
                M.log_remove("_try_local_rearrangement", bl_pl, f"blocker idx={idx}")

        # Place pkg at the freed candidate position
        tx, ty, tz, trot = tighten_position(
            planner, pkg,
            candidate["x"], candidate["y"], 0, candidate["rotation"],
        )
        if not planner.validate_position(pkg, tx, ty, tz, trot).valid:
            tx, ty, tz, trot = candidate["x"], candidate["y"], 0, candidate["rotation"]

        pkg_name = pkg.name if pkg else "?"
        place_result = planner.place_package(pkg, tx, ty, tz, trot, _trace_reason=f"_try_local_rearrangement/{pkg_name}")
        if not place_result.valid:
            M.log(None, pkg, None, None, "_try_local_rearrangement FAILED, restoring snapshot")
            _restore_placements(planner, snapshot)
            continue

        # Re-place each blocker on the floor
        all_ok = True
        for bl in blockers:
            best = _best_floor_candidate(planner, bl.package, container, remaining_pkgs)
            if best is None:
                all_ok = False
                break
            bl_name = bl.package.name if bl.package else "?"
            if not planner.place_package(bl.package, best["x"], best["y"],
                                         best["z"], best["rotation"]).valid:
                all_ok = False
                break

        if not all_ok:
            M.log(None, pkg, None, None, "_try_local_rearrangement all_ok=False, restoring snapshot")
            _restore_placements(planner, snapshot)
            continue

        # Score comparison: only accept if the floor arrangement is strictly better
        floor_score = planner.evaluate_position(
            pkg, tx, ty, tz, trot,
            remaining_packages=remaining_pkgs,
        )
        if floor_score.total > stack_score:
            return True

        # Floor arrangement is not better — restore and try next candidate
        M.log(None, pkg, None, None, "_try_local_rearrangement score not better, restoring snapshot")
        _restore_placements(planner, snapshot)

    return False


def estimate_remaining_after(pkg, pos, session):
    """Estimate remaining capacity % after placing pkg at pos.

    Returns (vol_pct, floor_pct, payload_pct). Lower = tighter fit = less waste.
    """
    planner = session._planner
    container = planner.state.container
    stats = planner.get_statistics()

    total_vol_mm3 = container.length * container.width * container.height
    used_vol_mm3 = stats.get("volume_used_m3", 0) * 1_000_000_000
    rem_vol = max(0.0, total_vol_mm3 - used_vol_mm3
                  - pkg.length_mm * pkg.width_mm * pkg.height_mm)

    total_floor_mm2 = container.length * container.width
    used_floor_pct = stats.get("floor_used_pct", 0) / 100.0
    used_floor_mm2 = used_floor_pct * total_floor_mm2
    floor_footprint = pkg.length_mm * pkg.width_mm if pos["z"] == 0 else 0
    rem_floor = max(0.0, total_floor_mm2 - used_floor_mm2 - floor_footprint)

    rem_payload = max(0.0, stats.get("weight_remaining_kg",
                      container.payload_kg) - pkg.weight_kg)

    vol_pct = rem_vol / total_vol_mm3 * 100 if total_vol_mm3 > 0 else 0.0
    floor_pct = (rem_floor / total_floor_mm2 * 100
                 if total_floor_mm2 > 0 else 0.0)
    payload_pct = (rem_payload / container.payload_kg * 100
                   if container.payload_kg > 0 else 0.0)
    return vol_pct, floor_pct, payload_pct


def _vehicle_capacity(vinfo):
    vol_mm3 = (vinfo.get("cargo_length_mm", 0) *
               vinfo.get("cargo_width_mm", 0) *
               vinfo.get("cargo_height_mm", 0))
    payload = vinfo.get("payload_kg", 0)
    return vol_mm3 * max(payload, 1)


def distribute_across_vehicles(packages, vehicle_sessions, debug=False, profile=None):
    """Distribute packages across multiple vehicles using Largest-Vehicle-First.

    Sorts vehicles by combined capacity (volume x payload) descending, then
    for each vehicle tries to fit all remaining packages before moving to
    the next (smaller) vehicle. This ensures the biggest vehicles are loaded
    first and smaller ones only receive leftovers.

    Args:
        packages: List of engine Package objects to distribute.
        vehicle_sessions: List of (vinfo_dict, LoadPlanningSession) tuples.
        debug: Enable debug output.

    Returns:
        (placed, failed, unplaced, placed_vehicle_map)
    """
    sorted_pkgs = sorted(
        packages,
        key=lambda p: (
            0 if not p.stackable else 1,
            -(p.length_mm * p.width_mm * p.height_mm),
            -p.weight_kg,
            -(p.length_mm * p.width_mm),
        ),
    )

    sorted_vehicles = sorted(
        vehicle_sessions,
        key=lambda vs: _vehicle_capacity(vs[0]),
        reverse=True,
    )

    placed = 0
    failed = 0
    unplaced = []
    placed_vehicle_map = {vinfo["vehicle_id"]: [] for vinfo, _ in vehicle_sessions}
    rearrangement_attempts = 0

    remaining_pkgs = list(sorted_pkgs)

    for vinfo, session in sorted_vehicles:
        if not remaining_pkgs:
            break

        pool = list(remaining_pkgs)
        remaining_pkgs = []

        # Per-vehicle frontier tracker for gap prevention
        planner = session._planner
        container = planner.state.container
        frontier = FrontierTracker(container.width, strip_width_mm=250)

        for i, pkg in enumerate(pool):
            future_pkgs = pool[i + 1:] + remaining_pkgs
            score, pos = find_best_for_pkg(pkg, vinfo, session, future_pkgs,
                                            frontier=frontier)
            if pos is not None:
                if pos["z"] > 0 and profile and profile.enable_rearrangement:
                    rearrangement_attempts += 1
                    if _try_local_rearrangement(
                            planner, pkg, container,
                            future_pkgs, score, max_remove=5):
                        placed += 1
                        placed_vehicle_map[vinfo["vehicle_id"]].append(pkg.name)
                        frontier.update_from_placement(planner.placements[-1])
                        continue

                pkg_name = pkg.name if pkg else "?"
                p_result = planner.place_package(
                    pkg, pos["x"], pos["y"], pos["z"], pos["rotation"],
                    _trace_reason=f"distribute_across_vehicles/{pkg_name}",
                )
                if p_result.valid:
                    placed += 1
                    placed_vehicle_map[vinfo["vehicle_id"]].append(pkg.name)
                    frontier.update_from_placement(planner.placements[-1])
                else:
                    failed += 1
                    unplaced.append(pkg.name)
                    remaining_pkgs.append(pkg)
            else:
                remaining_pkgs.append(pkg)

    failed = len(unplaced)

    # Post-placement compaction: frontier gap-fill → step → stack → frontier
    cmp_passes = profile.compact_passes if profile else 2
    cmp_step = profile.compact_step_mm if profile else 50.0
    for _, session in sorted_vehicles:
        planner = session._planner
        if planner.placements:
            # Rebuild frontier from current placements
            c = planner.state.container
            frontier = FrontierTracker(c.width, strip_width_mm=250)
            for pl in planner.placements:
                frontier.update_from_placement(pl)
            # Pass 1: frontier-based gap fill
            M.stage("== dist: fill_frontier_gaps ==")
            fill_frontier_gaps(planner, frontier)
            # Pass 2: step-iteration compaction
            M.stage("== dist: compact_placements ==")
            compact_placements(planner, passes=cmp_passes, step=cmp_step)
            # Pass 3: whole-stack groups
            M.stage("== dist: compact_stacks ==")
            do_stacks = profile.enable_stack_compaction if profile else True
            if do_stacks:
                compact_stacks(planner, step=cmp_step)
            # Pass 4: final frontier sweep
            for pl in planner.placements:
                frontier.update_from_placement(pl)
            fill_frontier_gaps(planner, frontier)

    # Reassign load_sequence based on physical position so animation
    # plays deepest-first, bottom-first, matching real loading order.
    for _, session in sorted_vehicles:
        pls = session._planner.placements
        if pls:
            reassign_load_sequences(pls)

    stats = {"rearrangement_attempts": rearrangement_attempts}
    return placed, failed, unplaced, placed_vehicle_map, stats


def _vehicle_avg_max_z(vehicle_sessions):
    """Compute (avg_z, max_z, package_list) per vehicle."""
    result = []
    for vinfo, session in vehicle_sessions:
        pls = session._planner.placements
        if not pls:
            continue
        total_z = 0.0
        max_z = 0.0
        for pl in pls:
            top = pl.z + (pl.package.height_mm if pl.package else 0)
            total_z += top
            if top > max_z:
                max_z = top
        avg_z = total_z / len(pls)
        result.append((avg_z, max_z, vinfo, session))
    return result


def balance_fleet_profiles(vehicle_sessions, max_moves=10):
    """Even out load profiles across the fleet by moving high-stack packages.

    Identifies vehicles with high average stack height and attempts to
    relocate their highest packages to vehicles with lower profiles.

    Args:
        vehicle_sessions: List of (vinfo_dict, LoadPlanningSession).
        max_moves: Maximum number of packages to relocate.

    Returns:
        (vehicle_sessions, moves) where moves is the count of successful
        relocations.
    """
    moves = 0
    for _ in range(max_moves):
        profiles = _vehicle_avg_max_z(vehicle_sessions)
        if len(profiles) < 2:
            break

        profiles.sort(key=lambda x: -x[0])  # highest avg Z first
        src_avg, src_max, src_vinfo, src_session = profiles[0]
        tgt_avg, tgt_max, tgt_vinfo, tgt_session = profiles[-1]

        if src_avg <= tgt_avg * 1.1:
            break

        src_pls = sorted(
            src_session._planner.placements,
            key=lambda pl: -(pl.z + (pl.package.height_mm if pl.package else 0)),
        )

        moved_this_round = False
        for pl in src_pls:
            pkg = pl.package
            if pkg is None:
                continue

            score, pos = find_best_for_pkg(pkg, tgt_vinfo, tgt_session)
            if pos is not None and abs(pos["z"]) < 0.001:
                idx = src_session._planner.placements.index(pl)
                src_session._planner.remove_package(idx)

                pkg_name = pkg.name if pkg else "?"
                result = tgt_session._planner.place_package(
                    pkg, pos["x"], pos["y"], pos["z"], pos["rotation"],
                    _trace_reason=f"balance_fleet/to_target/{pkg_name}",
                )
                if result.valid:
                    moves += 1
                    moved_this_round = True
                    break
                else:
                    src_session._planner.place_package(
                        pkg, pl.x, pl.y, pl.z, pl.rotation,
                        _trace_reason=f"balance_fleet/restore_src/{pkg_name}",
                    )

        if not moved_this_round:
            break

    return vehicle_sessions, moves
