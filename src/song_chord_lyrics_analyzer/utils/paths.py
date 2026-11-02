"""Cross-platform path helpers (roadmap sections 4 and 104-105).

Nothing in the project may hard-code ``/tmp``, ``/home/user`` or
``C:\\Users\\...``. All platform-specific locations are resolved here.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

__all__ = [
    "canonical_path_str",
    "default_cache_dir",
    "default_data_dir",
    "default_export_dir",
    "default_model_dir",
    "default_temp_dir",
    "ensure_directory",
    "is_windows",
    "is_macos",
    "is_linux",
    "resolve_output_path",
    "write_text_atomic",
]

CACHE_ENV_VAR = "SONGLAB_CACHE_DIR"
DATA_ENV_VAR = "SONGLAB_DATA_DIR"
TEMP_ENV_VAR = "SONGLAB_TEMP_DIR"

_APP_DIR_NAME = "songlab"


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name)
    if not raw:
        return None
    return Path(raw).expanduser()


def _platform_cache_dir() -> Path:
    if is_windows():
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / _APP_DIR_NAME / "Cache"
        return Path.home() / "AppData" / "Local" / _APP_DIR_NAME / "Cache"
    if is_macos():
        return Path.home() / "Library" / "Caches" / _APP_DIR_NAME
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    return root / _APP_DIR_NAME


def _platform_data_dir() -> Path:
    if is_windows():
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / _APP_DIR_NAME
        return Path.home() / "AppData" / "Roaming" / _APP_DIR_NAME
    if is_macos():
        return Path.home() / "Library" / "Application Support" / _APP_DIR_NAME
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / _APP_DIR_NAME


def default_cache_dir() -> Path:
    """Return the cache directory, honouring ``SONGLAB_CACHE_DIR``."""
    override = _env_path(CACHE_ENV_VAR)
    return override if override is not None else _platform_cache_dir()


def default_data_dir() -> Path:
    """Return the application data directory, honouring ``SONGLAB_DATA_DIR``."""
    override = _env_path(DATA_ENV_VAR)
    return override if override is not None else _platform_data_dir()


def default_model_dir() -> Path:
    """Return the directory reserved for downloaded models.

    Model weights are fetched by the libraries that use them - the lyrics engine
    goes through ``huggingface_hub`` and its own cache - so this path is what
    ``songlab doctor`` reports rather than where those files actually land.
    """
    return default_data_dir() / "models"


def default_export_dir() -> Path:
    """Return the directory used when no explicit output directory is given."""
    return default_data_dir() / "exports"


def default_temp_dir() -> Path:
    """Return a writable temporary directory for the current platform.

    ``SONGLAB_TEMP_DIR`` overrides the system temporary directory.
    """
    override = _env_path(TEMP_ENV_VAR)
    if override is not None:
        return override
    return Path(tempfile.gettempdir())


def ensure_directory(path: Path) -> Path:
    """Create ``path`` (and parents) if needed and return it."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def canonical_path_str(path: str | Path) -> str:
    """Render ``path`` for a document that other machines must read.

    ``str(Path)`` is host-specific: on Windows it writes ``C:\\music\\a.wav``
    into JSON that is meant to be portable and diffable. Forward slashes are
    readable by ``Path()`` on every target platform, so every path that leaves
    the application inside a canonical document or a sidecar goes through here.
    """
    return Path(path).as_posix()


def resolve_output_path(path: str | Path, *, base_dir: Path | None = None) -> Path:
    """Resolve an output path without ever targeting an input file implicitly.

    Relative paths are resolved against ``base_dir`` (default: current working
    directory) so exports land where the user expects them.
    """
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = (base_dir or Path.cwd()) / candidate
    return candidate


def write_text_atomic(path: str | Path, text: str, *, encoding: str = "utf-8") -> Path:
    """Write ``text`` to ``path`` so an interruption cannot leave it half-written.

    ``Path.write_text`` truncates the target first, so a full disk, text the
    encoding cannot hold or a ``Ctrl+C`` at the wrong moment leaves the user with
    a partial file where a complete one was - and a JSON document cut in half
    reads as if it never existed. This writes beside the target and renames over
    it, so the swap is one step: a reader sees the old file or the new one.

    The temporary is created in the target's own directory on purpose: a rename
    inside one directory is atomic, while one that crosses devices is a copy
    with the same half-written window this exists to close. Durability across a
    power cut is a different promise and needs a directory flush this does not
    make.

    Args:
        path: The file to write. Its directory must already exist.
        text: The whole content, as one string.
        encoding: Written as UTF-8 by default; line endings follow the platform
            default, exactly as :meth:`pathlib.Path.write_text` did.

    Returns:
        The path written, so the caller can report it.

    Raises:
        OSError: The directory is missing, the write failed or the rename was
            refused. The previous content of ``path`` is untouched in every
            case, and the temporary is removed.
    """
    target = Path(path)
    descriptor, staging_name = tempfile.mkstemp(dir=str(target.parent), prefix=".part-")
    staging = Path(staging_name)
    try:
        with os.fdopen(descriptor, "w", encoding=encoding) as handle:
            handle.write(text)
        os.replace(staging_name, str(target))
    except BaseException:
        # A stopped run is exactly the interruption being defended against, and
        # it arrives as an exception here rather than as a signal to the writer.
        staging.unlink(missing_ok=True)
        raise
    return target
