"""
Weight validation — tracks running total and checks against payload.
"""


def calculate_total_weight(placements: list) -> float:
    """Sum weight of all placed packages in kg."""
    return sum(p.get("_weight_kg", 0) for p in placements)


def check_weight(placements: list, payload_kg: float) -> dict:
    """Check if total weight exceeds truck payload.

    Returns:
        {"pass": True, "current_kg": ..., "payload_kg": ..., "remaining_kg": ...}
        or {"pass": False, "current_kg": ..., "payload_kg": ..., "remaining_kg": ..., "errors": [...]}
    """
    current = calculate_total_weight(placements)
    remaining = payload_kg - current
    if remaining >= 0:
        return {"pass": True, "current_kg": current, "payload_kg": payload_kg,
                "remaining_kg": remaining}
    return {"pass": False, "current_kg": current, "payload_kg": payload_kg,
            "remaining_kg": remaining,
            "errors": [f"Weight exceeded by {-remaining:.1f} kg"]}
