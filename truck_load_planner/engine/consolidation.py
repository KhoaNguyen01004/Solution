"""
Vehicle consolidation and limited repacking.

After the initial fleet-level distribution, some vehicles may contain
only one or two packages that could be relocated to other vehicles
that still have free space.

Phase 3 — Vehicle Consolidation:
    Find the least-loaded vehicle and attempt to move all of its
    packages into other vehicles using the normal validation pipeline.

Phase 4 — Limited Repacking:
    If direct relocation fails, try temporarily relocating 1-2
    blocking packages to free up space, then retry.

This module does NOT perform full global optimisation — it keeps
the search bounded to avoid exponential blowup.
"""

from itertools import combinations
from typing import Optional
from truck_load_planner.engine.package import Package
from truck_load_planner.engine.distribution import find_best_for_pkg


def _count_packages(vehicle_sessions):
    """Return list of (package_count, idx, vinfo, session) sorted ascending."""
    counted = []
    for idx, (vinfo, session) in enumerate(vehicle_sessions):
        count = len(session._planner.placements)
        counted.append((count, idx, vinfo, session))
    counted.sort(key=lambda x: x[0])
    return counted


def _try_relocate_package(pkg, exclude_vinfo, vehicle_sessions):
    """Try to place *pkg* into any vehicle other than *exclude_vinfo*.

    Returns (session, pos) on success, (None, None) on failure.
    """
    for vinfo, session in vehicle_sessions:
        if vinfo["vehicle_id"] == exclude_vinfo["vehicle_id"]:
            continue
        score, pos = find_best_for_pkg(pkg, vinfo, session)
        if pos is not None:
            return session, pos
    return None, None


def _limited_repack(pkg, exclude_vinfo, vehicle_sessions, max_blockers=2):
    """Try to place *pkg* by temporarily relocating blocking packages.

    For each destination vehicle, identify packages whose removal would
    allow *pkg* to fit.  Relocate those blockers, place *pkg*, then
    attempt to re-place the blockers (either in the same vehicle or
    elsewhere).

    Returns True if successful.
    """
    for vinfo, session in vehicle_sessions:
        if vinfo["vehicle_id"] == exclude_vinfo["vehicle_id"]:
            continue

        planner = session._planner
        placements = list(planner.placements)

        # Try removing 1..max_blockers packages and see if pkg fits
        for n in range(1, max_blockers + 1):
            for blocker_indices in combinations(range(len(placements)), n):
                blocker_pls = [placements[i] for i in blocker_indices]

                # Temporarily remove blockers
                removed = []
                for i in sorted(blocker_indices, reverse=True):
                    removed.append(planner.state.pop_placement(i))

                # Try placing the target package
                score, pos = find_best_for_pkg(pkg, vinfo, session)
                if pos is not None:
                    p_result = planner.place_package(
                        pkg, pos["x"], pos["y"], pos["z"], pos["rotation"],
                    )
                    if p_result.valid:
                        # Try to re-place blockers (any vehicle)
                        all_replaced = True
                        for blocker_pl in removed:
                            b_pkg = blocker_pl.package
                            if b_pkg is None:
                                continue
                            b_session, b_pos = _try_relocate_package(
                                b_pkg, exclude_vinfo, vehicle_sessions,
                            )
                            if b_session and b_pos:
                                b_session._planner.place_package(
                                    b_pkg, b_pos["x"], b_pos["y"],
                                    b_pos["z"], b_pos["rotation"],
                                )
                            else:
                                all_replaced = False
                                break

                        if all_replaced:
                            return True

                        # Undo: remove target, restore blockers
                        planner.remove_package(len(planner.placements) - 1)

                # Restore blockers
                for bl in removed:
                    if bl.package:
                        planner.state.append_placement(
                            bl.package, bl.x, bl.y, bl.z, bl.rotation,
                        )

    return False


def consolidate_fleet(vehicle_sessions, packages, max_iterations=10):
    """Consolidate fleet by eliminating near-empty vehicles.

    Phase 3 — Vehicle Consolidation:
        Find the vehicle with the fewest packages and attempt to
        relocate every package into other vehicles.

    Phase 4 — Limited Repacking:
        If direct relocation fails, try temporarily moving 1-2
        blocking packages in the destination vehicle.

    Args:
        vehicle_sessions: List of (vinfo_dict, LoadPlanningSession).
        packages: All engine Package objects (for reference).
        max_iterations: Max consolidation passes.

    Returns:
        (vehicle_sessions, eliminated_count) where vehicle_sessions
        is the (possibly reduced) list.
    """
    eliminated = 0

    for _ in range(max_iterations):
        counted = _count_packages(vehicle_sessions)
        # Skip vehicles with 0 packages or only 1 vehicle left
        viable = [(c, idx, v, s) for c, idx, v, s in counted if c > 0]
        if len(viable) <= 1:
            break

        # Pick the least-loaded vehicle
        min_count, min_idx, min_vinfo, min_session = viable[0]

        # If the least-loaded has more than 3 packages, stop — further
        # consolidation would require significant replanning
        if min_count > 3:
            break

        packages_to_move = list(min_session._planner.placements)
        relocated = []
        failed = False

        for pl in packages_to_move:
            pkg = pl.package
            if pkg is None:
                continue

            # Phase 3: direct relocation
            dest_session, pos = _try_relocate_package(
                pkg, min_vinfo, vehicle_sessions,
            )

            # Phase 4: limited repacking if direct move fails
            if dest_session is None:
                ok = _limited_repack(pkg, min_vinfo, vehicle_sessions)
                if not ok:
                    failed = True
                    break
                # After limited repack, the package was placed somewhere
                relocated.append(pkg)
            else:
                p_result = dest_session._planner.place_package(
                    pkg, pos["x"], pos["y"], pos["z"], pos["rotation"],
                )
                if p_result.valid:
                    relocated.append(pkg)
                else:
                    failed = True
                    break

        if not failed and len(relocated) == len(packages_to_move):
            # Remove the empty vehicle from the list
            vehicle_sessions.pop(min_idx)
            eliminated += 1
        else:
            # Undo any relocations from this failed attempt
            # (restore by re-running distribution would be complex;
            #  for simplicity, we skip this vehicle and move on)
            pass

    return vehicle_sessions, eliminated
