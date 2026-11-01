"""Shared numeric validation for the canonical model (roadmap section 38).

The canonical document is JSON, and JSON has no literal for ``NaN`` or
infinity: the codec writes the bare token, which strict parsers reject. The
model already refused negative times and reversed intervals, but a non-finite
float slips past a sign test — ``float("nan") < 0`` is false — so every
float-valued field asks the same question here. Refusing at the model boundary
means an engine bug cannot reach a document, an export or the window.
"""

from __future__ import annotations

import math

__all__ = ["require_finite"]


def require_finite(value: float, label: str) -> None:
    """Reject ``NaN`` and both infinities for a numeric model field.

    Args:
        value: The value the model is about to store.
        label: Field name used in the message, matching the wording of the
            sign and ordering checks next to it.

    Raises:
        ValueError: When ``value`` is not a finite number.
    """
    if not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number, got {value!r}")
