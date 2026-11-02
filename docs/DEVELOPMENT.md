# Development

## 1. Requirements

* Python 3.10 or newer (CI tests 3.10, 3.11, 3.12 and 3.13)
* `venv` + `pip` — Conda, Poetry and Pipenv are intentionally not required
* Optional: FFmpeg (`ffmpeg` + `ffprobe`) for anything that is not a WAV file

## 2. Setup

Linux / macOS:

```bash
git clone <repository>
cd song-chord-lyrics-analyzer

python -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev,gui]"
```

On a Debian or Ubuntu (`.deb`) system install `python3-venv` before the `venv`
line — those distributions ship `python3` without that module, so
`python -m venv` fails until `sudo apt install python3-venv` has run. On Fedora,
Arch, openSUSE and Alpine the equivalent package has a different name and the
commands above are unchanged; the README "Installation" section spells out which
lines are `.deb`-specific.

Windows (PowerShell):

```powershell
git clone <repository>
cd song-chord-lyrics-analyzer

python -m venv .venv
.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev,gui]"
```

The core package has **no** required dependencies. Analysis engines are opt-in
extras that are added phase by phase, with their licence and platform support
recorded in `docs/DEPENDENCY_MATRIX.md` first. The gate environment needs the
development tools and the window stubs (`.[dev,gui]`). The full local suite adds
the DSP and playback stacks:

```bash
python -m pip install -e ".[dev,dsp,playback,gui]"
```

`gui` (PyQt6) is required for the mypy gate and the window tests; `.[dev]` alone
cannot type-check `gui/`. `dsp` (numpy/librosa/soundfile) runs the real engines;
`playback` (sounddevice) runs the real player; `build` (PyInstaller) only builds
the frozen application of section 10 and is never imported by the package, the
tests or the gate. The window's tests drive it on the offscreen platform plugin
(`QT_QPA_PLATFORM=offscreen`, set by the `qt_app` fixture), so no display or sound
card is required. The installed package itself stays Qt-free and the core test
matrix runs without it.

## 3. Everyday commands

```bash
python scripts/check.py      # the four-command gate with this interpreter
python scripts/check.py --quick       # ruff + mypy only
python scripts/check.py --tests-only  # pytest only

pytest                       # full suite
pytest -q -m "not integration"   # skip tests that need FFmpeg
pytest -m integration        # only the FFmpeg integration tests
ruff check .                 # lint
ruff format --check .        # formatting (markdown is excluded on purpose)
python -m mypy               # type check
songlab --help               # CLI smoke check
songlab doctor               # environment report
songlab info samples/example.wav
```

`scripts/check.py` uses `sys.executable`, so activating the environment is what
selects the tools; on headless Linux it sets `QT_QPA_PLATFORM=offscreen`. There
is no required environment name: `.venv` is the convention, and the author's
`.venv-chords` is not part of a fresh clone.

Two measurement scripts sit beside the gate. `scripts/chord_benchmark.py`
reproduces the chord accuracy figures, and
`scripts/analysis_cost_probe.py` reproduces the timing figures of
[`ENGINE_COMPARISON.md`](ENGINE_COMPARISON.md) §10 — where an analysis spends
its time, decode by decode (`--make-fixture` builds the generated-audio input,
`--json` writes the record into the gitignored `.cache/`; a machine-readable
result is never committed).

Every `chord_benchmark.py` run is also an accuracy check. The committed vectors
in `benchmark/reference/` pin the metrics of one measured run on one fixed
evaluation set, and the harness compares its own aggregate against the vector
named by `--vector` (default
`benchmark/reference/chroma_baseline-instructed.json`): it prints one row per
tracked metric with `improved` / `regressed` / `unchanged` and exits **3** on a
regression. A run that did not score that set — a `--limit` subset, another
corpus, the `performed` annotation — prints why it was skipped instead of
comparing a number from a different corpus. Use `--no-check-vector` to measure
without tracking, and `--write-vector PATH` to adopt a run as a new vector
(`--overwrite-vector` to replace one); a vector written that way carries the
run's own figures, its environment and the digest of the manifest it scored, so
it cannot describe a corpus that was not measured. The comparison itself lives
in `song_chord_lyrics_analyzer.benchmark.regression` and measures nothing.

## 4. Repository layout

```text
src/song_chord_lyrics_analyzer/   package (see docs/ARCHITECTURE.md)
tests/unit/                       fast, dependency-free tests
tests/integration/                tests that need FFmpeg or heavy models
tests/regression/                 fixture-driven behaviour locks
tests/fixtures/                   generated audio helpers + expectation JSON
docs/                             architecture, matrix, licence audit, this file
samples/                          small, licence-clear audio for experiments
benchmark/                        generated benchmark reports (git-ignored),
                                  plus benchmark/reference/ — committed accuracy vectors
results/                          generated analysis output (git-ignored)
scripts/                          gate script + one-off maintenance helpers
translations/                     Qt Linguist catalogues (phase 17)
external/                         third-party reference submodules (never imported)
```

`external/` holds the projects of roadmap section 24 as git submodules. They are study
material only: never imported, packaged, installed, linted, type-checked, tested or
copied from, and the exclusions are configured in `pyproject.toml` for that reason. See
[`../AGENTS.md`](../AGENTS.md) and [`../external/README.md`](../external/README.md), and
`scripts/add_external_repos.sh` to add or refresh them.

## 5. Conventions

* English only: identifiers, CLI text, errors, logs, docs and test names.
* `pathlib.Path` everywhere; never hard-code `/tmp`, `/home/...` or `C:\...`.
* Timestamps are seconds as `float` in the model; formatting happens at the
  edges (`utils/time.py`).
* New canonical data goes into a typed dataclass in `models/`, never into a bare
  `dict`.
* Public functions are typed and validated; untyped `dict[str, Any]` is only
  acceptable for engine-specific payloads that are stored verbatim.
* Subprocesses: argument lists, `shell=False`, explicit timeouts.
* Anything model-driven must be optional and must report `is_available()`.
* Roadmap progress markers: finish work and mark it in the same change. A
  completed deliverable is `[x]`; a partial one is `[~]` with the missing part
  named; `[ ]` is not implemented. The archived `[*]` convention is not used.
  See `CONTRIBUTING.md`.

## 6. Adding an engine (target workflow)

1. Read `docs/DEPENDENCY_MATRIX.md` and add the licence findings to
   `docs/LICENSE_AUDIT.md` **before** writing code.
2. Create `engines/<name>.py` implementing `ChordEngine`, `LyricsEngine`, ...,
   including `engine_info()` and `is_available()`.
3. Register it in `engines/registry.py::create_default_registry()`.
4. Add unit tests with a fake payload plus an integration test that skips when
   the dependency is missing.
5. Document installation, platform support and known limitations.

## 7. Testing policy

* Tests never require network access and never download models. The optional
  `lyrics` extras/integration tests are the exception when explicitly selected;
  the normal gate leaves them out.
* Tests must not commit copyrighted commercial songs; audio is generated
  (`tests/fixtures/audio.py`) or explicitly licensed (`samples/`).
* Optional tools are handled with `pytest.mark.skipif`, never by failing.
* Bug fixes come with a regression test; expectation-driven behaviour lives in
  `tests/fixtures/*.json` so changes show up as a reviewable diff.
* Never report accuracy numbers that were not measured (see `docs/BENCHMARK.md`
  once phase 11 lands).

## 8. Working with AI agents

The stable onboarding guide is [`AGENT_ONBOARDING.md`](AGENT_ONBOARDING.md), with
the binding rules in [`../AGENTS.md`](../AGENTS.md). It covers the environment
matrix, repository map, common setup failures and a prompt template. Tool
pointers (`CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`,
`.cursor/rules/repository.mdc`) delegate to `AGENTS.md`.

## 9. Environment variables

| Variable | Purpose |
| --- | --- |
| `SONGLAB_FFMPEG` / `SONGLAB_FFPROBE` | explicit executable paths |
| `SONGLAB_CACHE_DIR` | analysis cache location |
| `SONGLAB_DATA_DIR` | application data (and default model) location |
| `SONGLAB_TEMP_DIR` | temporary file location |

Environment variables are advanced overrides only; user-facing configuration
belongs in explicit CLI options and (later) the settings dialog.

## 10. Building the frozen application

`songlab` reaches a machine as a console script installed by pip. A user who has
no Python needs the same program as a file they can run, and that is what
`scripts/build_app.py` produces: a [PyInstaller](https://pyinstaller.org)
one-directory bundle of the CLI, built from `packaging/songlab_entry.py` (three
lines that call `cli.main.main`, so the executable and the installed command
cannot drift apart).

```bash
python -m pip install -e ".[build]"        # PyInstaller, a build tool only
python scripts/build_app.py --check        # what would be bundled, and the command
python scripts/build_app.py                # build into dist/ and run the product path
```

Two files, one plan. `scripts/build_app.py` decides **what** goes in and
`packaging/songlab.spec` says **how** the bundle is assembled; the spec imports
the script and reads those decisions back, so nothing is kept in two places. The
spec is a file and not a list of flags because PyInstaller ignores every
command-line option except the paths once a spec is given -- and because one
workaround below has to run inside the process that writes the archive.

What the build decides, and why:

* **it carries the extras this interpreter has.** Every engine reaches numpy,
  librosa, soundfile or sounddevice through `importlib.import_module(name)` -- a
  string, invisible to static analysis -- so the script declares each importable
  one as a hidden import. `--check` prints the list before anything is built.
* **the lyrics stack is excluded, deliberately.** The `parakeet-onnx` engine only
  works after `onnx-asr` downloads the model, so a bundle carrying it would still
  need a network fetch before a user could transcribe anything. `songlab doctor`
  inside the bundle then reports `lyrics` missing, which is the truth about the
  artifact rather than a promise it cannot keep.
* **a collected package does not bring its own test suite.**
  `collect_submodules("numba")` brought every module under `numba.tests`, and
  those import pytest, coverage and pygments, so a product bundle carried a test
  runner. `is_test_module()` drops them by name; nothing at runtime reaches them.
* **the archive drops the tooling a dependency only reaches by accident.** numba
  highlights LLVM dumps with pygments — inside a `try`, with a fallback — so the
  static graph carried 340 pygments modules into the product; the spec removes
  those trees from the module list before the archive is written, because
  PyInstaller's own `excludes` cannot do it (excluding a parent does not exclude
  its submodules). `coverage` is **not** on that list:
  `numba/core/lowering.py` imports `numba.misc.coverage_support` on every compile
  and that module subclasses `coverage.types.Tracer` outside its `try`, so a
  bundle without coverage builds and then fails in the chord pass — measured on
  this machine, 2026-11-01.
* **one directory, not one file.** LGPL components (libsndfile inside
  `soundfile`, the Qt build under PyQt6) require that the user can replace the
  library, which a self-extracting single file works against.
* **the notices come from the artifact.** `docs/LICENSE_AUDIT.md` §6 lists what
  must travel with a binary. `THIRD_PARTY_NOTICES.txt` is written after the
  bundle exists: the component list is read out of the PYZ archive inside
  `songlab.exe` (not from what the build was asked to carry), each name is
  matched to the wheel it came from, and that wheel's own licence text is copied
  unchanged into `notices/`. Each §6 component is then answered by file-name
  evidence inside the directory -- a Windows scipy wheel ships OpenBLAS and no
  libgfortran, and the notice says exactly that. The project `LICENSE` is copied
  beside it.
* **an unpatched CPython 3.12 needs the path anonymization switched off.**
  PyInstaller rewrites every collected code object's `co_filename` through
  `code.replace()`, and CPython 3.12.0 loses the local-slot kinds there, so a
  module whose comprehension target is also a global name comes out with the
  wrong scope. The first symptom is the frozen app dying at
  `import scipy.stats` with `NameError: name 'obj' is not defined` -- a bundle
  that builds and then cannot start. CPython 3.12.1 fixed `code.replace()`
  ([gh-110543](https://github.com/python/cpython/issues/110543), tracked
  upstream as [PyInstaller #7992](https://github.com/pyinstaller/pyinstaller/issues/7992)),
  so the spec probes the interpreter rather than version-testing it: on a broken
  one it replaces the anonymizer with a no-op -- the bundle keeps this machine's
  paths in tracebacks instead of losing scipy -- and on a patched one it does
  nothing at all. If a future PyInstaller moves that call, the build refuses with
  an explanation instead of producing the broken app.
* **a build that is not run is not a build.** After bundling, the script executes
  the *executable*: `--version`, `doctor`, `info` and `chords --json` against the
  committed sample, and it starts `songlab gui` under `QT_QPA_PLATFORM=offscreen`
  to check the window constructs inside the bundle (that it stayed up, not that
  it was clicked through). `--no-verify` skips this.

`dist/`, `build/` and the scratch under `.cache/build/` are gitignored: no frozen
artifact is committed, and the gate does not build one. The bundle has been built
and run on Windows 10 (see the record in the roadmap Phase K entry); the same
script on Linux and macOS is written but not yet executed, so those platforms are
not claimed.
