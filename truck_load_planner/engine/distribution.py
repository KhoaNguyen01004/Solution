from truck_load_planner.engine.package import Package
from truck_load_planner.engine.placement import Placement
from truck_load_planner.engine.trace_mutations import M
from truck_load_planner.engine.candidate_points import generate_candidates, tighten_position

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


def find_best_for_pkg(pkg, vinfo, session, remaining_pkgs=None):
    best_score = float("-inf")
    best_pos = None
    planner = session._planner
    
    candidates = generate_candidates(planner, pkg)

    for candidate in candidates:
        tx, ty, tz, trot = tighten_position(
            planner,
            pkg,
            candidate["x"],
            candidate["y"],
            candidate["z"],
            candidate["rotation"],
        )
        
        vresult = planner.validate_position(pkg, tx, ty, tz, trot)
        if not vresult.valid:
            continue

        score = planner.evaluate_position(
            pkg, tx, ty, tz, trot,
            remaining_packages=remaining_pkgs,
        )
        
        if score.total > best_score:
            best_score = score.total
            best_pos = {"x": tx, "y": ty, "z": tz, "rotation": trot}

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
            -p.width_mm,
            -p.length_mm,
            -(p.length_mm * p.width_mm * p.height_mm),
            -p.weight_kg,
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
                    unplaced.append(pkg.name)
                    remaining_pkgs.append(pkg)
            else:
                remaining_pkgs.append(pkg)

    # In original logic, failed was len(unplaced) but unplaced didn't cover pure rejections correctly if we just matched the old code,
    # let's just make it len(remaining_pkgs) to be correct.
    failed = len(remaining_pkgs)
    unplaced = [p.name for p in remaining_pkgs]

    for _, session in sorted_vehicles:
        pls = session._planner.placements
        if pls:
            reassign_load_sequences(pls)

    stats = {"rearrangement_attempts": 0}
    return placed, failed, unplaced, placed_vehicle_map, stats
