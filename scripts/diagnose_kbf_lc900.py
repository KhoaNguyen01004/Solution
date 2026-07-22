"""Diagnostic: KBF 280R + LC 900 gap scenario with debug output.

Usage:
    python scripts/diagnose_kbf_lc900.py          # standard output
    python scripts/diagnose_kbf_lc900.py --full    # detailed + saves to txt
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, r'D:\ChiTuyen\Solution')

from truck_load_planner.engine.package import Package
from truck_load_planner.engine.container import Container
from truck_load_planner.engine.planner import Planner
from truck_load_planner.engine.frontier import FrontierTracker
from truck_load_planner.engine.distribution import (
    fill_frontier_gaps, compact_placements, compact_stacks,
    reassign_load_sequences,
)
from truck_load_planner.engine.candidate_points import (
    settle_package, tighten_position,
)

TRUCK = Container(
    id=10, name="Truck 9700x2370x2320",
    length=9700, width=2370, height=2320, payload_kg=28000,
)

KBF = Package(id=1, name="KBF 280R", length_mm=1050, width_mm=2370,
              height_mm=2320, weight_kg=2000, stackable=False,
              allow_rotation=False)
LC900 = Package(id=2, name="LC 900-4/6TXA", length_mm=900, width_mm=770,
                height_mm=1200, weight_kg=500, stackable=True,
                allow_rotation=True)

# ── helpers ──────────────────────────────────────────────────────────

_log_lines = []

def log(*args, **kw):
    line = kw.pop('sep', ' ').join(str(a) for a in args) if not args else ''
    if args:
        line = (kw.pop('sep', ' ') if 'sep' in kw else ' ').join(str(a) for a in args)
    print(*args, **kw)
    _log_lines.append(line if args else '')


def fmt_frontier(frontier):
    lines = []
    for idx, f in enumerate(frontier._frontier):
        y_start = idx * frontier.strip_width
        y_end = min((idx + 1) * frontier.strip_width, TRUCK.width)
        label = f"  y=[{y_start:5.0f},{y_end:5.0f})"
        if f > 0.001:
            lines.append(f"{label}  frontier={f:8.0f}mm")
        else:
            lines.append(f"{label}  frontier=      0mm")
    return "\n".join(lines)


def placements_sorted(planner):
    return sorted(planner.placements, key=lambda p: p.x)


def fmt_placement(pl):
    pkg = pl.package
    if pl.rotation in (0, 180):
        dx, dy = pkg.length_mm, pkg.width_mm
    else:
        dx, dy = pkg.width_mm, pkg.length_mm
    xmax = pl.x + dx
    return (f"{pkg.name:15s} @ ({pl.x:7.0f}, {pl.y:7.0f}, {pl.z:3.0f}) "
            f"rot={pl.rotation:3d}  xmax={xmax:7.0f}  size={dx:4.0f}x{dy:4.0f}")


# ── detailed analysis ───────────────────────────────────────────────

def analyze_gap(frontier, pl, label):
    """Per-strip gap breakdown for a single package."""
    pkg = pl.package
    if pl.rotation in (0, 180):
        dx, dy = pkg.length_mm, pkg.width_mm
    else:
        dx, dy = pkg.width_mm, pkg.length_mm

    lines = [f"  [{label}] {fmt_placement(pl)}"]
    gap = frontier.gap_distance(pl.x, pl.y, dy)
    lines.append(f"    gap_distance={gap:.0f}mm (max deficit across all strips)")

    for idx in frontier._covered_strips(pl.y, dy):
        y_start = idx * frontier.strip_width
        y_end = min((idx + 1) * frontier.strip_width, TRUCK.width)
        fr = frontier._frontier[idx]
        deficit = max(0, fr - pl.x)
        lines.append(f"    strip y=[{y_start:5.0f},{y_end:5.0f}): "
                     f"fr={fr:8.0f}  deficit={deficit:6.0f}mm")
    lines.append("")
    return "\n".join(lines)


def analyze_settle(planner, pl, label):
    """Test what settle_package would do with this package."""
    pkg = pl.package
    tx, ty, tz, trot = settle_package(planner, pkg, pl.x, pl.y, pl.z, pl.rotation)
    improved = abs(tx - pl.x) > 1.0
    lines = [
        f"  [{label}] settle_package: ({pl.x:.0f},{pl.y:.0f},{pl.z:.0f}) → "
        f"({tx:.0f},{ty:.0f},{tz:.0f})  improved={improved}"
    ]
    if not improved:
        tx2, ty2, tz2, trot2 = tighten_position(
            planner, pkg, pl.x, pl.y, pl.z, pl.rotation, step=50.0,
        )
        improved2 = abs(tx2 - pl.x) > 1.0
        lines.append(
            f"           tighten_position (step=50): ({pl.x:.0f}...) → "
            f"({tx2:.0f},{ty2:.0f},{tz2:.0f})  improved={improved2}"
        )
    lines.append("")
    return "\n".join(lines)


def frontier_with_breakdown(frontier, planner):
    """Show per-strip frontier with each package's contribution."""
    contrib = {i: [] for i in range(frontier.num_strips)}
    for pl in planner.placements:
        pkg = pl.package
        if pkg is None or pl.z > 0.001:
            continue
        h_clr = getattr(pkg, 'horizontal_clearance_mm', 10.0)
        if pl.rotation in (0, 180):
            dx, dy = pkg.length_mm, pkg.width_mm
        else:
            dx, dy = pkg.width_mm, pkg.length_mm
        new_x = pl.x + dx + h_clr
        for idx in frontier._covered_strips(pl.y, dy):
            contrib[idx].append((pkg.name[:12], new_x))

    lines = []
    for idx, fr in enumerate(frontier._frontier):
        y_start = idx * frontier.strip_width
        y_end = min((idx + 1) * frontier.strip_width, TRUCK.width)
        src = contrib[idx]
        if src:
            contrib_str = "; ".join(f"{n}→{x:.0f}" for n, x in src)
        else:
            contrib_str = "(none)"
        lines.append(f"  y=[{y_start:5.0f},{y_end:5.0f}): fr={fr:8.0f}  | {contrib_str}")
    return "\n".join(lines)


# ── main ────────────────────────────────────────────────────────────

def main():
    full = "--full" in sys.argv

    log("=" * 72)
    log("KBF 280R + LC 900 Diagnostic")
    log(f"Mode: {'FULL' if full else 'STANDARD'}")
    log(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 72)

    planner = Planner(TRUCK)

    # ── 1. Manually place KBF 280R flush at front wall ──
    r1 = planner.place_package(KBF, 0, 0, 0, 0)
    assert r1.valid, f"KBF failed: {r1.reasons}"
    log(f"\nPlaced KBF 280R @ (0, 0, 0)")

    # ── 2. Auto-arrange 3 LC 900 units ──
    pkgs = [LC900, LC900, LC900]
    result = planner.auto_arrange(pkgs, debug=True)
    log(f"\nAuto-arrange: placed={result.placed_packages}, failed={result.failed_packages}")

    # ── 3. Final positions ──
    log("\n" + "─" * 60)
    log("FINAL POSITIONS")
    log("─" * 60)
    for pl in placements_sorted(planner):
        log(f"  {fmt_placement(pl)}")

    # ── 4. Gap check ──
    log("\n" + "─" * 60)
    log("GAP CHECK")
    log("─" * 60)
    kbf_pl = [pl for pl in planner.placements if pl.package_id == 1][0]
    kbf_xmax = kbf_pl.x + KBF.length_mm
    log(f"  KBF right edge: x={kbf_xmax:.0f}mm")

    lc_pls = sorted([pl for pl in planner.placements if pl.package_id == 2],
                    key=lambda pl: pl.x)
    for i, pl in enumerate(lc_pls):
        pkg = pl.package
        if pl.rotation in (0, 180):
            dx = pkg.length_mm
        else:
            dx = pkg.width_mm
        pl_xmax = pl.x + dx
        if i == 0:
            gap = pl.x - kbf_xmax
            clearance_gap = (getattr(pkg, 'horizontal_clearance_mm', 10.0)
                             + getattr(KBF, 'horizontal_clearance_mm', 10.0))
            log(f"  LC900[{i}] @ x={pl.x:.0f}  xmax={pl_xmax:.0f}  "
                f"gap_from_KBF={gap:.0f}mm  (clearance={clearance_gap:.0f}mm)")
        else:
            prev = lc_pls[i - 1]
            prev_pkg = prev.package
            prev_xmax = prev.x + (prev_pkg.length_mm if prev.rotation in (0, 180)
                                  else prev_pkg.width_mm)
            gap = pl.x - prev_xmax
            # Y overlap check
            prev_dy = prev_pkg.width_mm if prev.rotation in (0, 180) else prev_pkg.length_mm
            cur_dy = pkg.width_mm if pl.rotation in (0, 180) else pkg.length_mm
            y_overlap = max(0, min(pl.y + cur_dy, prev.y + prev_dy) - max(pl.y, prev.y))
            side_by_side = y_overlap <= 0
            log(f"  LC900[{i}] @ x={pl.x:.0f}  xmax={pl_xmax:.0f}  "
                f"gap_from_LC900[{i-1}]={gap:+.0f}mm  "
                f"y_overlap={y_overlap:.0f}mm  side_by_side={side_by_side}")

    # ── 5. Full detailed analysis (--full only) ──
    if full:
        # 5a. Frontier with per-strip contribution sources
        log("\n" + "─" * 60)
        log("FRONTIER (per-strip breakdown)")
        log("─" * 60)
        frontier_bd = FrontierTracker(TRUCK.width, strip_width_mm=250)
        for pl in planner.placements:
            frontier_bd.update_from_placement(pl)
        log(frontier_with_breakdown(frontier_bd, planner))

        # 5b. Per-package gap analysis (frontier gap per strip)
        log("\n" + "─" * 60)
        log("PER-PACKAGE GAP ANALYSIS")
        log("─" * 60)
        for pl in placements_sorted(planner):
            pkg = pl.package
            if pl.z > 0.001:
                log(f"  [{pkg.name}] z={pl.z:.0f} > 0 (stacked, skip strip analysis)")
                continue
            label = f"{pkg.name[:12]}@{pl.x:.0f},{pl.y:.0f}"
            log(analyze_gap(frontier_bd, pl, label))

        # 5c. Per-package settle test
        log("─" * 60)
        log("SETTLE / TIGHTEN TEST")
        log("─" * 60)
        for pl in placements_sorted(planner):
            pkg = pl.package
            label = f"{pkg.name[:12]}@{pl.x:.0f}"
            log(analyze_settle(planner, pl, label))

    # ── 6. Debug log ──
    if result.debug_log:
        log("\n" + "─" * 60)
        log(f"DEBUG LOG ({len(result.debug_log)} entries)")
        log("─" * 60)
        for entry in result.debug_log:
            pos = entry.get("chosen_position")
            score = entry.get("best_score", 0)
            name = entry.get("package_name", "?")
            tight = "(tightened)" if entry.get("tightened") else ""
            slide = "(slide pass)" if entry.get("slide_pass") else ""
            if pos:
                log(f"  {name:15s} score={score:6.1f}  {tight}{slide:15s}  "
                    f"→ x={pos['x']:.0f} y={pos['y']:.0f} z={pos['z']:.0f}")
            else:
                log(f"  {name:15s} score={score:6.1f}  {tight}{slide:15s}  "
                    f"→ NO POSITION FOUND")

    # ── 7. Frontier from final placements ──
    log("\n" + "─" * 60)
    log("FRONTIER AFTER ALL PLACEMENTS")
    log("─" * 60)
    frontier = FrontierTracker(TRUCK.width, strip_width_mm=250)
    for pl in planner.placements:
        frontier.update_from_placement(pl)
    log(fmt_frontier(frontier))

    # ── 8. fill_frontier_gaps test ──
    log("\n" + "─" * 60)
    log("FILL FRONTIER GAPS")
    log("─" * 60)
    frontier2 = FrontierTracker(TRUCK.width, strip_width_mm=250)
    for pl in planner.placements:
        frontier2.update_from_placement(pl)
    before = len(planner.placements)
    moved = fill_frontier_gaps(planner, frontier2)
    after = len(planner.placements)
    log(f"  Packages moved: {moved}  (placements before={before}, after={after})")

    if full and moved > 0:
        log("\n  Positions after gap-fill:")
        for pl in placements_sorted(planner):
            log(f"    {fmt_placement(pl)}")

    # ── 9. Final validation ──
    total = planner.evaluate_plan()
    valid = planner.validate()
    log(f"\n  Plan total score: {total.total:.1f}")
    log(f"  Plan valid: {valid.valid}")
    if not valid.valid:
        log(f"  Reasons: {valid.reasons}")

    log("\n" + "=" * 72)
    log("DIAGNOSTIC COMPLETE")
    log("=" * 72)

    # ── Save to file (--full mode only) ──
    if full:
        out_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(out_dir, f"kbf_lc900_diagnostic_{ts}.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(_log_lines))
        log(f"\nReport saved to: {out_path}")


if __name__ == "__main__":
    main()
