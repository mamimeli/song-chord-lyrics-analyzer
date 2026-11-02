"""The frozen-app build script and spec (roadmap Phase K, bundling half).

Neither can be tested by building: a PyInstaller run takes minutes, needs the
optional stacks and writes gigabytes of ignored output. What is testable is the
plan -- which dynamic imports it declares, which stacks it refuses to carry,
where it puts its scratch, what it writes beside the bundle to satisfy
``docs/LICENSE_AUDIT.md`` §6, and whether the workaround for an interpreter whose
``code.replace()`` mangles module scope is applied when it is needed. Those are
the decisions a build is judged on, and each one is checkable without running a
build: the script is loaded from its file and the spec is executed against fake
PyInstaller objects.

Both are developer tooling, not package modules, so neither is importable.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build_app.py"
SPEC = ROOT / "packaging" / "songlab.spec"


def _load_build_app() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_app", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build_app = _load_build_app()


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_spec(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Execute the spec against fakes and return what it asked PyInstaller for.

    ``PyInstaller`` itself is replaced in :mod:`sys.modules`, so this works on an
    interpreter that has never seen the build tooling -- which is the interpreter
    the CI matrix and the gate run on.
    """
    calls: dict[str, Any] = {}

    def collect_data_files(package: str) -> list[tuple[str, str]]:
        return [(f"{package}/payload.txt", ".")]

    def collect_submodules(package: str) -> list[str]:
        return [f"{package}.sub", f"{package}.tests.test_{package}", f"{package}.conftest"]

    hooks = ModuleType("PyInstaller.utils.hooks")
    hooks.collect_data_files = collect_data_files  # type: ignore[attr-defined]
    hooks.collect_submodules = collect_submodules  # type: ignore[attr-defined]
    top = ModuleType("PyInstaller")
    monkeypatch.setitem(sys.modules, "PyInstaller", top)
    monkeypatch.setitem(sys.modules, "PyInstaller.utils", ModuleType("PyInstaller.utils"))
    monkeypatch.setitem(sys.modules, "PyInstaller.utils.hooks", hooks)
    for name in build_app.ANONYMIZER_MODULES:
        module = ModuleType(name)
        setattr(
            module,
            build_app.ANONYMIZER,
            lambda code_object, filename: code_object,
        )
        monkeypatch.setitem(sys.modules, name, module)
        parent, _, _child = name.rpartition(".")
        if parent not in sys.modules:
            monkeypatch.setitem(sys.modules, parent, ModuleType(parent))

    class Analysis:
        def __init__(self, scripts: list[str], **kwargs: Any) -> None:
            calls["analysis"] = {"scripts": scripts, **kwargs}
            self.pure = [
                ("librosa", "/site-packages/librosa/__init__.py", "PY_SOURCE"),
                ("numba.core.codegen", "/site-packages/numba/core/codegen.py", "PY_SOURCE"),
                ("pygments.lexers", "/site-packages/pygments/lexers.py", "PY_SOURCE"),
                ("pytest", "/site-packages/pytest/__init__.py", "PY_SOURCE"),
                ("coverage.types", "/site-packages/coverage/types.py", "PY_SOURCE"),
            ]
            self.scripts = ("entry",)
            self.binaries = ("binaries",)
            self.datas = ("datas",)

    class PYZ:
        def __init__(self, pure: Any) -> None:
            calls["pyz"] = list(pure)

    class EXE:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            calls["exe"] = {"args": args, "kwargs": kwargs}

    class COLLECT:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            calls["collect"] = {"args": args, "kwargs": kwargs}

    builders: dict[str, Any] = {"Analysis": Analysis, "PYZ": PYZ, "EXE": EXE, "COLLECT": COLLECT}
    builders.update(
        __file__=str(SPEC),
        SPECPATH=str(SPEC.parent),
        __name__="pyinstaller_spec",
    )
    exec(compile(SPEC.read_text(encoding="utf-8"), str(SPEC), "exec"), builders)
    return calls


# --------------------------------------------------------------------------- #
# What the build declares
# --------------------------------------------------------------------------- #
class TestWhatTheBuildCarries:
    def test_the_lyrics_stack_is_never_bundled(self) -> None:
        """A bundle that still needs a model download is not a product increment."""
        assert "onnx_asr" in build_app.EXCLUDED_MODULES
        assert "onnxruntime" in build_app.EXCLUDED_MODULES
        present = build_app.present_modules()
        assert "onnx_asr" not in present
        assert "onnxruntime" not in present

    def test_the_list_covers_every_dynamic_import_in_the_package(self) -> None:
        """A new ``import_module("name")`` in the package must reach this list."""
        reached = {
            match.split(".")[0]
            for path in (ROOT / "src").rglob("*.py")
            for match in re.findall(
                r'import_module\("([^"]+)"\)', path.read_text(encoding="utf-8", errors="replace")
            )
        }
        assert reached, "the package is expected to reach at least one stack by name"
        assert reached <= set(build_app.LAZY_MODULES) | {"PyQt6"}

    def test_the_spec_analyses_the_entry_point_it_names(self) -> None:
        assert build_app.ENTRY.is_file()
        assert build_app.SPEC.is_file()

    def test_the_build_command_names_the_spec_and_nothing_else(self) -> None:
        """PyInstaller ignores every flag but the paths once a spec is given."""
        command = build_app.pyinstaller_command(dist_dir=Path("dist"), work_dir=Path("work"))
        assert command[-1] == str(build_app.SPEC)
        assert command[command.index("--distpath") + 1] == "dist"
        assert command[command.index("--workpath") + 1] == "work"
        for flag in ("--hidden-import", "--collect-data", "--onedir", "--name"):
            assert not any(argument.startswith(flag) for argument in command)


# --------------------------------------------------------------------------- #
# The spec, executed against fakes
# --------------------------------------------------------------------------- #
class TestTheSpec:
    def test_it_carries_the_plan_the_script_computes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _run_spec(monkeypatch)
        analysis = calls["analysis"]
        assert analysis["scripts"] == [str(build_app.ENTRY)]
        assert set(build_app.EXCLUDED_MODULES) <= set(analysis["excludes"])
        assert set(build_app.present_modules()) <= set(analysis["hiddenimports"])

    def test_it_collects_the_declared_submodules_and_data(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _run_spec(monkeypatch)
        for package in build_app.COLLECT_SUBMODULES:
            assert f"{package}.sub" in calls["analysis"]["hiddenimports"]
        for package in build_app.COLLECT_DATA:
            assert (f"{package}/payload.txt", ".") in calls["analysis"]["datas"]

    def test_it_does_not_bundle_a_collected_packages_test_suite(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``numba.tests`` reached the bundle and brought pytest with it."""
        calls = _run_spec(monkeypatch)
        collected = calls["analysis"]["hiddenimports"]
        assert "numba.tests.test_numba" not in collected
        assert "librosa.conftest" not in collected
        assert not any(".tests." in name for name in collected)

    def test_it_keeps_the_archive_free_of_developer_tooling(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Numba imports pygments and its harness behind a guard; the bundle drops them."""
        calls = _run_spec(monkeypatch)
        names = [module[0] for module in calls["pyz"]]
        assert "librosa" in names
        assert "numba.core.codegen" in names
        assert "pygments.lexers" not in names
        assert "pytest" not in names

    def test_it_keeps_coverage_because_the_jit_imports_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``numba.core.lowering`` subclasses ``coverage.types.Tracer`` at import time."""
        calls = _run_spec(monkeypatch)
        assert "coverage.types" in [module[0] for module in calls["pyz"]]
        assert "coverage" not in build_app.DEV_ONLY_PACKAGES

    def test_it_builds_one_directory_not_one_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LGPL components must stay replaceable, so no --onefile archive."""
        calls = _run_spec(monkeypatch)
        assert calls["exe"]["kwargs"]["exclude_binaries"] is True
        assert calls["exe"]["kwargs"]["console"] is True
        assert calls["exe"]["kwargs"]["name"] == build_app.APP_NAME
        assert calls["collect"]["kwargs"]["name"] == build_app.APP_NAME


# --------------------------------------------------------------------------- #
# The interpreter whose code.replace() mangles module scope
# --------------------------------------------------------------------------- #
class TestTheScopeWorkaround:
    def test_the_probe_source_is_a_module_the_interpreter_accepts(self) -> None:
        """The probe tests the rewrite, not the snippet: plain exec must succeed."""
        exec(compile(build_app.SCOPE_PROBE, "probe.py", "exec"), {"__name__": "probe"})

    def test_the_probe_reports_what_the_interpreter_actually_does(self) -> None:
        """Its answer is the rewritten snippet's, so a fix upstream is noticed."""
        rewritten = compile(build_app.SCOPE_PROBE, "probe.py", "exec").replace(
            co_filename="anon.py"
        )
        broken = False
        try:
            exec(rewritten, {"__name__": "probe"})
        except AssertionError:
            broken = True
        assert build_app.code_replace_loses_module_scope() is broken

    def test_it_replaces_the_anonymizer_exactly_when_needed(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        calls = _run_spec(monkeypatch)
        broken = build_app.code_replace_loses_module_scope()
        for name in build_app.ANONYMIZER_MODULES:
            replaced = (
                getattr(sys.modules[name], build_app.ANONYMIZER)
                is build_app._leave_code_objects_alone
            )
            assert replaced is broken
        assert calls["analysis"]["scripts"] == [str(build_app.ENTRY)]
        if broken:
            assert "path anonymization: disabled" in capsys.readouterr().out

    def test_it_leaves_pyinstaller_alone_on_a_fixed_interpreter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(build_app, "code_replace_loses_module_scope", lambda: False)
        assert build_app.disable_unsafe_path_anonymization() == (
            "path anonymization: left as PyInstaller's default"
        )

    def test_it_refuses_to_build_a_known_broken_bundle(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If PyInstaller moved the anonymizer, the build must fail, not lie."""
        empty = ModuleType("moved_away")
        for name in build_app.ANONYMIZER_MODULES:
            monkeypatch.setitem(sys.modules, name, empty)
        monkeypatch.setattr(build_app, "code_replace_loses_module_scope", lambda: True)
        with pytest.raises(RuntimeError, match="cannot import scipy"):
            build_app.disable_unsafe_path_anonymization()


# --------------------------------------------------------------------------- #
# The notices a binary has to carry
# --------------------------------------------------------------------------- #
class _PackagePath:
    """The part of ``importlib.metadata.PackagePath`` the notices use: a name and a file."""

    def __init__(self, recorded: str, located: Path) -> None:
        self._recorded = recorded
        self._located = located

    def __str__(self) -> str:
        return self._recorded

    def locate(self) -> Path:
        return self._located


class _Wheel:
    """A distribution as ``importlib.metadata`` hands it to the build."""

    def __init__(
        self, name: str, version: str, metadata: dict[str, str], files: list[_PackagePath]
    ):
        self.name = name
        self.version = version
        self.metadata = metadata
        self.files = files


def _fake_wheel(
    root: Path, name: str, *, version: str, licence_text: str = "", **fields: str
) -> _Wheel:
    """A wheel's metadata, with its own licence file on disk when it declares one."""
    files: list[_PackagePath] = []
    if licence_text:
        recorded = f"{name}-{version}.dist-info/LICENSE"
        source = root / recorded
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(licence_text, encoding="utf-8")
        files.append(_PackagePath(recorded, source))
    metadata = {"Name": name, "Version": version, **fields}
    return _Wheel(name, version, metadata, files)


def _fake_bundle(
    monkeypatch: pytest.MonkeyPatch,
    modules: set[str],
    wheels: dict[str, _Wheel],
    *,
    mapping: dict[str, tuple[str, ...]] | None = None,
) -> None:
    """Say what is inside the bundle and where its wheels are, without building.

    ``bundled_modules`` reads an archive and ``importlib.metadata`` reads this
    machine's site-packages; both belong to the building environment, so the
    notices are tested against fakes that answer the same questions.
    """
    monkeypatch.setattr(build_app, "bundled_modules", lambda app_dir: set(modules))
    monkeypatch.setattr(
        build_app,
        "packages_distributions",
        lambda: mapping if mapping is not None else {name: (name,) for name in modules},
    )
    monkeypatch.setattr(build_app, "distribution", lambda name: wheels[name])


class TestTheThirdPartyNotices:
    def test_it_names_the_version_licence_and_notice_of_each_component(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        soundfile = _fake_wheel(
            tmp_path,
            "soundfile",
            version="0.14.0",
            licence_text="LGPL text",
            **{"License-Expression": "LGPL-2.1-or-later"},
        )
        numpy = _fake_wheel(tmp_path, "numpy", version="2.5.4", License="BSD-3-Clause")
        _fake_bundle(monkeypatch, {"soundfile", "numpy"}, {"soundfile": soundfile, "numpy": numpy})

        notices = {n["name"]: n for n in build_app.collect_notices(tmp_path)}

        assert set(notices) == {"numpy", "soundfile"}
        assert notices["soundfile"]["version"] == "0.14.0"
        assert notices["soundfile"]["license"] == "LGPL-2.1-or-later"
        assert notices["soundfile"]["notice_file"] == "notices/soundfile-LICENSE"
        assert (tmp_path / "notices" / "soundfile-LICENSE").read_text(
            encoding="utf-8"
        ) == "LGPL text"
        assert notices["numpy"]["license"] == "BSD-3-Clause"
        assert notices["numpy"]["notice_file"] == ""

    def test_a_module_that_is_not_in_the_bundle_is_not_listed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The report describes the artifact, not everything this machine has installed."""
        wheel = _fake_wheel(tmp_path, "librosa", version="1.0.0", License="MIT")
        _fake_bundle(monkeypatch, {"librosa"}, {"librosa": wheel, "onnxruntime": wheel})

        text = build_app.write_notices(tmp_path, project_license=ROOT / "LICENSE").read_text(
            encoding="utf-8"
        )

        assert "librosa 1.0.0 -- MIT" in text
        assert "onnxruntime" not in text

    def test_the_licence_field_is_read_in_preference_order(self) -> None:
        assert build_app._licence_of({"License-Expression": "MIT", "License": "other"}) == "MIT"
        assert build_app._licence_of({"License": "BSD-3-Clause"}) == "BSD-3-Clause"
        # A wheel that dumps its whole text into `License` is not naming a licence.
        whole_text = build_app._licence_of(
            {"License": "Permission is hereby granted, free of charge, to any person"}
        )
        assert whole_text == "see the licence text copied to the notices"
        assert build_app._licence_of({}) == "not stated in the wheel"

    def test_a_section_six_component_is_reported_from_the_files_that_ship(
        self, tmp_path: Path
    ) -> None:
        """A Windows scipy wheel carries OpenBLAS and no libgfortran; the notice says so."""
        for name in ("libopenblas64__.dll", "libsndfile_a440.dll", "qt6core.dll"):
            (tmp_path / name).write_text("binary", encoding="utf-8")
        by_component = {row["component"]: row for row in build_app.audited_components(tmp_path)}
        assert by_component["OpenBLAS"]["evidence"] == "libopenblas64__.dll"
        assert by_component["LAPACK"]["evidence"] == "libopenblas64__.dll"
        assert by_component["libsndfile"]["evidence"] == "libsndfile_a440.dll"
        assert by_component["Qt"]["evidence"] == "qt6core.dll"
        assert by_component["libgfortran"]["evidence"] == ""
        assert by_component["libquadmath"]["evidence"] == ""

    def test_it_says_which_audited_component_is_absent_rather_than_omitting_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _fake_bundle(monkeypatch, set(), {})
        (tmp_path / "libopenblas64__.dll").write_text("binary", encoding="utf-8")

        text = build_app.write_notices(tmp_path, project_license=ROOT / "LICENSE").read_text(
            encoding="utf-8"
        )

        assert "OpenBLAS (through scipy) -- BSD-3-Clause" in text
        assert "in this bundle: yes: libopenblas64__.dll" in text
        assert "libquadmath (through scipy) -- LGPL-2.1-or-later" in text
        assert "no file of this build matches" in text

    def test_it_names_the_project_licence_and_copies_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _fake_bundle(monkeypatch, set(), {})
        path = build_app.write_notices(tmp_path, project_license=ROOT / "LICENSE")
        assert "GPL-3.0-or-later" in path.read_text(encoding="utf-8")
        copied = (tmp_path / "LICENSE.txt").read_text(encoding="utf-8")
        assert copied == (ROOT / "LICENSE").read_text(encoding="utf-8")

    def test_ffmpeg_is_reported_as_executed_not_bundled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _fake_bundle(monkeypatch, set(), {})
        text = build_app.write_notices(tmp_path, project_license=ROOT / "LICENSE").read_text(
            encoding="utf-8"
        )
        assert "FFmpeg is not bundled" in text

    def test_an_empty_bundle_says_so_instead_of_inventing_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A bundled name that is no distribution contributes no third-party row."""
        _fake_bundle(monkeypatch, {"_distutils_hack"}, {}, mapping={})
        text = build_app.write_notices(tmp_path, project_license=ROOT / "LICENSE").read_text(
            encoding="utf-8"
        )
        assert "no third-party distribution metadata was matched" in text
        assert not (tmp_path / build_app.NOTICES_DIR).exists()


# --------------------------------------------------------------------------- #
# The executable it points at
# --------------------------------------------------------------------------- #
def test_the_executable_name_follows_the_platform(tmp_path: Path) -> None:
    expected = "songlab.exe" if sys.platform.startswith("win") else "songlab"
    assert build_app.app_executable(tmp_path).name == expected


# --------------------------------------------------------------------------- #
# The script itself, as a person runs it
# --------------------------------------------------------------------------- #
class TestTheCheckFlag:
    def test_it_prints_the_plan_without_building(self, tmp_path: Path) -> None:
        result = _run("--check", "--dist", str(tmp_path / "dist"))
        assert result.returncode in (0, 2), result.stderr
        assert "entry point:" in result.stdout
        assert "excluded:" in result.stdout and "onnx_asr" in result.stdout
        assert str(SPEC) in result.stdout or result.returncode == 2

    def test_it_says_what_is_missing_rather_than_lying(self, tmp_path: Path) -> None:
        """A machine without PyInstaller is told how to get it, exit 2."""
        result = _run("--check", "--dist", str(tmp_path / "dist"))
        if result.returncode == 2:
            assert "pip install pyinstaller" in result.stdout
        else:
            pytest.skip("PyInstaller is installed here, so the refusal path is not reachable")

    def test_it_refuses_an_unknown_flag(self) -> None:
        result = _run("--nonsense")
        assert result.returncode == 2
