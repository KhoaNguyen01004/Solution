"""
Axis-Aligned Bounding Box (AABB) and coordinate transformation utilities.
Pure geometry — no business logic.
"""


class AABB:
    __slots__ = ("xmin", "ymin", "zmin", "xmax", "ymax", "zmax")

    def __init__(self, xmin: float, ymin: float, zmin: float,
                 xmax: float, ymax: float, zmax: float):
        self.xmin = xmin
        self.ymin = ymin
        self.zmin = zmin
        self.xmax = xmax
        self.ymax = ymax
        self.zmax = zmax

    @classmethod
    def from_dimensions(cls, x: float, y: float, z: float,
                        length_mm: float, width_mm: float, height_mm: float,
                        rotation: int = 0, clearance: float = 0):
        if rotation in (90, 270):
            dx = width_mm
            dy = length_mm
        else:
            dx = length_mm
            dy = width_mm
        return cls(x - clearance, y - clearance, z - clearance,
                   x + dx + clearance, y + dy + clearance, z + height_mm + clearance)

    def intersects(self, other: "AABB") -> bool:
        return (
            self.xmin < other.xmax and self.xmax > other.xmin
            and self.ymin < other.ymax and self.ymax > other.ymin
            and self.zmin < other.zmax and self.zmax > other.zmin
        )

    def contains(self, other: "AABB") -> bool:
        return (
            self.xmin <= other.xmin and self.xmax >= other.xmax
            and self.ymin <= other.ymin and self.ymax >= other.ymax
            and self.zmin <= other.zmin and self.zmax >= other.zmax
        )

    def contains_point(self, x: float, y: float, z: float, tol: float = 0.001) -> bool:
        return (
            self.xmin - tol <= x <= self.xmax + tol
            and self.ymin - tol <= y <= self.ymax + tol
            and self.zmin - tol <= z <= self.zmax + tol
        )

    def strictly_contains_point(self, x: float, y: float, z: float, tol: float = 0.001) -> bool:
        """Check if point is strictly inside (exclusive on max boundaries).

        A point on the right/front/top face of a package is a valid
        adjacent position, not an occupied one, so the max boundary
        is excluded.

        ``xmin - tol <= x < xmax`` — the tolerance on the min side
        catches floating-point near-zero; the strict ``< xmax``
        allows points exactly on the right/front/top face.
        """
        return (
            self.xmin - tol <= x < self.xmax
            and self.ymin - tol <= y < self.ymax
            and self.zmin - tol <= z < self.zmax
        )

    def translate(self, dx: float = 0, dy: float = 0, dz: float = 0) -> "AABB":
        return AABB(
            self.xmin + dx, self.ymin + dy, self.zmin + dz,
            self.xmax + dx, self.ymax + dy, self.zmax + dz,
        )

    def overlap_area_xy(self, other: "AABB") -> float:
        dx = max(0, min(self.xmax, other.xmax) - max(self.xmin, other.xmin))
        dy = max(0, min(self.ymax, other.ymax) - max(self.ymin, other.ymin))
        return dx * dy


def mm_to_px(mm: float, scale: float) -> float:
    return mm * scale


def px_to_mm(px: float, scale: float) -> float:
    return px / scale


def compute_scale(truck_length_mm: float, truck_width_mm: float,
                  canvas_width_px: int, canvas_height_px: int,
                  margin_px: int = 40) -> float:
    avail_w = canvas_width_px - 2 * margin_px
    avail_h = canvas_height_px - 2 * margin_px
    scale_x = avail_w / truck_length_mm if truck_length_mm else 1
    scale_y = avail_h / truck_width_mm if truck_width_mm else 1
    return min(scale_x, scale_y)


def rotate_dimensions(length: float, width: float, rotation: int):
    if rotation % 180 == 90:
        return width, length
    return length, width
