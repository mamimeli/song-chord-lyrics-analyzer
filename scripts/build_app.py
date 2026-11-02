#!/usr/bin/env python3
"""Build a frozen ``songlab`` application for this platform.

Developer tooling, not a shipped command: it lives in ``scripts/``, is never
imported by the package, and its output (``dist/``, ``.cache/build/``) is
gitignored. The build itself is
``packaging/songlab.spec``: this script decides *what* goes in, the spec says
*how* the bundle is assembled. It exists because roadmap Phase K's bundling half
asks for a build a user can run without Python, and because a frozen build is
where three documented assumptions get tested at once:

* the runtime directories: :mod:`song_chord_lyrics_analyzer.utils.paths` derives
  cache/data/temp from ``SONGLAB_*`` and the OS environment, never from the
  executable's own location, so a frozen app must still find a writable place;
* the optional stacks: every engine reaches numpy, librosa, sounddevice,
  onnx_asr or onnxruntime through ``importlib.import_module(name)`` -- a *string
  name*, which PyInstaller's static analysis cannot see. What is importable in
  the building interpreter is declared as a hidden import, so the bundle carries
  exactly the extras this machine has and ``songlab doctor`` inside the bundle
  reports the rest honestly;
* the notices: ``docs/LICENSE_AUDIT.md`` §6 lists what must travel with a binary
  (OpenBLAS/LAPACK inside scipy, libsndfile inside soundfile, the Qt build under
  PyQt6). This script writes them from the metadata **actually inside the
  bundle** rather than from a hand-kept list, and it builds one directory rather
  than one file so those LGPL libraries stay replaceable.

Usage::

    # what would be bundled, and the exact command, without building
    python scripts/build_app.py --check

    # build into dist/ and run the product path from the executable
    python scripts/build_app.py

    # build only (a machine without the sample's decoder, or a first try)
    python scripts/build_app.py --no-verify

Exit codes: ``0`` built (and verified, unless ``--no-verify``), ``1`` the build
or the verification failed, ``2`` a bad request.
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
import sys
from email.message import Message
from importlib.metadata import (
    Distribution,
    PackageNotFoundError,
    distribution,
    packages_distributions,
)
from importlib.util import find_spec
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRY = ROOT / "packaging" / "songlab_entry.py"
SPEC = ROOT / "packaging" / "songlab.spec"
DEFAULT_DIST = ROOT / "dist"
DEFAULT_WORK = ROOT / ".cache" / "build"
APP_NAME = "songlab"

#: Modules the package imports by name at runtime. PyInstaller follows every
#: ``import`` *statement* it can see -- including the ones inside functions -- so
#: PyQt6 and the ``gui/`` package need no help; these names do, because they are
#: string arguments to ``importlib.import_module``.
#: ``song_chord_lyrics_analyzer.audio.decode._import_dsp`` and the four engines
#: are what keeps this list honest; update it when a new lazy import lands.
LAZY_MODULES = ("numpy", "librosa", "soundfile", "sounddevice", "onnx_asr", "onnxruntime")

#: Not bundled in this build: the lyrics stack's engine only works after
#: ``onnx-asr`` downloads the Parakeet weights, so a bundle carrying it would
#: still need a network fetch before a user could transcribe anything. Excluded
#: explicitly, which is also what makes ``songlab doctor`` inside the bundle
#: report ``lyrics`` missing -- the build says what it is.
EXCLUDED_MODULES = ("onnx_asr", "onnxruntime", "huggingface_hub")

#: Packages whose submodules are only ever reached through a registry or a
#: plugin search, so static analysis misses them even when the parent is found.
COLLECT_SUBMODULES = ("librosa", "numba")

#: Developer tooling that a collected package imports behind a
#: ``try: import X except ImportError`` fallback -- numba highlights LLVM dumps
#: with ``pygments`` and reaches ``pytest`` only through its own test harness.
#: PyInstaller's ``excludes`` cannot drop these (excluding a parent does not
#: exclude its submodules), so the spec removes these trees from the module list
#: before the archive is written; where numba does reach one, it takes the
#: fallback it was written to take.
#:
#: ``coverage`` is deliberately absent from this list. ``numba/core/lowering.py``
#: imports ``numba.misc.coverage_support`` on every compile, and that module's
#: ``try: import coverage`` is followed by an *unguarded*
#: ``class NumbaTracer(coverage.types.Tracer)`` -- measured 2026-11-01, a bundle
#: without coverage dies in the chord pass with
#: ``module 'coverage' has no attribute 'types'``. A tracer the JIT needs at
#: import time is not dev-only, however dev-only it looks.
DEV_ONLY_PACKAGES = ("pygments", "pytest", "pluggy", "iniconfig")

#: Data files a frozen build needs: scipy's and librosa's own non-Python
#: payloads.
COLLECT_DATA = ("librosa", "scipy", "sklearn")

#: Commands the verification runs, in order, with the sample the repository
#: commits. A frozen app that starts but cannot analyse is not a product.
VERIFY_SAMPLE = ROOT / "samples" / "vocadito_2.wav"

#: Where PyInstaller hides the build machine's paths: it rebuilds every collected
#: code object through this attribute, in these two modules.
ANONYMIZER = "replace_filename_in_code_object"
ANONYMIZER_MODULES = ("PyInstaller.building.utils", "PyInstaller.archive.writers")

#: A module whose comprehension target is also a global name -- the shape that an
#: unpatched CPython 3.12 ``code.replace()`` gets wrong.
SCOPE_PROBE = "obj = 0\nobj = [obj for obj in range(1)]\nassert 'obj' in dir()\n"


def code_replace_loses_module_scope() -> bool:
    """Whether this interpreter rewrites a module code object into the wrong scope.

    ``code.replace()`` in CPython 3.12.0 drops the local-slot kinds, so a module
    frame that inlines a comprehension (PEP 709) stops reporting its globals
    through ``dir()``. PyInstaller rebuilds every bundled module with that call,
    and the frozen copy of ``scipy.stats._distn_infrastructure`` -- which cleans
    up its docstrings with exactly this pattern and then says ``del obj`` -- dies
    at import with ``NameError: name 'obj' is not defined``. CPython 3.12.1 fixed
    ``code.replace()`` (gh-110543, reported against PyInstaller issue #7992), so
    probe the interpreter instead of version-testing it.
    """
    rewritten = compile(SCOPE_PROBE, "songlab-scope-probe.py", "exec").replace(
        co_filename="songlab-scope-probe.py"
    )
    try:
        exec(rewritten, {"__name__": "songlab_scope_probe"})
    except AssertionError:
        return True
    return False


def _leave_code_objects_alone(code_object, _filename):
    """The stand-in for PyInstaller's anonymizer: hand back what it was given."""
    return code_object


def disable_unsafe_path_anonymization() -> str:
    """Stop PyInstaller rewriting ``co_filename`` when rewriting breaks scoping.

    Called from the spec, so it runs in the process that writes the archive. The
    cost is that a traceback out of the frozen app names paths on this build
    machine; the alternative is a bundle that cannot import scipy.

    Returns:
        One line saying what was done, for the build log.
    """
    if not code_replace_loses_module_scope():
        return "path anonymization: left as PyInstaller's default"
    patched = []
    for name in ANONYMIZER_MODULES:
        try:
            module = importlib.import_module(name)
        except ImportError:
            continue
        if hasattr(module, ANONYMIZER):
            setattr(module, ANONYMIZER, _leave_code_objects_alone)
            patched.append(name)
    if not patched:
        raise RuntimeError(
            "this interpreter's code.replace() breaks module scoping, but "
            f"PyInstaller's path anonymizer ({ANONYMIZER}) is not in "
            f"{', '.join(ANONYMIZER_MODULES)}: the build would produce an app that "
            "cannot import scipy. Build with CPython 3.12.1 or newer, or update "
            "the workaround to wherever PyInstaller moved that call."
        )
    return (
        f"path anonymization: disabled ({', '.join(patched)}) -- this interpreter's "
        "code.replace() breaks comprehension scoping, so the bundle keeps build paths "
        "instead of a scipy that cannot import"
    )


def present_modules() -> tuple[str, ...]:
    """Which of :data:`LAZY_MODULES` this build should carry.

    A module named in :data:`EXCLUDED_MODULES` is never bundled, whatever the
    interpreter has. ``find_spec`` is used rather than an import, so the build
    plan is decided without loading a DSP stack into the process that runs
    PyInstaller.
    """
    present: list[str] = []
    for name in LAZY_MODULES:
        if name in EXCLUDED_MODULES:
            continue
        try:
            if find_spec(name) is not None:
                present.append(name)
        except (ImportError, ValueError):  # a broken parent package is not installed
            continue
    return tuple(present)


def is_test_module(name: str) -> bool:
    """Whether a collected submodule is a package's own test suite.

    ``numba`` is the reason this exists: ``collect_submodules`` brought its whole
    test suite, and those modules import pytest, coverage and pygments -- so a
    product bundle carried a test runner. Nothing at runtime reaches them.
    """
    return bool({"tests", "test", "conftest"} & set(name.lower().split(".")))


def is_dev_only(name: str) -> bool:
    """Whether a collected module belongs to :data:`DEV_ONLY_PACKAGES`."""
    return name.split(".")[0] in DEV_ONLY_PACKAGES


def pyinstaller_command(
    *,
    python: str | Path = sys.executable,
    dist_dir: Path,
    work_dir: Path,
) -> list[str]:
    """The PyInstaller invocation for this build, as one honest list.

    Only the paths travel as flags: PyInstaller ignores every other command-line
    option when a spec file is given, so the plan lives in
    ``packaging/songlab.spec`` -- which reads it back from this module, so there
    is still one place that decides what a bundle contains.
    """
    return [
        str(python),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        str(SPEC),
    ]


def app_executable(app_dir: Path, *, name: str = APP_NAME) -> Path:
    """The executable inside a one-directory bundle."""
    suffix = ".exe" if sys.platform.startswith("win") else ""
    return app_dir / f"{name}{suffix}"


#: docs/LICENSE_AUDIT.md section 6 records what the wheels carry *inside* them and
#: the licence the audit gives each. The markers are file-name fragments that show
#: the component really is in this artifact: the notice is only owed for what
#: actually ships, so a component with no matching file is reported as absent.
AUDITED_COMPONENTS = (
    (
        "OpenBLAS",
        "scipy",
        ("openblas",),
        "BSD-3-Clause",
        "scipy's own licence text names the libraries its wheel bundles.",
    ),
    (
        "LAPACK",
        "scipy",
        ("lapack", "openblas"),
        "BSD-3-Clause-Open-MPI",
        "LAPACK ships inside the OpenBLAS library of the same name.",
    ),
    (
        "libgfortran",
        "scipy",
        ("gfortran",),
        "GPL-3.0-or-later WITH GCC-exception-3.1",
        "covered by the GCC Runtime Library Exception; the notice may not be stripped.",
    ),
    (
        "libquadmath",
        "scipy",
        ("quadmath",),
        "LGPL-2.1-or-later",
        "the library stays replaceable because this build is a directory.",
    ),
    (
        "libsndfile",
        "soundfile",
        ("sndfile",),
        "LGPL",
        "_soundfile_data/COPYING is the licence text, already inside the bundle.",
    ),
    (
        "Qt",
        "PyQt6",
        ("qt6core", "qt6gui", "qt6widgets"),
        "LGPL",
        "the Qt libraries arrive through their own wheel (PyQt6-Qt6, whose metadata "
        "reads 'LGPL v3'); PyQt6 itself is GPL-3.0-only or commercial.",
    ),
)

NOTICES_DIR = "notices"


def bundled_modules(app_dir: Path) -> set[str]:
    """Every top-level import name inside the bundle.

    Read out of the archive the build just wrote rather than from what the build
    was asked to carry: this is the one list that cannot flatter the artifact, and
    the notices below are written from it.
    """
    from PyInstaller.archive.readers import CArchiveReader  # build-time only

    pyz = CArchiveReader(app_executable(app_dir)).open_embedded_archive("PYZ.pyz")
    return {str(name).split(".")[0] for name in pyz.toc}


def _licence_of(metadata: Message) -> str:
    """The licence a wheel declares, in the words the wheel itself uses."""
    expression = metadata.get("License-Expression")
    if expression:
        return expression.strip()
    declared = metadata.get("License") or ""
    if not declared:
        return "not stated in the wheel"
    first = declared.splitlines()[0].strip()
    # A wheel that puts the whole licence text in this field is not naming a
    # licence, so point at the text instead of quoting its first line.
    return first if len(first) <= 40 else "see the licence text copied to the notices"


def _copy_licence_text(dist: Distribution, app_dir: Path) -> str:
    """Copy the wheel's own licence file into ``notices/`` and return its name.

    Nothing is written from memory: the text either ships in the wheel, in which
    case it travels with the bundle unchanged, or the wheel ships none and the
    record carries only the licence its metadata named.
    """
    target = None
    for path in dist.files or ():
        location = str(path).replace("\\", "/")
        if ".dist-info" not in location:
            continue
        name = location.split("/")[-1]
        if not name.upper().startswith(("LICENSE", "COPYING")):
            continue
        source = path.locate()
        if source.is_file():
            target = (source, name)
            break
    if target is None:
        return ""
    notices = app_dir / NOTICES_DIR
    notices.mkdir(parents=True, exist_ok=True)
    copied = notices / f"{dist.name}-{target[1]}"
    shutil.copyfile(target[0], copied)
    return f"{NOTICES_DIR}/{copied.name}"


def collect_notices(app_dir: Path) -> list[dict[str, str]]:
    """One record per distribution inside the bundle: version, licence, notice file.

    The bundle's import names are matched to distributions through the *building*
    environment's metadata, because that is where a wheel's licence text lives. A
    name that belongs to the standard library, to this project, or to no
    distribution at all contributes no third-party record.
    """
    names = bundled_modules(app_dir)
    mapping = packages_distributions()
    third_party = sorted({found for name in names for found in mapping.get(name, ())})
    records: list[dict[str, str]] = []
    for distribution_name in third_party:
        try:
            dist = distribution(distribution_name)
        except PackageNotFoundError:
            continue
        records.append(
            {
                "name": distribution_name,
                "version": dist.version,
                "license": _licence_of(dist.metadata),
                "notice_file": _copy_licence_text(dist, app_dir),
            }
        )
    return records


def audited_components(app_dir: Path) -> list[dict[str, str]]:
    """Whether each section 6 component is in this bundle, by file-name evidence.

    The rows describe the artifact a user receives, which is why the answer is a
    search of ``app_dir`` and not a copy of the audit table: a Windows scipy wheel
    carries OpenBLAS and no libgfortran, and the notice has to say so.
    """
    file_names = [path.name.lower() for path in app_dir.rglob("*") if path.is_file()]
    rows: list[dict[str, str]] = []
    for component, wheel, markers, license_text, note in AUDITED_COMPONENTS:
        evidence = sorted({name for name in file_names if any(m in name for m in markers)})
        rows.append(
            {
                "component": component,
                "wheel": wheel,
                "license": license_text,
                "evidence": evidence[0] if evidence else "",
                "note": note,
            }
        )
    return rows


def write_notices(app_dir: Path, *, project_license: Path) -> Path:
    """Write ``THIRD_PARTY_NOTICES.txt`` and the licence texts beside the bundle.

    The point is the section 6 obligation: a binary that carries libsndfile, the Qt
    build or scipy's OpenBLAS has to carry their notices too. Both halves come from
    the artifact -- the component list from the archive the build wrote, the licence
    text from the wheels it collected -- so the file cannot claim a notice for a
    library that is not in the build, and cannot hide one that is.
    """
    notices = collect_notices(app_dir)
    lines = [
        "Third-party notices for the songlab frozen application",
        "=" * 56,
        "",
        "This application is distributed under the GNU General Public License",
        "version 3 or later (GPL-3.0-or-later). The licence text is in LICENSE.txt",
        "next to this file.",
        "",
        "The component list is read out of the archive this build wrote, so it",
        "names what is in this directory rather than what the build was asked for.",
        "Licence texts are copied from the wheels into the notices/ directory",
        "unchanged; a nested tree of notices (numpy) is stated inside its own",
        "top-level licence file.",
        "",
        "Components bundled inside wheels (docs/LICENSE_AUDIT.md section 6)",
        "-" * 58,
    ]
    for row in audited_components(app_dir):
        found = f"yes: {row['evidence']}" if row["evidence"] else "no file of this build matches"
        lines.append(f"{row['component']} (through {row['wheel']}) -- {row['license']}")
        lines.append(f"    in this bundle: {found}")
        lines.append(f"    {row['note']}")
    lines += [
        "",
        "Distributions inside this bundle",
        "-" * 58,
    ]
    for notice in notices:
        where = f" -- {notice['notice_file']}" if notice["notice_file"] else ""
        lines.append(f"{notice['name']} {notice['version']} -- {notice['license']}{where}")
    if not notices:
        lines.append("no third-party distribution metadata was matched in the bundle")
    lines += [
        "",
        "FFmpeg is not bundled: the application locates and executes an installed",
        "ffmpeg/ffprobe when one is present (docs/LICENSE_AUDIT.md section 5).",
        "This build is a directory, not a single self-extracting file, so the",
        "shared libraries below it can be replaced by the user -- the condition",
        "the LGPL notices of libsndfile and Qt depend on.",
        "",
    ]
    target = app_dir / "THIRD_PARTY_NOTICES.txt"
    target.write_text("\n".join(lines), encoding="utf-8")
    if project_license.is_file():
        shutil.copyfile(project_license, app_dir / "LICENSE.txt")
    return target


def _run_app(
    executable: Path, arguments: list[str], *, timeout: float
) -> subprocess.CompletedProcess[str]:
    """Run the frozen app with UTF-8 output, so a box-drawing glyph cannot crash it."""
    return subprocess.run(
        [str(executable), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _verify_window(executable: Path, sample: Path, *, seconds: float = 20.0) -> str:
    """Start the frozen window offscreen and report whether it stayed up.

    A bundle missing its Qt platform plugin exits inside a second with a message
    on stderr; a window that constructed is still running when the clock expires.
    That is the whole of what this checks -- the frozen window is not clicked
    through here, and a build without PyQt6 skips it rather than failing.
    """
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    with subprocess.Popen(
        [str(executable), "gui", str(sample)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    ) as process:
        try:
            _, stderr = process.communicate(timeout=seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return f"window: ok (opened offscreen and ran {seconds:.0f} s before closing)"
        raise RuntimeError(f"the frozen window exited with {process.returncode}.\n{stderr}")


def verify(app_dir: Path, *, sample: Path = VERIFY_SAMPLE, timeout: float = 180.0) -> list[str]:
    """Run the product path from the executable and report what happened.

    Raises:
        RuntimeError: When the executable is missing or a step fails; the
            message carries the captured stderr, because a frozen failure is
            otherwise invisible.
    """
    executable = app_executable(app_dir)
    if not executable.is_file():
        raise RuntimeError(f"{executable} was not produced by the build.")
    steps: list[str] = []
    commands: list[tuple[str, list[str]]] = [
        ("version", ["--version"]),
        ("doctor", ["doctor"]),
    ]
    if sample.is_file():
        commands.append(("info", ["info", str(sample)]))
        commands.append(("chords", ["chords", str(sample), "--json"]))
    for label, arguments in commands:
        result = _run_app(executable, arguments, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(
                f"'songlab {' '.join(arguments)}' exited {result.returncode}.\n{result.stderr}"
            )
        steps.append(f"{label}: ok ({len(result.stdout.splitlines())} lines out)")
    if find_spec("PyQt6") is not None and sample.is_file():
        steps.append(_verify_window(executable, sample))
    else:
        steps.append("window: skipped (this interpreter has no PyQt6 to bundle)")
    return steps


def _describe(modules: tuple[str, ...], *, dist: Path, work: Path) -> int:
    """Print what a build here would carry, and the command that would do it."""
    print(f"interpreter: {sys.executable}")
    print(f"build definition: {SPEC}")
    print(f"entry point: {ENTRY}")
    if modules:
        print(f"dynamic stacks bundled: {', '.join(modules)}")
    else:
        print("dynamic stacks bundled: none (core-only build: info, doctor, export)")
    print(f"excluded: {', '.join(EXCLUDED_MODULES)}")
    print(f"dev-only trees dropped: {', '.join(DEV_ONLY_PACKAGES)}")
    print(f"submodules collected: {', '.join(COLLECT_SUBMODULES)}")
    print(f"data collected: {', '.join(COLLECT_DATA)}")
    if code_replace_loses_module_scope():
        print("path anonymization: off (this interpreter's code.replace() breaks scoping)")
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is not installed in this interpreter: pip install pyinstaller")
        return 2
    command = pyinstaller_command(dist_dir=dist, work_dir=work)
    print("\ncommand:\n  " + " ".join(command))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Build, or describe, the frozen application."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dist", type=Path, default=DEFAULT_DIST, metavar="DIR", help="where dist/songlab lands"
    )
    parser.add_argument(
        "--work", type=Path, default=DEFAULT_WORK, metavar="DIR", help="build scratch directory"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="print what would be bundled and the command, then exit",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="build without running the product path from the executable",
    )
    args = parser.parse_args(argv)

    modules = present_modules()
    if args.check:
        return _describe(modules, dist=args.dist, work=args.work)

    command = pyinstaller_command(dist_dir=args.dist, work_dir=args.work)
    print("building (this copies the DSP stack; it takes minutes, not seconds)...")
    built = subprocess.run(command, cwd=ROOT, check=False)
    if built.returncode != 0:
        print(f"error: PyInstaller exited {built.returncode}", file=sys.stderr)
        return 1

    app_dir: Path = args.dist / APP_NAME
    notices = write_notices(app_dir, project_license=ROOT / "LICENSE")
    print(f"notices: {notices}")

    if args.no_verify:
        print(f"built {app_dir} (not verified)")
        return 0
    try:
        steps = verify(app_dir)
    except (RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"error: the frozen app failed: {error}", file=sys.stderr)
        return 1
    print(f"verified {app_executable(app_dir)}")
    for step in steps:
        print(f"  {step}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
