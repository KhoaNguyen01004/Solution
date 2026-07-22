from __future__ import annotations

import math
from typing import Optional

_DEFAULT_STRIP_MM = 200


class FrontierTracker:
    """Tracks the deepest occupied X position per Y-strip.

    After each floor-level placement, the frontier advances for every
    Y-strip the package footprint covers.  A "gap" exists when a newly
    placed package sits behind (greater X than) the current frontier of
    its Y-strip — the space ahead of it is wasted.

    This tracker is used during the greedy placement pass to penalise
    gap-inducing candidates, and during post-processing to identify
    already-placed packages that need re-settling.
    """

    def __init__(self, container_width: float, strip_width_mm: float = _DEFAULT_STRIP_MM):
        self.strip_width = strip_width_mm
        self._container_width = container_width
        self.num_strips = max(1, math.ceil(container_width / strip_width_mm))
        self._frontier: list[float] = [0.0] * self.num_strips

    # ── Query ──────────────────────────────────────────────────────────

    def get_frontier_at(self, y: float) -> float:
        """Return the frontier X for the strip covering position *y*."""
        idx = self._strip_index(y)
        return self._frontier[idx]

    def gap_distance(self, xmin: float, y: float, y_span: float) -> float:
        """How far *xmin* is behind the frontier across the Y-span.

        Returns the *maximum* deficit across all strips the package
        overlaps.  Zero or negative means no gap (fully at or ahead of
        frontier).
        """
        max_gap = 0.0
        for idx in self._covered_strips(y, y_span):
            gap = self._frontier[idx] - xmin
            if gap > max_gap:
                max_gap = gap
        return max_gap

    def gap_ratio(self, xmin: float, y: float, y_span: float) -> float:
        """Fraction of Y-span that is behind the frontier (0..1).

        Returns how much of the package's Y-width sits in strips where
        the frontier is ahead of its xmin.  0.0 = fully at/forward of
        frontier; 1.0 = fully behind.
        """
        total_overlap = 0.0
        for idx in self._covered_strips(y, y_span):
            strip_ymin = idx * self.strip_width
            strip_ymax = min((idx + 1) * self.strip_width, self._container_width)
            y_lo = max(y, strip_ymin)
            y_hi = min(y + y_span, strip_ymax)
            if y_hi > y_lo:
                overlap = y_hi - y_lo
                if self._frontier[idx] > xmin:
                    total_overlap += overlap
        return min(total_overlap / max(y_span, 1.0), 1.0)

    # ── Mutation ───────────────────────────────────────────────────────

    def update(self, xmin: float, xmax: float, y: float, y_span: float,
               clearance: float = 10.0) -> None:
        """Advance the frontier for every Y-strip covered by [y, y+span].

        The frontier is set to ``max(current, xmax + clearance)`` — it
        never recedes.
        """
        new_x = xmax + clearance
        for idx in self._covered_strips(y, y_span):
            if new_x > self._frontier[idx]:
                self._frontier[idx] = new_x

    def update_from_placement(self, pl) -> None:
        """Convenience: update frontier from a Placement."""
        pkg = pl.package
        if pkg is None or pl.z > 0.001:
            return
        if pl.rotation in (90, 270):
            dx, dy = pkg.width_mm, pkg.length_mm
        else:
            dx, dy = pkg.length_mm, pkg.width_mm
        h_clr = getattr(pkg, 'horizontal_clearance_mm', 10.0)
        self.update(pl.x, pl.x + dx, pl.y, dy, clearance=h_clr)

    def reset(self) -> None:
        self._frontier = [0.0] * self.num_strips

    # ── Internal ───────────────────────────────────────────────────────

    def _strip_index(self, y: float) -> int:
        idx = int(y // self.strip_width)
        return min(idx, self.num_strips - 1)

    def _covered_strips(self, y: float, y_span: float) -> range:
        start = int(y // self.strip_width)
        end = int((y + y_span - 0.001) // self.strip_width)
        return range(max(0, start), min(end, self.num_strips - 1) + 1)
