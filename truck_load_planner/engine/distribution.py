from truck_load_planner.engine.package import Package
from truck_load_planner.engine.validation import ValidationMode

from truck_load_planner.engine.candidate_points import (
    tighten_position, generate_floor_anchors,
)
from truck_load_planner.engine.placement import Placement
from truck_load_planner.engine.trace_mutations import M


def reassign_load_sequences(placements: list) -> None:
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


def expand_candidates(base_candidates, allow_rotation):
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


def find_best_for_pkg(pkg, vinfo, session, remaining_pkgs=None):
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

        score = planner.evaluate_position(
            pkg, tx, ty, tz, trot,
            remaining_packages=remaining_pkgs,
        )
        scored.append((score.total, {"x": tx, "y": ty, "z": tz, "rotation": trot}))

    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        floor_cands = [s for s in scored if s[1]["z"] < 0.001]
        stack_cands = [s for s in scored if 0.001 <= s[1]["z"]]
        if floor_cands:
            best_score, best_pos = floor_cands[0][0], floor_cands[0][1]
        elif stack_cands:
            best_score, best_pos = stack_cands[0][0], stack_cands[0][1]
        else:
            best_score, best_pos = scored[0][0], scored[0][1]

    return best_score, best_pos


def _vehicle_capacity(vinfo):
    vol_mm3 = (vinfo.get("cargo_length_mm", 0) *
               vinfo.get("cargo_width_mm", 0) *
               vinfo.get("cargo_height_mm", 0))
    payload = vinfo.get("payload_kg", 0)
    return vol_mm3 * max(payload, 1)


def distribute_across_vehicles(packages, vehicle_sessions, debug=False, profile=None):
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

    remaining_pkgs = list(sorted_pkgs)

    for vinfo, session in sorted_vehicles:
        if not remaining_pkgs:
            break

        pool = list(remaining_pkgs)
        remaining_pkgs = []

        for i, pkg in enumerate(pool):
            future_pkgs = pool[i + 1:] + remaining_pkgs
            score, pos = find_best_for_pkg(pkg, vinfo, session, future_pkgs)
            if pos is not None:
                pkg_name = pkg.name if pkg else "?"
                p_result = session._planner.place_package(
                    pkg, pos["x"], pos["y"], pos["z"], pos["rotation"],
                    _trace_reason=f"distribute_across_vehicles/{pkg_name}",
                )
                if p_result.valid:
                    placed += 1
                    placed_vehicle_map[vinfo["vehicle_id"]].append(pkg.name)
                else:
                    failed += 1
                    unplaced.append(pkg.name)
                    remaining_pkgs.append(pkg)
            else:
                remaining_pkgs.append(pkg)

    failed = len(unplaced)

    for _, session in sorted_vehicles:
        pls = session._planner.placements
        if pls:
            reassign_load_sequences(pls)

    stats = {"rearrangement_attempts": 0}
    return placed, failed, unplaced, placed_vehicle_map, stats
