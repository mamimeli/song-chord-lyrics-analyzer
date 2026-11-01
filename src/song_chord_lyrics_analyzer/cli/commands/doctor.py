"""``songlab doctor`` - report environment and dependency status.

Diagnostics come before analysis: this command tells the user which optional
tools are actually usable, which optional extras are installed and what each one
buys, which registered engines can run here, and where caches live. A packaged
build has to answer the same question (roadmap Phase K), so the extras table
below is the one place that maps an extra to the imports that stand for it.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from importlib.util import find_spec
from pathlib import Path
from typing import Any

import song_chord_lyrics_analyzer
from song_chord_lyrics_analyzer import PROJECT_NAME, __version__
from song_chord_lyrics_analyzer.audio.ffmpeg import (
    discover_ffmpeg_tools,
    ffmpeg_install_hint,
    tool_version,
)
from song_chord_lyrics_analyzer.engines import EngineKind, create_default_registry
from song_chord_lyrics_analyzer.utils.paths import (
    default_cache_dir,
    default_data_dir,
    default_export_dir,
    default_model_dir,
    default_temp_dir,
)

__all__ = [
    "OPTIONAL_EXTRAS",
    "add_arguments",
    "collect_status",
    "format_report",
    "run",
]

#: The runtime extras of the installed distribution: the import names that stand
#: for each one, and what a user loses without it. Keep in step with
#: ``[project.optional-dependencies]`` in ``pyproject.toml`` - that file decides
#: what pip installs, this table decides what doctor can say about it.
OPTIONAL_EXTRAS: dict[str, tuple[tuple[str, ...], str]] = {
    "dsp": (
        ("numpy", "librosa", "soundfile"),
        "the chord, key and tempo engines, and decoding anything that is not WAV",
    ),
    "playback": (
        ("numpy", "sounddevice"),
        "audio output for 'songlab play' and the window's transport",
    ),
    "gui": (("PyQt6",), "the desktop window ('songlab gui'), which also needs the two above"),
    "lyrics": (
        ("numpy", "librosa", "soundfile", "onnx_asr", "onnxruntime", "huggingface_hub"),
        "the 'parakeet-onnx' lyrics engine",
    ),
}


def _module_present(name: str) -> bool:
    """True when ``name`` is importable here, without importing it.

    Checking the spec instead of importing keeps ``doctor`` quick and keeps the
    core install Qt-free and DSP-free: this command reports on those stacks, it
    does not load them.
    """
    try:
        return find_spec(name) is not None
    except (ImportError, ValueError):  # a broken parent package is not installed
        return False


def _extra_status(extra: str, modules: tuple[str, ...], provides: str) -> dict[str, Any]:
    missing = [name for name in modules if not _module_present(name)]
    return {
        "installed": not missing,
        "missing": missing,
        "provides": provides,
        "pip": f'pip install "{PROJECT_NAME}[{extra}]"',
    }


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Register ``songlab doctor`` arguments."""
    parser.add_argument(
        "--json",
        action="store_true",
        help="print machine-readable JSON instead of a report",
    )


def _package_path() -> str | None:
    """Return the directory the package is loaded from (``None`` if frozen)."""
    module_file = getattr(song_chord_lyrics_analyzer, "__file__", None)
    if not module_file:
        return None
    return str(Path(module_file).parent)


def _tool_status(name: str, path: Any) -> dict[str, Any]:
    if path is None:
        return {"name": name, "found": False, "path": None, "version": None}
    return {"name": name, "found": True, "path": str(path), "version": tool_version(path)}


def collect_status() -> dict[str, Any]:
    """Collect environment, dependency and registry status."""
    tools = discover_ffmpeg_tools()
    registry = create_default_registry()

    engines: dict[str, list[dict[str, Any]]] = {}
    for kind in EngineKind:
        names = registry.names(kind)
        if not names:
            continue
        available = set(registry.available(kind))
        engines[kind.value] = [{"name": name, "available": name in available} for name in names]

    return {
        "application": {
            "name": "song-chord-lyrics-analyzer",
            "version": __version__,
            "cli": "songlab",
            "package_path": _package_path(),
        },
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "tools": {
            "ffmpeg": _tool_status("ffmpeg", tools.ffmpeg),
            "ffprobe": _tool_status("ffprobe", tools.ffprobe),
        },
        "extras": {
            extra: _extra_status(extra, modules, provides)
            for extra, (modules, provides) in OPTIONAL_EXTRAS.items()
        },
        "directories": {
            "cache": str(default_cache_dir()),
            "data": str(default_data_dir()),
            "models": str(default_model_dir()),
            "exports": str(default_export_dir()),
            "temp": str(default_temp_dir()),
        },
        "engines": engines,
    }


def format_report(status: dict[str, Any]) -> str:
    """Render the collected status as a readable report."""
    application = status["application"]
    lines = [
        "SongLab doctor",
        "==============",
        f"Application:  {application['name']} {application['version']}",
        f"Package path: {application['package_path']}",
        f"Python:       {status['python']['version']} ({status['python']['implementation']})",
        f"Interpreter:  {status['python']['executable']}",
        f"Platform:     {status['platform']['system']} {status['platform']['release']} "
        f"({status['platform']['machine']})",
        "",
        "External tools",
    ]

    for name in ("ffmpeg", "ffprobe"):
        tool = status["tools"][name]
        if tool["found"]:
            lines.append(f"  {name:<8} ok      {tool['path']}")
            if tool["version"]:
                lines.append(f"           {tool['version']}")
        else:
            lines.append(f"  {name:<8} missing")

    if not all(status["tools"][name]["found"] for name in ("ffmpeg", "ffprobe")):
        lines.append("")
        lines.extend(f"  {line}" for line in ffmpeg_install_hint().splitlines())

    lines.append("")
    lines.append("Optional extras")
    for extra, info in status["extras"].items():
        state = "ok" if info["installed"] else "missing"
        lines.append(f"  {extra:<9} {state:<8} {info['provides']}")
        if not info["installed"]:
            lines.append(f"            not importable: {', '.join(info['missing'])}")
            lines.append(f"            {info['pip']}")

    lines.append("")
    lines.append("Directories")
    for label in ("cache", "data", "models", "exports", "temp"):
        lines.append(f"  {label:<8} {status['directories'][label]}")

    lines.append("")
    lines.append("Analysis engines")
    if status["engines"]:
        for kind, engines in sorted(status["engines"].items()):
            for engine in engines:
                state = "ok" if engine["available"] else "unavailable here"
                lines.append(f"  {kind:<8} {engine['name']:<18} {state}")
    else:
        lines.append("  none registered yet (engines are added in later roadmap phases)")

    return "\n".join(lines)


def run(args: argparse.Namespace) -> int:
    """Execute ``songlab doctor``."""
    status = collect_status()
    if args.json:
        print(json.dumps(status, indent=2, ensure_ascii=False))
    else:
        print(format_report(status))
    return 0
