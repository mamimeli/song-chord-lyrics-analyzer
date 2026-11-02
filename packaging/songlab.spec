"""PyInstaller build definition for the frozen ``songlab`` application.

Executed by a build and never imported by the package: ``scripts/build_app.py``
runs ``python -m PyInstaller packaging/songlab.spec`` and owns the decisions --
which optional stacks to carry, which to refuse, what the bundle then has to
prove to be called verified. This file owns the two things only a spec can own:
the shape of the bundle, and the build-time workaround that has to run inside
the PyInstaller process while it writes the archive.

``docs/DEVELOPMENT.md`` section 10 is the how-to and what a build claims;
``docs/LICENSE_AUDIT.md`` section 6 is why this is a directory, not one file.
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# PyInstaller defines SPECPATH as the directory that holds this file.
REPOSITORY = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(REPOSITORY / "scripts"))

import build_app  # noqa: E402

# A code object PyInstaller rebuilds to hide build paths can come out of
# `code.replace()` with the wrong scope on an unpatched CPython 3.12. This is
# that patch, applied or not by probe rather than by version test.
print(build_app.disable_unsafe_path_anonymization())

analysis = Analysis(
    [str(build_app.ENTRY)],
    pathex=[],
    binaries=[],
    datas=[file for package in build_app.COLLECT_DATA for file in collect_data_files(package)],
    hiddenimports=[
        *build_app.present_modules(),
        *(
            name
            for package in build_app.COLLECT_SUBMODULES
            for name in collect_submodules(package)
            if not build_app.is_test_module(name)
        ),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=list(build_app.EXCLUDED_MODULES),
    noarchive=False,
)
# Numba reaches pygments and its own test harness through guarded imports, so
# dropping those trees keeps a syntax highlighter and a test runner out of a
# product bundle; the guarded import then takes the fallback numba was written to
# take. coverage is not one of them -- numba's lowering path subclasses it at
# import time, so a bundle without it cannot compile.
pyz = PYZ([module for module in analysis.pure if not build_app.is_dev_only(str(module[0]))])

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name=build_app.APP_NAME,
    debug=False,
    strip=False,
    upx=False,
    console=True,
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name=build_app.APP_NAME,
)
