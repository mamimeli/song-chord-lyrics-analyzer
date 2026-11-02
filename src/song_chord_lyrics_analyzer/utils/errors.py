"""Exception hierarchy for user-facing errors.

The CLI translates these exceptions into short, actionable messages instead of
raw tracebacks (roadmap section 63).
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "AnalysisCancelled",
    "AudioFileNotFoundError",
    "ConfigError",
    "DuplicateEngineError",
    "DependencyError",
    "EngineNotFoundError",
    "InputError",
    "SchemaError",
    "SongLabError",
    "UnsupportedAudioError",
]

#: Exit code used when the user supplied something invalid.
EXIT_INPUT_ERROR = 2
#: Exit code used when an external tool or optional dependency is missing.
EXIT_DEPENDENCY_ERROR = 3
#: Exit code used for unexpected internal failures.
EXIT_INTERNAL_ERROR = 1
#: Exit code used when the run was stopped on purpose: the same one a shell
#: reports for ``Ctrl+C`` (128 + SIGINT), because it means the same thing.
EXIT_INTERRUPTED = 130


class SongLabError(Exception):
    """Base class for all expected, user-facing failures.

    Attributes:
        message: One-line explanation of what went wrong.
        hint: Optional instruction telling the user how to recover.
    """

    exit_code: int = EXIT_INTERNAL_ERROR

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        if self.hint:
            return f"{self.message}\n\n{self.hint}"
        return self.message


class InputError(SongLabError):
    """The user provided invalid input (missing file, bad argument, ...)."""

    exit_code = EXIT_INPUT_ERROR


class AudioFileNotFoundError(InputError):
    """The requested audio file does not exist."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            f"Audio file not found: {path}",
            hint="Check the path and try again.",
        )
        self.path = path


class UnsupportedAudioError(InputError):
    """The file exists but does not look like usable audio."""

    def __init__(self, path: Path, *, reason: str | None = None) -> None:
        message = f"Unsupported or unreadable audio file: {path}"
        if reason:
            message = f"{message}\nReason: {reason}"
        super().__init__(
            message,
            hint=(
                "Supported container formats include WAV, MP3, FLAC, OGG, M4A, AAC "
                "and AIFF. Install FFmpeg to extend format support.\n"
                f"Requested file: {path}"
            ),
        )
        self.path = path


class DependencyError(SongLabError):
    """An external executable or optional Python dependency is missing."""

    exit_code = EXIT_DEPENDENCY_ERROR


class AnalysisCancelled(SongLabError):
    """The caller stopped a run that was still working.

    Its own type because it must never be mistaken for what an analysis can also
    do on its own. An engine that raises is a breakdown: that is recorded as a
    failed step and the rest of the document survives. Here the caller refused the
    work, so the run returns *nothing* - a caller that kept half a document would
    be presenting work it never finished, and an engine that was never given the
    chance to finish is not a broken one.

    Attributes:
        stopped_at: What the run refused to start, e.g. ``'the lyrics layer'`` or
            ``'chord window 2 of 3 (120.0-180.0 s)'``, so the message names the
            real unit of work rather than the abstraction that cancelled.
    """

    exit_code = EXIT_INTERRUPTED

    def __init__(self, stopped_at: str, *, hint: str | None = None) -> None:
        super().__init__(
            f"The analysis was stopped before {stopped_at}.",
            hint=hint
            or (
                "A stopped run assembles no document, so there is no partial "
                "result to keep: analyse the song again from the start."
            ),
        )
        self.stopped_at = stopped_at


class EngineNotFoundError(InputError):
    """The requested analysis engine is not registered."""

    def __init__(self, kind: str, name: str, available: list[str]) -> None:
        available_text = ", ".join(available) if available else "(none registered)"
        super().__init__(
            f"Unknown {kind} engine: {name}",
            hint=f"Available {kind} engines: {available_text}",
        )
        self.kind = kind
        self.name = name
        self.available = available


class DuplicateEngineError(SongLabError):
    """An engine with the same name is already registered for that kind."""

    def __init__(self, kind: str, name: str) -> None:
        super().__init__(f"A {kind} engine named {name!r} is already registered.")
        self.kind = kind
        self.name = name


class ConfigError(SongLabError):
    """The configuration is invalid or inconsistent."""

    exit_code = EXIT_INPUT_ERROR


class SchemaError(SongLabError):
    """A canonical document could not be (de)serialized."""

    exit_code = EXIT_INPUT_ERROR
