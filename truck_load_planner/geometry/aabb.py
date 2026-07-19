"""
Axis-Aligned Bounding Box (AABB) operations.
Pure geometry — no business logic.
"""


class AABB:
    """An axis-aligned bounding box defined by min/max corners."""

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
                        length: float, width: float, height: float,
                        rotation: int = 0):
        """Create AABB for a package at (x,y,z) with given dimensions.
        Rotation 0: length→X axis, width→Y axis.
        Rotation 90/270: length→Y axis, width→X axis.
        """
        if rotation in (90, 270):
            dx = width
            dy = length
        else:
            dx = length
            dy = width
        return cls(x, y, z, x + dx, y + dy, z + height)

    @property
    def width_x(self) -> float:
        return self.xmax - self.xmin

    @property
    def width_y(self) -> float:
        return self.ymax - self.ymin

    @property
    def width_z(self) -> float:
        return self.zmax - self.zmin

    @property
    def volume(self) -> float:
        return self.width_x * self.width_y * self.width_z

    def intersects(self, other: "AABB") -> bool:
        """Check if two AABBs overlap in 3D space."""
        return (
            self.xmin < other.xmax and self.xmax > other.xmin
            and self.ymin < other.ymax and self.ymax > other.ymin
            and self.zmin < other.zmax and self.zmax > other.zmin
        )

    def contains(self, other: "AABB") -> bool:
        """Check if this AABB fully contains another."""
        return (
            self.xmin <= other.xmin and self.xmax >= other.xmax
            and self.ymin <= other.ymin and self.ymax >= other.ymax
            and self.zmin <= other.zmin and self.zmax >= other.zmax
        )

    def translate(self, dx: float = 0, dy: float = 0, dz: float = 0) -> "AABB":
        return AABB(
            self.xmin + dx, self.ymin + dy, self.zmin + dz,
            self.xmax + dx, self.ymax + dy, self.zmax + dz,
        )
