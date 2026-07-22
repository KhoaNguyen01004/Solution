"""
License plate normalization utilities.

Vietnamese plates follow the pattern ``XX-XXXXX`` where the last 5 digits
are the globally unique serial number.  This module provides helpers for
extracting that identifying suffix regardless of formatting.
"""

import re
from typing import Optional


def normalize_plate(plate: Optional[str]) -> str:
    """Extract the trailing 5-digit serial from a license plate.

    Examples::

        normalize_plate("50H-09473")  ->  "09473"
        normalize_plate("09473")      ->  "09473"
        normalize_plate("50E18463")   ->  "18463"
        normalize_plate("18463")      ->  "18463"
        normalize_plate("")           ->  ""
        normalize_plate(None)         ->  ""

    Returns the last 5 digits found in the string, or the full digit
    sequence if it is shorter than 5 characters.
    """
    if not plate:
        return ""
    digits = re.sub(r"[^0-9]", "", plate)
    return digits[-5:] if len(digits) >= 5 else digits
