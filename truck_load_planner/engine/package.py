from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional


class StackingMode(Enum):
    NONE = "none"
    LIGHT_ONLY = "light_only"
    NORMAL = "normal"

    def __str__(self) -> str:
        return self.value


@dataclass
class Package:
    id: Optional[int] = None
    name: str = ""
    length_mm: float = 0.0
    width_mm: float = 0.0
    height_mm: float = 0.0
    weight_kg: float = 0.0
    stackable: bool = False
    allow_rotation: bool = False
    fragile: bool = False
    color: str = "#3b82f6"
    horizontal_clearance_mm: float = 10.0
    vertical_clearance_mm: float = 0.0
    max_top_weight_kg: float = 0.0
    max_stack_layers: int = 0
    stacking_mode: StackingMode = StackingMode.NORMAL

    def __post_init__(self):
        if not self.stackable and self.stacking_mode == StackingMode.NORMAL:
            self.stacking_mode = StackingMode.NONE

    @property
    def volume_m3(self) -> float:
        return (self.length_mm * self.width_mm * self.height_mm) / 1_000_000_000

    @property
    def clearance_mm(self) -> float:
        """Deprecated: kept for backward compatibility during migration."""
        return self.horizontal_clearance_mm

    def to_dict(self) -> dict:
        d = asdict(self)
        d["volume_m3"] = self.volume_m3
        d["stacking_mode"] = self.stacking_mode.value
        return d

    @staticmethod
    def _derive_stacking_mode(data: dict) -> StackingMode:
        explicit = data.get("stacking_mode")
        if explicit is not None:
            if isinstance(explicit, StackingMode):
                return explicit
            try:
                return StackingMode(explicit)
            except ValueError:
                pass
        max_top = data.get("max_top_weight_kg", 0.0)
        if max_top and float(max_top) > 0:
            return StackingMode.LIGHT_ONLY
        old = bool(data.get("stackable", data.get("allow_stacking", 0)))
        return StackingMode.NORMAL if old else StackingMode.NONE

    @staticmethod
    def from_dict(data: dict) -> "Package":
        old_clr = data.get("clearance_mm", data.get("clearance", None))
        if old_clr is not None:
            h_clr = float(old_clr)
            v_clr = 0.0
        else:
            h_clr = float(data.get("horizontal_clearance_mm", 10.0))
            v_clr = float(data.get("vertical_clearance_mm", 0.0))
        mode = Package._derive_stacking_mode(data)
        stackable = bool(data.get("stackable", data.get("allow_stacking", 0)))
        return Package(
            id=data.get("id"),
            name=data.get("name", ""),
            length_mm=data.get("length_mm", data.get("length", 0)),
            width_mm=data.get("width_mm", data.get("width", 0)),
            height_mm=data.get("height_mm", data.get("height", 0)),
            weight_kg=data.get("weight_kg", 0),
            stackable=stackable,
            allow_rotation=bool(data.get("allow_rotation", 0)),
            fragile=bool(data.get("fragile", 0)),
            color=data.get("color", "#3b82f6"),
            horizontal_clearance_mm=h_clr,
            vertical_clearance_mm=v_clr,
            max_top_weight_kg=float(data.get("max_top_weight_kg", 0.0)),
            max_stack_layers=int(data.get("max_stack_layers", 0)),
            stacking_mode=mode,
        )
