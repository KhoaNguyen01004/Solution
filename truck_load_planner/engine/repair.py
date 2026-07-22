"""
Fleet-level Destroy-and-Repair (Large Neighborhood Search) optimizer.

Operates on the entire fleet solution, not per-vehicle.  Reuses the
existing Best-Fit Decreasing distribution pipeline so that package
reassignment across vehicles (including vehicle elimination) is
discovered naturally.
"""

import math
import time
from collections import namedtuple
from typing import Optional

from truck_load_planner.engine.package import Package
from truck_load_planner.engine.geometry import AABB
from truck_load_planner.engine.distribution import distribute_across_vehicles
from truck_load_planner.engine.profile import PlannerProfile
from truck_load_planner.optimization.vehicle_cost import (
    VehicleCostModel, compute_fleet_cost,
)

_PlacementRecord = namedtuple(
    "_PlacementRecord",
    ["package", "vehicle_id", "x", "y", "z", "rotation", "volume"],
)

_FLOOR_GRID_RESOLUTION = 50  # mm per cell for fragmentation BFS


def _largest_empty_floor_region(placements, container) -> float:
    """Largest connected empty region on the floor (z == 0) in mm².

    Discretises the floor into *grid* cells and runs a BFS over
    empty cells using 4-directional connectivity.
    """
    if not container:
        return 0.0

    w = max(1, int(math.ceil(container.length / _FLOOR_GRID_RESOLUTION)))
    h = max(1, int(math.ceil(container.width / _FLOOR_GRID_RESOLUTION)))

    if w <= 0 or h <= 0:
        return 0.0

    occupied = [[False] * h for _ in range(w)]

    for pl in placements:
        pkg = pl.package
        if pkg is None:
            continue
        if pl.z > 0:
            continue

        aabb = AABB.from_dimensions(
            pl.x, pl.y, pl.z,
            pkg.length_mm, pkg.width_mm, pkg.height_mm,
            pl.rotation, clearance=0,
        )
        x0 = max(0, int(aabb.xmin / _FLOOR_GRID_RESOLUTION))
        x1 = min(w - 1, int((aabb.xmax - 0.001) / _FLOOR_GRID_RESOLUTION))
        y0 = max(0, int(aabb.ymin / _FLOOR_GRID_RESOLUTION))
        y1 = min(h - 1, int((aabb.ymax - 0.001) / _FLOOR_GRID_RESOLUTION))
        for gx in range(x0, x1 + 1):
            for gy in range(y0, y1 + 1):
                occupied[gx][gy] = True

    visited = [[False] * h for _ in range(w)]
    max_cells = 0

    for sx in range(w):
        for sy in range(h):
            if occupied[sx][sy] or visited[sx][sy]:
                continue

            stack = [(sx, sy)]
            visited[sx][sy] = True
            cells = 0

            while stack:
                cx, cy = stack.pop()
                cells += 1
                for nx, ny in ((cx - 1, cy), (cx + 1, cy),
                               (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        if not occupied[nx][ny] and not visited[nx][ny]:
                            visited[nx][ny] = True
                            stack.append((nx, ny))

            if cells > max_cells:
                max_cells = cells

    cell_area_mm2 = _FLOOR_GRID_RESOLUTION ** 2
    return max_cells * cell_area_mm2


def _compute_fleet_metrics(vehicle_sessions):
    """Compute fleet-level comparison metrics.

    Returns (total_placed, active_vehicles, total_empty_floor_mm2,
             avg_score, total_cost).

    Packing quality metrics come first (placed count, vehicles, floor,
    score); total_cost is a tie-breaker for similarly good solutions.
    """
    total_placed = 0
    active_vehicles = 0
    total_empty_floor = 0.0
    total_score = 0.0

    for vinfo, session in vehicle_sessions:
        planner = session._planner
        placements = planner.placements
        container = planner.state.container

        count = len(placements)
        total_placed += count
        if count > 0:
            active_vehicles += 1

        empty = _largest_empty_floor_region(placements, container)
        total_empty_floor += empty

        if count > 0:
            plan_score = planner.evaluate_plan()
            total_score += plan_score.total * count

    avg_score = total_score / total_placed if total_placed > 0 else 0.0
    total_cost = compute_fleet_cost(vehicle_sessions)
    return total_placed, active_vehicles, total_empty_floor, avg_score, total_cost


def _is_better(new, old):
    """Compare fleet solutions by priority order.

    Returns True if *new* is strictly better than *old*.
    Priority:
      1. More packages successfully placed
      2. Fewer vehicles used
      3. Smaller contiguous empty floor region (total across vehicles)
      4. Higher average placement score
      5. Lower total transportation cost (tie-breaker)
    """
    n_placed, n_vehicles, n_floor, n_score, n_cost = new
    o_placed, o_vehicles, o_floor, o_score, o_cost = old

    if n_placed != o_placed:
        return n_placed > o_placed
    if n_vehicles != o_vehicles:
        return n_vehicles < o_vehicles
    if n_floor != o_floor:
        return n_floor < o_floor
    if n_score != o_score:
        return n_score > o_score
    return n_cost < o_cost


def _collect_placement_records(vehicle_sessions, unplaced_packages):
    """Collect all placed packages with their vehicle/position info.

    Returns a list of _PlacementRecord sorted by ascending volume.
    """
    records = []
    for vinfo, session in vehicle_sessions:
        vid = vinfo["vehicle_id"]
        for pl in session._planner.placements:
            pkg = pl.package
            if pkg is None:
                continue
            vol = pkg.length_mm * pkg.width_mm * pkg.height_mm
            records.append(_PlacementRecord(
                package=pkg,
                vehicle_id=vid,
                x=pl.x, y=pl.y, z=pl.z,
                rotation=pl.rotation,
                volume=vol,
            ))

    records.sort(key=lambda r: r.volume)

    unplaced_pkgs = list(unplaced_packages) if unplaced_packages else []
    return records, unplaced_pkgs


def _recreate_sessions(vehicle_sessions):
    """Create fresh LoadPlanningSession copies.

    Each copy has the same container config and features as the original
    but an empty planner state.
    """
    fresh = []
    for vinfo, session in vehicle_sessions:
        from truck_load_planner.session import LoadPlanningSession

        new_session = LoadPlanningSession()
        new_session.select_container(session.container, session.features)
        new_session.vehicle_id = session.vehicle_id
        fresh.append((vinfo, new_session))
    return fresh


def _place_kept_packages(sessions, kept_records):
    """Place kept packages into their original positions in fresh sessions.

    *sessions* is a list of (vinfo, LoadPlanningSession) tuples.
    *kept_records* is a list of _PlacementRecord to restore.
    """
    session_map = {}
    for vinfo, session in sessions:
        session_map[vinfo["vehicle_id"]] = session

    for rec in kept_records:
        session = session_map.get(rec.vehicle_id)
        if session is None:
            continue
        session._planner.place_package(
            rec.package, rec.x, rec.y, rec.z, rec.rotation,
        )


def _format_floor_area(mm2):
    """Format mm² to m² with one decimal place."""
    return f"{mm2 / 1_000_000:.1f} m²"


def _count_stacks(vehicle_sessions):
    """Count packages with z > 0, both fleet-wide and per-vehicle."""
    total = 0
    per_vehicle = {}
    for vinfo, session in vehicle_sessions:
        vid = vinfo["vehicle_id"]
        stacks = sum(1 for pl in session._planner.placements if pl.z > 0)
        per_vehicle[vid] = stacks
        total += stacks
    return total, per_vehicle


def _per_vehicle_empty_floor(vehicle_sessions):
    """Return dict of vehicle_id -> largest empty floor region mm²."""
    result = {}
    for vinfo, session in vehicle_sessions:
        vid = vinfo["vehicle_id"]
        container = session._planner.state.container
        empty = _largest_empty_floor_region(session._planner.placements, container)
        result[vid] = empty
    return result





def optimize_layout(
    vehicle_sessions,
    packages: list[Package],
    unplaced_packages: Optional[list[Package]] = None,
    max_passes: int = 3,
    debug: bool = False,
    profile: Optional[PlannerProfile] = None,
):
    """Run fleet-level Destroy-and-Repair optimization.

    Args:
        vehicle_sessions: List of (vinfo_dict, LoadPlanningSession) tuples
            from the greedy distribution pass.
        packages: All engine Package objects that were passed to the
            original distribution (placed + unplaced).
        unplaced_packages: Packages that the original greedy pass could
            not place anywhere.
        max_passes: Maximum repair passes (default 3, overridden by profile).
        debug: Print debug output.
        profile: PlannerProfile controlling repair behaviour. When profile
            is provided and ``enable_repair`` is False the function returns
            immediately. When ``enable_adaptive_repair`` is True the loop
            terminates early when no meaningful improvement occurs.

    Returns:
        (vehicle_sessions, improved, stats) where vehicle_sessions are the
        (possibly improved) sessions, improved indicates whether any
        repair was accepted, and stats is a dict with repair metadata.
    """
    if unplaced_packages is None:
        unplaced_packages = []

    # ── Early skip when repair is disabled by profile ────────────
    if profile is not None and not profile.enable_repair:
        return vehicle_sessions, False, {
            "repair_passes": 0,
            "repair_improved": False,
        }

    max_passes = profile.max_repair_passes if profile else max_passes
    time_limit = profile.repair_time_limit_sec if profile else None

    old_metrics = _compute_fleet_metrics(vehicle_sessions)
    overall_improved = False
    total_rearrangement_attempts = 0
    start_time = time.time()
    repair_passes = 0

    for pass_num in range(1, max_passes + 1):
        # ── Time budget check ────────────────────────────────────
        if time_limit is not None and (time.time() - start_time) > time_limit:
            if debug:
                print(f"  Time limit ({time_limit}s) reached, stopping")
            break

        repair_passes = pass_num

        if debug:
            print(f"\nRepair Pass {pass_num}")

        records, unplaced_pkgs = _collect_placement_records(
            vehicle_sessions, unplaced_packages,
        )

        if not records:
            break

        # Snapshot pre-pass state for adaptive termination
        pre_metrics = old_metrics
        pre_stacks, _ = _count_stacks(vehicle_sessions)

        pass_improved = False
        current_sessions = vehicle_sessions

        for destroy_idx in range(len(records)):
            kept = records[:destroy_idx]
            destroyed = [r.package for r in records[destroy_idx:]]

            all_to_distribute = destroyed + unplaced_pkgs
            if not all_to_distribute:
                continue

            fresh_sessions = _recreate_sessions(current_sessions)
            _place_kept_packages(fresh_sessions, kept)

            _, _, _, _, dist_stats = distribute_across_vehicles(
                all_to_distribute, fresh_sessions, debug=False, profile=profile,
            )
            total_rearrangement_attempts += dist_stats.get("rearrangement_attempts", 0)

            new_metrics = _compute_fleet_metrics(fresh_sessions)

            if _is_better(new_metrics, old_metrics):
                removed_names = [r.package.name for r in records[destroy_idx:]]
                repacked_count = len(all_to_distribute)

                if debug:
                    for name in removed_names:
                        print(f"  Removed: {name}")
                    print(f"  Repacked: {repacked_count} packages")
                    print(f"  Packages placed: {old_metrics[0]} \u2192 {new_metrics[0]}")
                    print(f"  Vehicles used: {old_metrics[1]} \u2192 {new_metrics[1]}")
                    print(f"  Largest empty region: {_format_floor_area(old_metrics[2])} \u2192 {_format_floor_area(new_metrics[2])}")
                    print(f"  Average placement score: {old_metrics[3]:.1f} \u2192 {new_metrics[3]:.1f}")
                    print(f"  Fleet cost: {old_metrics[4]:.1f} \u2192 {new_metrics[4]:.1f}")
                    print("  Accepted")

                vehicle_sessions = fresh_sessions
                old_metrics = new_metrics
                current_sessions = fresh_sessions
                pass_improved = True
                overall_improved = True

        if pass_improved:
            # ── Adaptive termination ─────────────────────────────
            if profile and profile.enable_adaptive_repair:
                post_stacks, _ = _count_stacks(vehicle_sessions)
                vehicles_reduced = old_metrics[1] < pre_metrics[1]
                stacks_reduced = post_stacks < pre_stacks

                if not vehicles_reduced and not stacks_reduced:
                    if debug:
                        print("  No vehicle or stack reduction — adaptive stop")
                    break
        else:
            if debug:
                print("  No improvement in this pass, stopping early")
            break

    stats = {
        "repair_passes": repair_passes,
        "repair_improved": overall_improved,
        "rearrangement_attempts": total_rearrangement_attempts,
    }
    return vehicle_sessions, overall_improved, stats
