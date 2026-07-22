"""General diagnostic: run detailed analysis on any package arrangement.

Usage:
    python scripts/diagnose.py <scenario> [--full]

Scenarios:
    kbf_lc900    KBF 280R (full-width) + 3× LC900 (gap regression)
    mixed        5× PKG_A + 3× PKG_B + 2× PKG_C (general mixed)
    custom       Define packages inline (see source)

    Use --full for detailed per-strip breakdown + saved report.
"""

import sys
import os
from datetime import datetime
from typing import Optional

sys.path.insert(0, r'D:\ChiTuyen\Solution')

from truck_load_planner.engine.package import Package
from truck_load_planner.engine.container import Container
from truck_load_planner.engine.planner import Planner
from truck_load_planner.engine.frontier import FrontierTracker
from truck_load_planner.engine.distribution import fill_frontier_gaps
from truck_load_planner.engine.candidate_points import (
    settle_package, tighten_position,
)

# ── log capture ────────────────────────────────────────────────────

_log_lines: list[str] = []


def log(*args, **kw):
    text = " ".join(str(a) for a in args)
    print(text)
    _log_lines.append(text)


# ── standard containers ────────────────────────────────────────────

CONTAINERS = {
    "truck": Container(
        id=10, name="Truck 9700×2370×2320",
        length=9700, width=2370, height=2320, payload_kg=28000,
    ),
    "40ft": Container(
        id=1, name="40ft Container",
        length=12000, width=2400, height=2700, payload_kg=28000,
    ),
    "small": Container(
        id=2, name="Small Box",
        length=2000, width=1500, height=1500, payload_kg=5000,
    ),
}

# ── common packages ────────────────────────────────────────────────

PACKAGES = {
    "KBF": Package(id=1, name="KBF 280R", length_mm=1050, width_mm=2370,
                   height_mm=2320, weight_kg=2000, stackable=False,
                   allow_rotation=False),
    "LC900": Package(id=2, name="LC 900-4/6TXA", length_mm=900, width_mm=770,
                     height_mm=1200, weight_kg=500, stackable=True,
                     allow_rotation=True),
    "PKG_A": Package(id=101, name="PKG_A", length_mm=1200, width_mm=1000,
                     height_mm=800, weight_kg=300, stackable=True,
                     allow_rotation=True),
    "PKG_B": Package(id=102, name="PKG_B", length_mm=800, width_mm=600,
                     height_mm=500, weight_kg=150, stackable=True,
                     allow_rotation=True),
    "PKG_C": Package(id=103, name="PKG_C", length_mm=600, width_mm=400,
                     height_mm=300, weight_kg=80, stackable=True,
                     allow_rotation=True),
}


# ══════════════════════════════════════════════════════════════════
#  Diagnostic engine
# ══════════════════════════════════════════════════════════════════

def run_diagnostic(planner: Planner,
                   container: Container,
                   package_list: list[Package],
                   *,
                   full: bool = False,
                   label: str = "diagnostic") -> str:
    """Run full diagnostic on a planner after auto-arrange.

    Args:
        planner: Planner with container already set.
        container: Container used (for frontier dimensions).
        package_list: Packages passed to auto_arrange.
        full: If True, include per-strip breakdown and save report.
        label: Label for the report filename.

    Returns:
        Path to saved report file (empty string if not saved).
    """
    _log_lines.clear()

    header(f"Package Arrangement Diagnostic: {label}")
    log(f"Container: {container.name}  ({container.length}×{container.width}×{container.height})")
    log(f"Packages:  {len(package_list)} units")
    for p in package_list:
        log(f"  - {p.name}  {p.length_mm}×{p.width_mm}×{p.height_mm}  "
            f"{p.weight_kg}kg  stackable={p.stackable}")
    log(f"Mode:      {'FULL' if full else 'STANDARD'}")
    log(f"Time:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    header("AUTO-ARRANGE")

    result = planner.auto_arrange(package_list, debug=True)
    log(f"Placed: {result.placed_packages}  Failed: {result.failed_packages}")

    # ── 1. Final positions ──
    header("FINAL POSITIONS")
    for pl in sorted(planner.placements, key=lambda p: p.x):
        log(f"  {fmt_pl(pl)}")

    # ── 2. Gap check ──
    header("GAP CHECK (adjacent packages)")
    placements_sorted = sorted(planner.placements, key=lambda p: p.x)
    for i, pl in enumerate(placements_sorted):
        pkg = pl.package
        dx = pkg.length_mm if pl.rotation in (0, 180) else pkg.width_mm
        pl_xmax = pl.x + dx
        if i == 0:
            log(f"  [{pkg.name}] @ x={pl.x:.0f}  xmax={pl_xmax:.0f}  (first package)")
        else:
            prev = placements_sorted[i - 1]
            prev_pkg = prev.package
            prev_dx = prev_pkg.length_mm if prev.rotation in (0, 180) else prev_pkg.width_mm
            prev_xmax = prev.x + prev_dx
            gap = pl.x - prev_xmax
            prev_dy = prev_pkg.width_mm if prev.rotation in (0, 180) else prev_pkg.length_mm
            cur_dy = pkg.width_mm if pl.rotation in (0, 180) else pkg.length_mm
            y_overlap = max(0, min(pl.y + cur_dy, prev.y + prev_dy) - max(pl.y, prev.y))
            log(f"  [{pkg.name}] @ x={pl.x:.0f}  xmax={pl_xmax:.0f}  "
                f"gap_from_prev={gap:+.0f}mm  y_overlap={y_overlap:.0f}mm  "
                f"{'SIDE_BY_SIDE' if y_overlap <= 0 else 'IN_LINE'}")

    # ── 3. Frontier with per-strip contributions ──
    frontier = FrontierTracker(container.width, strip_width_mm=200)
    for pl in planner.placements:
        frontier.update_from_placement(pl)

    if full:
        header("FRONTIER (per-strip contribution breakdown)")
        log(fmt_frontier_breakdown(frontier, planner.placements, container.width))

    # ── 4. Per-package gap analysis ──
    header("PER-PACKAGE FRONTIER GAP")
    for pl in sorted(planner.placements, key=lambda p: p.x):
        if pl.z > 0.001:
            log(f"  [{pl.package.name}]  z={pl.z:.0f} > 0 (stacked, skip)")
            continue
        log(analyze_gap(frontier, pl, container.width))

    # ── 5. Settle / tighten test ──
    if full:
        header("SETTLE / TIGHTEN TEST")
        for pl in sorted(planner.placements, key=lambda p: p.x):
            log(analyze_settle(planner, pl))

    # ── 6. Debug log ──
    if result.debug_log:
        header(f"DEBUG LOG ({len(result.debug_log)} entries)")
        for entry in result.debug_log:
            pos = entry.get("chosen_position")
            score = entry.get("best_score", 0)
            name = entry.get("package_name", "?")
            tight = "TIGHTENED" if entry.get("tightened") else ""
            slide = "SLIDE" if entry.get("slide_pass") else ""
            flags = " | ".join(filter(None, [tight, slide]))
            if pos:
                log(f"  {name:20s}  score={score:6.1f}  [{flags:20s}]  "
                    f"→ x={pos['x']:7.0f} y={pos['y']:7.0f} z={pos['z']:3.0f}")
            else:
                log(f"  {name:20s}  score={score:6.1f}  [{flags:20s}]  "
                    f"→ NO POSITION")

    # ── 7. Frontier summary ──
    header("FRONTIER AFTER ALL PLACEMENTS")
    log(fmt_frontier(frontier, container.width))

    # ── 8. fill_frontier_gaps test ──
    header("FILL FRONTIER GAPS")
    frontier2 = FrontierTracker(container.width, strip_width_mm=200)
    for pl in planner.placements:
        frontier2.update_from_placement(pl)
    before = len(planner.placements)
    moved = fill_frontier_gaps(planner, frontier2)
    after = len(planner.placements)
    log(f"  Packages moved: {moved}  (placements before={before}, after={after})")

    if full and moved > 0:
        log("  Positions after gap-fill:")
        for pl in sorted(planner.placements, key=lambda p: p.x):
            log(f"    {fmt_pl(pl)}")

    # ── 9. Validation ──
    header("VALIDATION")
    total = planner.evaluate_plan()
    valid = planner.validate()
    log(f"  Score: {total.total:.1f}")
    log(f"  Valid: {valid.valid}")
    if not valid.valid:
        for r in valid.reasons:
            log(f"    - {r}")

    header("DIAGNOSTIC COMPLETE")

    # ── Save report (full mode only) ──
    saved = ""
    if full:
        out_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(out_dir, f"{label}_{ts}.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(_log_lines))
        log(f"\nReport saved to: {out_path}")
        saved = out_path

    return saved


# ══════════════════════════════════════════════════════════════════
#  Formatting helpers
# ══════════════════════════════════════════════════════════════════

def header(title: str):
    log("")
    log("─" * 60)
    log(title)
    log("─" * 60)


def fmt_pl(pl) -> str:
    pkg = pl.package
    if pl.rotation in (0, 180):
        dx, dy = pkg.length_mm, pkg.width_mm
    else:
        dx, dy = pkg.width_mm, pkg.length_mm
    xmax = pl.x + dx
    return (f"{pkg.name:20s}  @ ({pl.x:7.0f}, {pl.y:7.0f}, {pl.z:3.0f})  "
            f"rot={pl.rotation:3d}°  xmax={xmax:7.0f}  "
            f"dim={dx:4.0f}×{dy:4.0f}×{pkg.height_mm:4.0f}")


def fmt_frontier(frontier, cw: float) -> str:
    lines = []
    for idx, f in enumerate(frontier._frontier):
        y_start = idx * frontier.strip_width
        y_end = min((idx + 1) * frontier.strip_width, cw)
        val = f"{f:8.0f}mm" if f > 0.001 else "      0mm"
        lines.append(f"  y=[{y_start:5.0f},{y_end:5.0f})  frontier={val}")
    return "\n".join(lines)


def fmt_frontier_breakdown(frontier, placements, cw: float) -> str:
    contrib = {i: [] for i in range(frontier.num_strips)}
    for pl in placements:
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
            contrib[idx].append((pkg.name[:14], new_x))

    lines = []
    for idx, fr in enumerate(frontier._frontier):
        y_start = idx * frontier.strip_width
        y_end = min((idx + 1) * frontier.strip_width, cw)
        src = contrib[idx]
        if src:
            contrib_str = "; ".join(f"{n}→{x:.0f}" for n, x in src)
        else:
            contrib_str = "(none)"
        lines.append(f"  y=[{y_start:5.0f},{y_end:5.0f}): fr={fr:8.0f}  | {contrib_str}")
    return "\n".join(lines)


def analyze_gap(frontier, pl, cw: float) -> str:
    pkg = pl.package
    dy = pkg.width_mm if pl.rotation in (0, 180) else pkg.length_mm
    gap = frontier.gap_distance(pl.x, pl.y, dy)
    lines = [
        f"  [{pkg.name}]  {fmt_pl(pl)}",
        f"    gap_distance={gap:.0f}mm (max deficit across strips)",
    ]
    for idx in frontier._covered_strips(pl.y, dy):
        y_start = idx * frontier.strip_width
        y_end = min((idx + 1) * frontier.strip_width, cw)
        fr = frontier._frontier[idx]
        deficit = max(0, fr - pl.x)
        lines.append(f"    strip y=[{y_start:5.0f},{y_end:5.0f}):  "
                     f"fr={fr:8.0f}  deficit={deficit:6.0f}mm")
    return "\n".join(lines)


def analyze_settle(planner, pl) -> str:
    pkg = pl.package
    tx, ty, tz, trot = settle_package(planner, pkg, pl.x, pl.y, pl.z, pl.rotation)
    improved = abs(tx - pl.x) > 1.0
    lines = [
        f"  [{pkg.name}]  settle:  ({pl.x:.0f},{pl.y:.0f},{pl.z:.0f}) → "
        f"({tx:.0f},{ty:.0f},{tz:.0f})  improved={improved}"
    ]
    if not improved:
        tx2, ty2, tz2, trot2 = tighten_position(
            planner, pkg, pl.x, pl.y, pl.z, pl.rotation, step=50.0,
        )
        improved2 = abs(tx2 - pl.x) > 1.0
        lines.append(
            f"             tighten: ({pl.x:.0f}...) → "
            f"({tx2:.0f},{ty2:.0f},{tz2:.0f})  improved={improved2}"
        )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
#  Scenarios
# ══════════════════════════════════════════════════════════════════

def make_planner(container_key: str = "truck") -> tuple[Planner, Container]:
    c = CONTAINERS[container_key]
    return Planner(c), c


def scenario_kbf_lc900(full: bool) -> str:
    planner, container = make_planner("truck")
    kbf = PACKAGES["KBF"]
    lc = PACKAGES["LC900"]
    r1 = planner.place_package(kbf, 0, 0, 0, 0)
    assert r1.valid, f"KBF placement failed: {r1.reasons}"
    pkgs = [lc, lc, lc]
    return run_diagnostic(planner, container, pkgs, full=full, label="kbf_lc900")


def scenario_mixed(full: bool) -> str:
    planner, container = make_planner("truck")
    pkgs = [
        PACKAGES["PKG_A"], PACKAGES["PKG_A"], PACKAGES["PKG_A"],
        PACKAGES["PKG_B"], PACKAGES["PKG_B"], PACKAGES["PKG_B"],
        PACKAGES["PKG_C"], PACKAGES["PKG_C"],
    ]
    return run_diagnostic(planner, container, pkgs, full=full, label="mixed")


# ══════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════

def main():
    scenarios = {
        "kbf_lc900": scenario_kbf_lc900,
        "mixed": scenario_mixed,
    }

    if len(sys.argv) < 2 or sys.argv[1] not in scenarios:
        print(__doc__)
        print("Available scenarios:")
        for k in scenarios:
            print(f"  {k}")
        sys.exit(1)

    full = "--full" in sys.argv
    scenario = sys.argv[1]
    saved = scenarios[scenario](full)
    if saved:
        print(f"\nReport: {saved}")


if __name__ == "__main__":
    main()
