"""Preferences the window remembers between runs (roadmap section 12, task L8).

``docs/DEVELOPMENT.md`` long promised that user-facing configuration "belongs in
explicit CLI options and (later) the settings dialog". This is the store that
promise needs: one small JSON file in songlab's own data directory, and the only
place a preference may live. A widget holds none, because a widget cannot be read
back after the process ends.

Two settings are committed, and only two, because a setting is committed only when
the window already has a control that writes it (`docs/GUI_REQUIREMENTS.md` item 8):
the language picked from the Language menu, and the folder the last song was opened
from. A chord chunk size and a spelling override are named there as *not* committed,
with the reason - no control writes them yet.

What makes a preference file different from a document, and shapes this module:

* **it may not break the application.** A missing, empty, corrupt, foreign or
  half-written file costs the preference and nothing else: reading one returns the
  defaults and never raises. The window is what the person came back for.
* **an unknown value is refused here, at the boundary.** A language the project
  does not plan is English, a folder that is not a directory is no folder, so no
  downstream reader revalidates a string that came off disk.
* **a write that fails loses the preference, not the window.** The file is written
  atomically, like every file a person owns, and an ``OSError`` on the way out is
  logged and dropped.
* **no version is stamped.** A document needs a schema because another build has to
  read it; a preference file has no migration to guard, and a value this build does
  not understand already falls back to its default.

``SONGLAB_DATA_DIR`` moves the file; no CLI option and no new environment variable
chooses it, because `songlab gui` is the only surface that has preferences to keep.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from song_chord_lyrics_analyzer.i18n import LANGUAGES, SOURCE_LANGUAGE
from song_chord_lyrics_analyzer.utils.logging import get_logger
from song_chord_lyrics_analyzer.utils.paths import (
    canonical_path_str,
    default_data_dir,
    ensure_directory,
    write_text_atomic,
)

__all__ = [
    "SETTINGS_FILENAME",
    "PreferenceStore",
    "Preferences",
    "default_preferences_path",
    "load_preferences",
    "save_preferences",
]

#: Name of the file inside songlab's data directory.
SETTINGS_FILENAME = "settings.json"

_logger = get_logger(__name__)


@dataclass(frozen=True)
class Preferences:
    """What the window remembers, with the value it uses when it remembers nothing.

    Attributes:
        language: The language code the window opens in. Always a key of
            :data:`~song_chord_lyrics_analyzer.i18n.LANGUAGES`; whether its
            catalogue is installed is the window's question, not this class's.
        last_folder: The directory the last song was opened from, or ``None``.
    """

    language: str = SOURCE_LANGUAGE
    last_folder: Path | None = None


def default_preferences_path() -> Path:
    """The file the window reads and writes: ``<data dir>/settings.json``."""
    return default_data_dir() / SETTINGS_FILENAME


def load_preferences(path: str | Path) -> Preferences:
    """Read ``path`` and return what can be trusted from it.

    Never raises for a file the person cannot have meant: absence, unreadable
    bytes, invalid JSON, a list where an object was expected and any single
    unusable value all end the same way - the defaults, for the whole file or for
    that one key.

    Args:
        path: The settings file.

    Returns:
        The remembered preferences, or the defaults.
    """
    values = _read_mapping(Path(path))
    return Preferences(
        language=_language_or_default(values.get("language")),
        last_folder=_folder_or_none(values.get("last_folder")),
    )


def save_preferences(preferences: Preferences, path: str | Path) -> Path:
    """Write ``preferences`` to ``path``, creating its directory.

    Args:
        preferences: The values to write.
        path: Where to write them.

    Returns:
        The path written.

    Raises:
        OSError: When the file could not be created or written. Callers that are
            keeping a window open catch it: a preference that cannot be stored is
            not a reason to lose the session.
    """
    target = Path(path)
    ensure_directory(target.parent)
    return write_text_atomic(
        target,
        json.dumps(_as_mapping(preferences), indent=2, sort_keys=True, ensure_ascii=False),
    )


class PreferenceStore:
    """The preferences file, read once and rewritten when a choice changes.

    The window asks it where to open a dialog and tells it what the person picked;
    it is the only object that knows the file's path, so a widget never builds a
    path of its own.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        """Read the file at ``path``, defaulting to :func:`default_preferences_path`."""
        self._path = Path(path) if path is not None else default_preferences_path()
        self._preferences = load_preferences(self._path)

    @property
    def path(self) -> Path:
        """The file this store reads and writes."""
        return self._path

    @property
    def preferences(self) -> Preferences:
        """The remembered values, as read at construction and updated since."""
        return self._preferences

    def start_folder(self) -> str:
        """Where a file dialog opens: the last folder, or ``""`` for Qt to choose."""
        return str(self._preferences.last_folder) if self._preferences.last_folder else ""

    def set_language(self, code: str) -> Preferences:
        """Remember the window's language; an unknown code remembers English."""
        return self._update(replace(self._preferences, language=_language_or_default(code)))

    def remember_folder(self, path: str | Path) -> Preferences:
        """Remember where ``path`` came from - its own directory, or its parent."""
        candidate = Path(path).expanduser()
        folder = candidate if candidate.is_dir() else candidate.parent
        return self._update(replace(self._preferences, last_folder=folder))

    def _update(self, preferences: Preferences) -> Preferences:
        """Make ``preferences`` current and try to store it, or say why it cannot."""
        self._preferences = preferences
        try:
            save_preferences(preferences, self._path)
        except OSError as error:
            # The choice still stands for this session; only the remembering failed.
            _logger.warning("could not store the preferences in %s: %s", self._path, error)
        return preferences


def _read_mapping(path: Path) -> Mapping[str, Any]:
    """The JSON object at ``path``, or nothing when there is no such object."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        loaded: Any = json.loads(text)
    except ValueError:
        _logger.warning("ignoring the unreadable preferences file %s", path)
        return {}
    if not isinstance(loaded, dict):
        _logger.warning("ignoring %s: the preferences file holds no object", path)
        return {}
    return loaded


def _language_or_default(value: Any) -> str:
    """``value`` as a language the application knows, else the source language."""
    if isinstance(value, str) and value in LANGUAGES:
        return value
    return SOURCE_LANGUAGE


def _folder_or_none(value: Any) -> Path | None:
    """``value`` as a directory that exists now, or ``None``.

    A folder that has been moved or unplugged is not a preference to repair: the
    dialog simply starts where Qt would have started it.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value).expanduser()
    return candidate if candidate.is_dir() else None


def _as_mapping(preferences: Preferences) -> dict[str, Any]:
    """The file's contents: the keys this module knows, and no others."""
    return {
        "language": preferences.language,
        "last_folder": (
            canonical_path_str(preferences.last_folder) if preferences.last_folder else None
        ),
    }
