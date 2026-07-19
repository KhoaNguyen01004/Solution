from dataclasses import dataclass, asdict
from typing import Optional


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
    clearance_mm: float = 10.0

    @property
    def volume_m3(self) -> float:
        return (self.length_mm * self.width_mm * self.height_mm) / 1_000_000_000

    def to_dict(self) -> dict:
        d = asdict(self)
        d["volume_m3"] = self.volume_m3
        return d

    @staticmethod
    def from_dict(data: dict) -> "Package":
        return Package(
            id=data.get("id"),
            name=data.get("name", ""),
            length_mm=data.get("length_mm", data.get("length", 0)),
            width_mm=data.get("width_mm", data.get("width", 0)),
            height_mm=data.get("height_mm", data.get("height", 0)),
            weight_kg=data.get("weight_kg", 0),
            stackable=bool(data.get("stackable", data.get("allow_stacking", 0))),
            allow_rotation=bool(data.get("allow_rotation", 0)),
            fragile=bool(data.get("fragile", 0)),
            color=data.get("color", "#3b82f6"),
            clearance_mm=float(data.get("clearance_mm", data.get("clearance", 10.0))),
        )
