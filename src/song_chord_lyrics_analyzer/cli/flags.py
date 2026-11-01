"""Shared validation for the numeric flags the commands accept.

``argparse`` turns ``--start nan`` and ``--start inf`` into perfectly ordinary
floats, and a ``NaN`` compares false against every bound, so a sign check alone
lets it through to the decoder — where it reappears as "unsupported or
unreadable audio file" for a file that opens fine. Finiteness is therefore
checked with the sign, at the command line, before any audio work starts.
"""

from __future__ import annotations

import math

from song_chord_lyrics_analyzer.utils.errors import InputError

__all__ = ["require_time_flag"]


def require_time_flag(flag: str, value: float | None) -> None:
    """Refuse a ``--flag`` whose seconds value cannot name a position.

    Args:
        flag: The flag name without its leading dashes, used in the message.
        value: The parsed value; ``None`` means the flag was not given.

    Raises:
        InputError: When the value is not a finite, non-negative number.
    """
    if value is None:
        return
    if not math.isfinite(value):
        raise InputError(
            f"--{flag} must be a finite number of seconds, got {value!r}.",
            hint="Times are real positions in the song; 'nan' and 'inf' are not accepted.",
        )
    if value < 0.0:
        raise InputError(
            f"--{flag} must not be negative, got {value!r}.",
            hint="Times are seconds from the start.",
        )
