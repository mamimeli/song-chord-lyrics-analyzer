# Product Roadmap — song-chord-lyrics-analyzer

**Repository:** `song-chord-lyrics-analyzer`
**Python package:** `song_chord_lyrics_analyzer`
**CLI:** `songlab`
**GUI:** PyQt6 behind the optional `gui` extra (minimal window implemented, Phase D)
**Target platforms:** Linux, Windows, macOS — developed and tested **from source**
on those systems; standalone frozen builds and installers are the final phase
(section 14), not the current objective.
**License:** GPL-3.0-or-later
**Authoritative:** this file is the development plan. The former research-first
roadmap is preserved unchanged at
[`docs/archive/ROADMAP-pre-product-reset.md`](docs/archive/ROADMAP-pre-product-reset.md)
for history only. Where the two disagree, **this file wins**.

---

## Status rules

Every task and phase uses exactly these markers:

| Marker | Meaning |
| --- | --- |
| `[x]` | **Implemented.** The stated requirement exists in the repository, runs, and has been verified by executing it — not merely by documentation, design or partial tests. |
| `[~]` | **Partially implemented.** Some of the requirement works; the missing part is stated in the phase. |
| `[ ]` | **Not implemented.** |

Rules:

* Be conservative. Truthful progress beats a roadmap that looks complete.
* Never mark `[x]` because research finished, a design doc exists, a prototype
  exists, tests cover only part of the requirement, an engine exists but is not
  integrated, or a CLI command exists while the product workflow behind it is
  incomplete.
* Markers are updated in the same change that completes (or genuinely advances)
  the work, so the roadmap never lags the code.
* Every claim in the *Current Reality* section below was re-verified against the
  repository on **2026-10-06**, by running the code, not by reading docs.

### Work categories

Each section is tagged with its category so research can never silently become
the main path:

* **[P] Product-critical** — required for the end-user application.
* **[S] Supporting infrastructure** — tests, metrics, benchmark, docs that serve the product.
* **[R] Research / experimental** — subordinate to the product; never a blocker.
* **[F] Future enhancement** — after the product works.

---

## 0. Project Goal

**[P]** Build a free, open-source, offline-first alternative to Chordify and
Chord AI: a desktop application the user points at a song file, which analyzes
it and shows the chords (and later the lyrics) **synchronized with playback**,
and lets the user correct, transpose, simplify and export the result.

The central user experience:

```text
MP3/audio file
    ↓
audio decoding
    ↓
audio analysis
    ↓
chord detection
    ↓
timestamped ChordEvent sequence
    ↓
audio playback
    ↓
synchronized chord display
```

Later:

```text
audio → lyrics transcription → timestamped lyrics → synchronized lyrics + chords
```

### Priority order

Since 2026-11-02 the ladder is short and explicit — **product quality first,
recognition accuracy next, complete and validated functionality then, standalone
distribution last**:

1. **Priority A — core product quality**, above all chord recognition accuracy
   and its reliability across genres, instruments, recording conditions and file
   lengths (Phase B, Phase I, Phase K's performance tasks).
2. **Priority B — complete and reliable application functionality**: every feature
   the project already intends, working and honest about what it cannot do
   (Phase D, Phase G, Phase H, Phase L).
3. **Priority C — testing, accuracy validation and stabilization**: a reproducible
   benchmark against independently verified ground truth, measurable acceptance
   criteria, regression tests for every improvement, and a documented limitation
   list (Phase J, Phase L).
4. **Final stage — cross-platform packaging and distribution**: frozen builds,
   installers and per-OS smoke tests, deferred until the entry criteria in
   section 14 are met. Cross-platform *source* compatibility (paths, discovery,
   CI, no OS-specific assumptions) is **not** deferred — it stays an ongoing
   requirement of every change.

The order below is the one that built the vertical slice (2026-10-06); it is kept
as the historical sequence, not as the current plan:
*audio loading → chord analysis → timestamped events → playback → synchronization
→ basic GUI → lyrics → synchronized lyrics → editing → transpose/simplify →
export → additional engines and accuracy → research.*

This order may be adjusted only when the repository proves another order is
technically necessary — never to insert more research ahead of the product, and
never to insert packaging ahead of accuracy.

### Direction change (2026-11-02)

Packaging stopped being the remaining objective. The Windows 10 frozen build of
2026-11-01 (section 14) is kept as a completed technical milestone and a founda-
tion for the final distribution phase, and is **not** expanded at this stage: no
Linux or macOS build, no installer and no briefcase work is scheduled until the
entry criteria in section 14 are met. What a user runs today is the source
install (`pip install -e .`), and what the project owes them is a genuinely
accurate, feature-complete analyzer. The reason is on the record: the measured
chord accuracy is 0.6312 CSR (0.6384 triad-reduced) on 180 GuitarSet comping
takes (`docs/ENGINE_COMPARISON.md` §8), which is not the accuracy of the proprie-
tary apps this project aims to replace, and a polished binary of an inaccurate
analyzer is not a product increment. `AGENTS.md` and `docs/AGENT_ONBOARDING.md`
carry the same instruction so a fresh agent does not pick packaging up again.

Section numbers stay where they were so that the references in `docs/`,
`CHANGELOG.md` and the commit history keep resolving; the **order to work in** is
10 (accuracy, PRIMARY) → 11 (the validation gate) → 12 (Phase L, product
completeness) → 13 (source compatibility, ongoing) → 14 (packaging, deferred).
Phase L is new in this change; the packaging content that used to sit in Phase K
moved to section 14 with its Windows 10 record intact.

### Direction change (2026-10-06)

The previous roadmap made research → benchmark → dataset → model → engine →
experiment the main path. That loop is now **supporting activity only**
(Phases I/J and the Research Backlog). All existing research, code, tests and
documentation are preserved; nothing is deleted because it is not on the
immediate product path. From now on the main path is:

**working vertical slice → validation → GUI → lyrics → editing/export →
improvements → additional engines/research.**

---

## 1. Current Reality / Baseline Audit

**[P]** Verified by execution on 2026-10-06 (Linux, Python 3.13, CPU-only).
Gate at the time of the audit: `ruff check` clean, `ruff format --check` 84 files
clean, `mypy` 57 files clean, `pytest` **1165 passed / 9 skipped** (core venv)
and **1173 passed / 1 skipped** (DSP venv with numpy/librosa).

Gate re-run after the headless Phase A/B/C work (same day): `ruff` clean,
`ruff format --check` 98 files,
`mypy` 61 files, `pytest` **1231 passed / 49 skipped** (core venv) and **1279
passed / 1 skipped** (DSP venv with numpy/librosa/soundfile/sounddevice).

Gate re-run after the Phase C display work (2026-10-07, same machine): `ruff`
clean, `ruff format --check` 103 files, `mypy` 63 files, `pytest` **1268 passed
/ 52 skipped** (core venv) and **1319 passed / 1 skipped** (DSP venv, where the
real-device playback and display-follow tests run).

Gate re-run after the Phase D window work (2026-10-08, same machine): `ruff`
clean, `ruff format --check` 118 files, `mypy` 71 files, `pytest` **1340 passed
/ 57 skipped** (core venv) and **1395 passed / 2 skipped** (DSP venv, which now
also installs the optional `gui` extra, so the window's tests run there on the
offscreen platform plugin, plus the real-device playback/follow tests).

Gate re-run after the playback playhead fix and the decode integration
(2026-10-16, same machine, Python 3.13.5): `ruff check` clean,
`ruff format --check` 150 files clean, `mypy` 87 files clean, `pytest` **1883
passed / 11 skipped** (`.venv` - on this machine it has the DSP and GUI extras
installed as well, so it is *not* the dependency-free core of the CI matrix)
and **1891 passed / 3 skipped** (`.venv-chords`: numpy 2.5.3, librosa 1.0.0,
sounddevice 0.5.6, real output device). The DSP suite was run a second time
under contention and gave **1891 passed / 3 skipped in 887 s** with eight
competing CPU processes (load average ~12 on 4 cores); `tests/integration/
test_display_integration.py` alone was run six times back to back, **3 passed
every time**, where the full-suite run of the same day *before* the fix failed
it with `AssertionError: the playhead must never go backwards` (positions
0.0503198 then 0.0385552) and both `.venv-chords` full-suite runs after the fix
passed it (`.venv` skips that test: no output device there).

Gate re-run after the chord chart and the measured front-end/template and
minimum-duration work (2026-10-27, same machine, Python 3.13.5, numpy 2.5.3,
librosa 1.0.0, PyQt6 offscreen): `ruff check` clean, `ruff format --check` 172
files clean, `mypy` 93 files clean, `pytest` **2136 passed / 2 skipped in
262 s**
(`.venv-chords`: numpy 2.5.3, librosa 1.0.0, sounddevice 0.5.6, PyQt6
6.11.0, real output device, `QT_QPA_PLATFORM=offscreen`; the two skips are the
intentional "the optional stack is installed here" branches) and **2128 passed
/ 10 skipped in 226 s** (`.venv`: no output device, so the eight playback
tests skip; the two "stack installed" branches differ too).

Gate re-run on **Windows 10**, first time on that platform (2026-10-31, Windows
10 22H2 build 19045.6466, CPython 3.12.0, numpy 2.5.4, librosa 1.0.0, soundfile
0.14.0, sounddevice 0.5.6, onnx-asr 0.12.0 with onnxruntime 1.31.1, PyQt6
6.11.0, ruff 0.17.3, mypy 2.4.1, pytest 9.2.0, FFmpeg and ffprobe 9.0.2 from
winget, real output device, no `QT_QPA_PLATFORM` override): `ruff check` clean,
`ruff format --check` 173 files clean, `mypy` 93 files clean, `pytest` **2133
passed / 10 skipped in 422 s** (the ten skips are the eight Qt catalogue tests
that need `lrelease` plus the two "the optional stack is installed here"
branches; the same counts held before and after the test-guard changes below,
because that environment installs everything). The first run in that
environment, before any fix and with neither FFmpeg nor the `lyrics` extra
installed, was **17 failed / 2102 passed / 19 skipped**. Six things had to
change to reach a clean gate — the PyQt6 6.12 stubs that no type checker can
parse, host separators leaking into the canonical JSON, the GuitarSet manifest
absolute-path rule that asked only the host flavour, the `resource` import that a
Windows type checker cannot follow, fifteen tests that required the `lyrics`
extra the documented gate does not install, and the Qt-free matrix that could not
collect the window tests at all — all recorded in `CHANGELOG.md`.

The gate was run again on that same machine and interpreter on 2026-10-31, after
the finiteness boundary landed (`models/validate.py`, the CLI time flags and the
chroma merge option — `CHANGELOG.md`): `ruff check` clean, `ruff format --check`
**175 files** clean, `mypy` **95 source files** clean, `pytest` **2182 passed /
10 skipped in 377 s** (the new tests are the finiteness cases, so the skips are
the same ten). The two CI test shapes were re-run alongside it in their own
venvs: dev-only **1930 passed / 109 skipped / 0 failed in 56 s** and
`dev,dsp,gui` with FFmpeg **2174 passed / 18 skipped / 0 failed in 150 s**.

That last item is what the CI matrix runs, so it was reproduced in a second
Windows venv installing exactly `-e ".[dev]"` — no Qt, no DSP, no FFmpeg needed.
Before: **4 collection errors, nothing run** (`ModuleNotFoundError: No module
named 'PyQt6'`, because four window test modules imported the Qt-needing package
above their own skip guard). After the guard move and the `_requires_dsp` marker:
**1880 passed / 110 skipped / 0 failed in 56 s** (2026-10-31, same interpreter).
A third venv with `-e ".[dev,dsp,gui]"` — the `dsp` job's shape, FFmpeg present,
no `lyrics` extra — gave **2125 passed / 18 skipped / 0 failed in 142 s**. macOS
has still never been run.

### Windows 10 product path — verified (2026-10-31)

The same environment ran the user-facing chain end to end: `songlab doctor`
lists the four registered engines and finds the winget FFmpeg; `songlab info`
probes `samples/vocadito_6.wav` (23.832 s, pcm_s16le, mono) and an MP3 transcode
of it made locally with FFmpeg (64 kbit/s, probed with ffprobe); `songlab chords`
on that MP3 returns 10 timestamped events through `chroma-baseline`; `songlab
play --at 5` prints the frame under the playhead; `songlab analyze --json`
returns 28 chord events and a forward-slash `input_path`; `songlab export
--format json -o` and `--format chordpro -o` write the file themselves as UTF-8
even when the output path contains a space, and the JSON they write reloads with
`provenance/input_path` in forward slashes; and `songlab gui
samples/vocadito_6.wav` opens a real top-level window titled "Song Chord Lyrics
Analyzer" with nothing on stderr. PowerShell 5.1's `>` redirection was measured
on the same machine and re-encodes the redirected `--json` stdout as UTF-16LE, so
the README tells Windows users to export with `-o`. A bad time on the command
line was measured there too: `songlab chords --start nan` on a readable WAV used
to answer "Unsupported or unreadable audio file … cannot convert float NaN to
integer", and since the 2026-10-31 finiteness guard it answers `--start must be a
finite number of seconds, got nan.` and exits 2 without opening the file.
What only a person can
confirm on Windows is
how it *looks* — waveform, chord bands and the chord-over-lyrics chart drawn
correctly — which the offscreen tests assert but this run did not screenshot.

### Windows 10 text output — a real bug, found and fixed (2026-10-31)

Checking the `schema_version` stamp (§1 of `docs/SERIALIZATION.md`) meant piping
`songlab analyze --json` into a file on this machine, and the file was not valid
UTF-8: `json.load(..., encoding="utf-8")` stopped with "codec can't decode byte
0xed in position 3812". The cause is not songlab — it is the stream. A redirected
Python stream on Windows takes the ANSI code page (measured here:
`sys.stdout.encoding == 'cp1252'` with `locale.getpreferredencoding() == 'cp1252'`),
while the document is written with `ensure_ascii=False` because its text is meant
to appear literally. So the Spanish words of a transcription went out as cp1252
bytes, and the same hole crashes instead of corrupting when the text has no byte
in that code page: before the fix, `songlab info "♪.wav" --json` exited 1 with
"Unexpected error: UnicodeEncodeError: 'charmap' codec can't encode character
'\u266a'" — an internal exception class for an ordinary file name.

`cli/main.py:configure_utf8_stdio()` now runs as the first statement of `main()`
and reconfigures stdout and stderr to UTF-8 unless the stream already writes
UTF-8 (an interactive console, a UTF-8 locale) or cannot be reconfigured (a
captured test stream). Re-running the same redirect on the 35.208 s committed
clip produced a UTF-8 file that loaded, printed `schema_version: 1` with 28 chord
events, and rebuilt through `decode(AnalysisResult, …)`. `songlab export -o FILE`
was never affected — it opens its own file as UTF-8 — and the POSIX C-locale case
(ASCII stdout, the same crash class on Linux containers) closes the same way.
Locked by `tests/unit/test_cli.py::TestStdioEncoding`, which fails before the fix
for both reasons: exit code 1, and cp1252 bytes where UTF-8 was promised.

### Windows 10 full product path cost — measured (2026-10-31)

The same machine is the first reference point for the real-time factor of the
whole product path, recorded in `docs/ENGINE_COMPARISON.md` §9 with its
environment and both fixtures. In short: on Windows 10, CPython 3.12, CPU only,
`songlab analyze` with all four registered engines took **23.0–27.4 s on the
35.208 s committed clip (RTF 1.29–1.53)** and **67.5–88.4 s on a 281.664 s cost
fixture (RTF 3.19–4.17)**, and without the optional `lyrics` extra the same
fixtures ran at **RTF 4.66–4.83** and **19.9–26.8**. The transcription is
72–84 % of the full path's time — the chord, key and tempo layers are not the
bottleneck — and the chord layer's own cost barely grows with file length
(4.3–4.7 s at 35 s versus 5.6–6.0 s at 282 s), which is why a short clip
measures a low real-time factor. Peak RSS has no Windows figure by design
(`resource.getrusage` is POSIX), so the memory half of the comparison stays
Linux-only. These are 2–3 run measurements on one laptop, quoted as a spread.

### Windows 10 window on a real MP3 — user-reported (2026-11-02)

The maintainer launched the application on Windows 10, opened a real MP3 and
reported what the window showed: version 0.1.0, Python 3.12.0, platform Windows
AMD64, run status succeeded, **115 chord events from `chroma-baseline`, average
chord confidence 0.58, 15 lyric segments and 225 words, detected key A major,
detected tempo 129.2 BPM**, with the waveform, the lyrics and the analysis
metadata all visible. A screenshot was supplied with the report; the report does
not say whether the launch was the source checkout or the frozen build, so this
entry evidences neither of those two paths specifically — the source path is
evidenced by the 2026-10-31 run above.

Read it for exactly what it is: **the application runs end to end on Windows 10
and produces a complete analysis.** It is not an accuracy measurement. The 0.58
is the engine's own calibrated confidence, not a hit rate — the measured
relationship between the two is in `docs/ENGINE_COMPARISON.md` §8, where a mean
confidence in that range sits on a 0.6384 triad CSR pipeline. Accuracy against
independently verified chord annotations is what section 10 task A1 and the
acceptance table there are for.

### Manual GUI verification — user-reported (2026-10-18)

The window was launched **by hand on MX Linux 25** (Debian 13 based) in this
repository's `.venv-chords` environment (CPython 3.13.5, PyQt6 installed), from
the repository root:

```bash
source .venv-chords/bin/activate
songlab gui
```

The **user** — not an automated test — opened an MP3 file, waited for the
analysis, and reported: the waveform appeared; a lyrics panel and the audio
information appeared on the right; playback worked; the position advanced along
the waveform; and chord names were displayed and changed during playback. The
same user estimated that roughly **75 % of the detected chords were correct**,
from listening and watching.

This is a **user-reported manual observation, not a benchmark**: one song, no
reference annotations, no defined matching rule, no repeatable procedure. It
must not be quoted as a validated 75 % chord-detection accuracy; an objective
figure needs a reference dataset with timed chords and a fixed evaluation
procedure (GuitarSet + `docs/BENCHMARK.md`). The launch steps, the screenshot
and the virtual-environment shutdown are documented in the README section
"Launching it by hand (MX Linux 25)". The read-only code audit that this
observation prompted is [`docs/CHORD_DETECTION_AUDIT.md`](docs/CHORD_DETECTION_AUDIT.md).

Separate from that manual session, the audit's own run on 2026-10-18 executed
the chord-related unit suites in `.venv-chords` and got **381 passed** (no GUI
and no real song).

### Chord-over-lyrics chart — verified (2026-10-21)

The window now draws a **chord chart over the synchronized lyrics**, the view
Chordify and Chord AI are known for, and it was verified by running the code:
`app/chord_lyrics.py` seats every chord above the timed word it starts on,
gives instrumental intros/breaks their own chord-only rows, never repeats a
chord that merely spans into the next line, and respells roots for a flat key;
`gui/lyrics_view.py` paints one monospace chord row plus one lyric row per
block, highlights the current chord from the same frame as the big label, and
keeps the block-to-display-index mapping exact for the lyric edits. The pure
presenter has 16 unit tests, the widget has 17 offscreen tests, and the window
has a test that C opens the first line, G starts a gap row, N opens the second
line and F starts the closing gap row. The measured accuracy of the engine
behind the chart is in §10 (Phase I); this section claims the **display**, not
a new accuracy number.

### The product path, link by link

| # | Link | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Real audio file input | `[x]` | `audio/validation.py` + `audio/probe.py` (ffprobe; WAV via stdlib). Verified on a real song file (296.8 s, MP3, 324 kbit/s). |
| 2 | Decoding to samples | `[x]` | One decode owner: `audio/decode.py` → `decode_audio()` (librosa/soundfile backend plus a stdlib WAV backend, mono/interleaved floats + sample rate) is asked by the chords, key, tempo and lyrics engines for the window they need, by `SoundDevicePlayer.load` for playback, and by `SongSession` for the waveform fallback; no component calls `librosa.load` privately any more. Verified 2026-10-16 on `samples/vocadito_6.wav` and `samples/vocadito_16.wav`: the three DSP engines return the same chord events (start/end/label), key and tempo before and after the switch, both whole-file and with a time window, plus a real compressed transcode through the service (`tests/integration/test_decode_integration.py`). |
| 3 | Chord engine on real audio | `[x]` | `ChromaBaselineEngine` registered, tested, measured (CSR **0.6312**, triad 0.6384, on 180 GuitarSet comping takes, instructed lead sheet, 2026-10-27 — `docs/ENGINE_COMPARISON.md` §8, reproducible with `scripts/chord_benchmark.py`; 0.6121 with the previous front end). Ran on a real song during the audit. |
| 4 | Timestamped ChordEvent sequence | `[x]` | `songlab chords` printed 76 events with `start`/`end`/`label` on a real song; `songlab analyze --json` emitted the same inside the canonical document with provenance (schema version 1, `schema/codec.py`). |
| 5 | Audio playback | `[x]` | `audio/playback.py`: `SoundDevicePlayer` streams decoded samples through PortAudio (`sounddevice`, optional `playback` extra), with `load`/`play`/`pause`/`stop`/`seek`/`close`. Verified on a real device on 2026-10-06; skipped honestly where no output device exists. |
| 6 | Lyrics engine (roadmap Phase E) | `[x]` | `ParakeetLyricsEngine` via `onnx-asr` (MIT runtime, CC-BY-4.0 weights), `songlab lyrics`, `run_analysis()` lyrics step. Chunked at 20 s; words carry `unknown` confidence. Verified on `samples/vocadito_6.wav` (real weights and real voice, offscreen) and structurally everywhere else. Model pulls (CC-BY-4.0) are fetched on first use and never committed. |
| 7 | Synchronized display (headless) | `[x]` | Phase C: `app/display.py` renders every `DisplayFrame` on a timer tick, terminal as the first front end. |
| 8 | Desktop window minimal slice | `[x]` | Phase D: `songlab gui`, `gui/` (`main_window.py`, `timeline.py`, `analysis_panel.py`, `__init__.py`), PyQt6 behind the `gui` extra, offscreen-verified; `app/timeline.py` + `app/summary.py` present all the data.
| 6 | Current playback timestamp | `[x]` | `position()` on the same player, backed by a pure `PlaybackTimeline` (injectable clock) and re-anchored to the frames PortAudio actually consumed. Deterministic unit tests plus a real-device test. |
| 7 | Synchronized chord display | `[x]` | `songlab play` draws the chord under the playhead from `SessionSnapshot` (`app/display.py`: `frame_from`, `render_frame`, `ConsoleDisplay`, `follow`; `cli/commands/play.py`), refreshing while the song plays and updating the frame as the chord changes. `--at SECONDS` prints one frame headlessly. Verified end to end on a real device on 2026-10-07 (the chord changed during real playback) and headlessly in CI. **Now with a window too:** since 2026-10-08 `songlab gui` renders the *same* frame, plus the waveform, the chord bands and the analysis panel (`gui/` + `app/timeline.py` + `app/summary.py`), so the display exists both as a terminal line and as a desktop window. |
| 9 | Chords above the lyrics | `[x]` | Phase F, 2026-10-21: `app/chord_lyrics.py` seats each chord above the timed word it starts on, with instrumental gap rows and flat-key spelling; `gui/lyrics_view.py` draws it in the same block the lyric edits address. 16 presenter tests, 17 offscreen widget tests and a window test (`TestChordsAboveTheLyrics`) were run. |

**Conclusion:** all seven links now exist, in **two** front ends, plus the chart
that seats the chords over the lyrics. Links 1–4 are verified on real audio, 5–6
are a tested player with a playhead, 7 is the display driven by the same
session, and 9 is the chord-over-lyrics chart driven by the effective chord and
lyric layers: the frame drawn at each refresh carries exactly the chord
`chord_at()` claims for that position, so neither the terminal line nor the
window can drift from the playhead, and a placed chord is anchored to the word
whose timestamps cover its onset. The **First Product Milestone (Phase C) is
therefore reached as a command-line product slice**, and **Phase D
(2026-10-08) adds the desktop window** around it: open a file, see the waveform
timeline with the detected chords, play, pause, seek, always see the chord for
the current position, and read the chords above the synchronized lyrics. What is
still missing from the *accuracy* of a Chordify/Chord AI-style application is a
learned chord model and a broader vocabulary; that is Phase I work, measured
against the same harness, not a missing foundation.

### What is genuinely implemented today

* `[x]` Canonical typed model: `models/` (AudioDocument, ChordEvent with
  start/end/label/confidence, KeyEstimate, TempoEstimate, LyricSegment/Word,
  AnalysisResult, Provenance, AnalysisRun).
* `[x]` Canonical JSON codec with `SCHEMA_VERSION = 1` (`schema/codec.py`).
* `[x]` Engine protocols + registry (`engines/base.py`, `engines/registry.py`).
  Registered engines: **chords** `chroma-baseline`, **lyrics** `parakeet-onnx`,
  **key** `krumhansl`, **tempo** `librosa-tempo` (verified through
  `create_default_registry()` on 2026-10-16). Kinds `BEATS`, `STEMS`, `NOTES`
  have **no** registered engine.
* `[x]` Chord engine: CQT chroma → 24 harmonic-weighted or binary triad
  templates → majority or Viterbi decoding (`engines/chroma_baseline.py`,
  `engines/decoding.py`), with a measured `sqrt` chroma compression, the
  change penalty 0.40, a 0.50 s minimum-duration merge, and every front-end /
  template option measurable separately (`docs/ENGINE_COMPARISON.md` §7, §8).
  Measured 2026-10-27: **CSR 0.6312 / triad 0.6384** on 180 GuitarSet comping
  takes (previous front end 0.6121 / 0.6183; the 0.30 s step measured 0.6283 /
  0.6356).
* `[x]` Application service `run_analysis()` (`analysis/service.py`): runs
  chords/key/tempo, skips unavailable engines honestly, assembles provenance
  (version, SHA-256, python, platform, engines, configuration).
* `[x]` CLI: `songlab info`, `doctor`, `chords`, `lyrics`, `analyze` (incl.
  `--json`), `export`, `play`, `gui`, `benchmark` (the command list of
  `songlab --help`, checked 2026-10-16).
* `[x]` Audio metadata probing, FFmpeg discovery with platform install hints,
  input validation (`audio/`).
* `[x]` Playback and the two displays: `audio/playback.py` (tested player with a
  playhead), `audio/peaks.py` (waveform peaks), `app/display.py` (terminal
  display), `app/timeline.py` + `app/summary.py` (timeline and panel presenters)
  and `gui/` (the PyQt6 window behind the optional `gui` extra). The window's
  lyrics view is a **chord chart**: `app/chord_lyrics.py` aligns chord onsets to
  timed words and `gui/lyrics_view.py` draws them, with instrumental gap rows
  and the active chord highlighted (2026-10-21).
* `[x]` Key-aware display spelling: `normalization/spelling.py` respells chord
  roots and slash basses for flat keys on the terminal, the chord strip, the big
  label and the chord chart, while the canonical document keeps its sharp
  spelling. An unknown key keeps the canonical spelling. Tests:
  `tests/unit/test_spelling.py`.
* `[x]` Metrics as library code: chord (CSR, boundary/change, timing), key,
  tempo (half/double kept), lyrics WER/CER (`metrics/`, `evaluation/`).
* `[x]` Benchmark infrastructure, kind-agnostic runner (`benchmark/`).
* `[x]` Tests: **1883 passed / 11 skipped** and **1891 passed / 3 skipped**
  (gate re-run dated 2026-10-16 above; the two local venvs differ by the eight
  tests that need an audio output device), fixtures with annotation-only
  GuitarSet oracles, CI workflow (the DSP job also runs the window offscreen).
  The chord-harness work on 2026-10-19 adds 27 tests; the gate then reported
  **1910 passed / 11 skipped** (same machine, `ruff` and `mypy` clean). The
  confidence work on 2026-10-20 adds 57 tests; the gate then reported **1967
  passed / 11 skipped** (`ruff` clean over 162 files, `ruff format --check` 162
  files, `mypy` 89 files). The chord-chart, spelling, chart-check and
  measured-front-end work through 2026-10-21..27 adds its own tests; the full
  `.venv-chords` suite reports **2136 passed / 2 skipped in 262 s**, `ruff`
  clean over 173 files and `mypy` 93 files clean. The Windows 10 gates on
  2026-11-01 (the full `.venv`: `dev`, `dsp`, `playback`, `gui` and `lyrics`,
  FFmpeg on `PATH`) report **2189 passed / 10 skipped in 356 s** for the extras
  report and **2200 passed / 10 skipped in 420 s** after the committed
  product-path benchmark case, both with `ruff check`, `ruff format --check` and
  `mypy` clean; the ten skips are the eight Qt Linguist (`lrelease`) tests, the
  "PyQt6 is installed here" branch of the window-command test and the
  lyrics-integration note. The same day the
  `dev`-only venv — the CI matrix shape, no Qt and no DSP — runs the CLI suite
  (23 tests) and the nine dependency-free halves of the new case module clean.
  After the cost-probe tooling (14 more tests) and the README platform split, the
  full `.venv` gate on the same machine reports **2214 passed / 10 skipped in
  386 s** with `ruff check` clean, `ruff format --check` 178 files clean and
  `mypy` 95 source files clean; the same venv set was re-run, and the `dev`-only
  CI-matrix venv gives **1952 passed / 119 skipped in 42 s**, where the new probe
  module splits exactly as designed — its 6 offline checks pass and its 8
  premise checks skip for want of numpy/librosa, so the CI shape never runs a
  measurement it cannot make.
* `[x]` Documentation of decisions: `docs/ARCHITECTURE.md`,
  `DEPENDENCY_MATRIX.md`, `LICENSE_AUDIT.md`, `DATASET.md`,
  `ENGINE_COMPARISON.md`, `BENCHMARK.md`, `TROUBLESHOOTING.md`.
* `[x]` Chord confidence: every `ChordEvent` carries a measured value. The
  current fit (2026-10-27, after the sqrt/harmonic front end and the 0.50 s
  minimum) is a logistic with slope 28.7942 / intercept -0.0738 on the event's
  mean score margin; the held-out 90 takes give Brier 0.1485 and ECE 0.0363,
  and accuracy is 0.809 on events scoring at least 0.60 (47.6 % of the held-out
  duration). The raw margin stays in `metadata["score_margin"]`. The earlier
  fits (slope 29.8735 / intercept -0.1484 for the 0.30 s step, and 23.4861 /
  0.1973 for the binary-template/tuning-zero front end) are kept in
  `docs/ENGINE_COMPARISON.md` as history.
* `[x]` Real-file E2E: `tests/integration/test_analysis_e2e.py` runs the real
  default registry (chroma-baseline + krumhansl + librosa-tempo) over a
  deterministic generated WAV and, with FFmpeg, over its MP3 transcode, and
  asserts timestamped chord events cover the file. It skips without the
  optional DSP stack.
* `[x]` Transposition: `transpose_chord_label()` /
  `transpose_note_name()` as tested library functions, plus the user-facing
  workflow since 2026-10-13 (Phase H): the window's "Transpose all chords..."
  dialog and `songlab export --transpose N`.
* `[x]` Playback foundation: `audio/playback.py` (`Player` protocol, timeline,
  `sounddevice` backend) and the shared decode service `audio/decode.py` it uses.
* `[x]` Synchronized chord display (terminal): `app/display.py` (pure
  `frame_from`/`render_frame`, `ConsoleDisplay`, `follow` with an injectable
  sleep) and `songlab play`, which draws the chord under the playhead and
  refreshes it while the song plays.
* `[x]` Minimal GUI window (Phase D): `gui/` + `songlab gui`, PyQt6 behind the
  optional `gui` extra, with the waveform timeline, the chord strip, the
  seekable playhead and the analysis panel.
* `[~]` GUI editing/undo-redo/exports/translations (`docs/GUI_REQUIREMENTS.md`
  `[F]` list: the lyrics view 2026-10-09, the editing/undo-redo/transpose/
  simplify/export-dialog work through 2026-10-13 and the confidence/engine
  panels 2026-10-14 are in; translations remain - the Language menu ships but
  no catalogue does), beats engine, stem separation, alignment, fusion,
  packaging (deferred to section 14 on 2026-11-02; one frozen Windows 10 build
  exists and was run there, no other platform).
* Empty package (placeholder only, `__init__.py`): `fusion/`. The packages that
  used to be placeholders hold real code now: `export/` (JSON / ChordPro /
  Markdown renderers), `alignment/` (`.lrc` and `.srt` parsing) and `i18n/`
  (catalogue discovery and the `QTranslator` wiring behind the window's
  Language menu).

### Known documentation drift (fix opportunistically, not a phase)

* Resolved on 2026-10-16: §1 claimed `export/`, `alignment/` and `i18n/` were
  empty packages (they have implementations), the link-2 row still said the DSP
  engines decode themselves, the registry bullet said `LYRICS` had no engine
  (`parakeet-onnx` is registered), the CLI bullet omitted `lyrics` and `export`,
  the transposition bullet still said there was no user-facing workflow, the
  same bullet still listed a lyrics engine as remaining work although Phases E
  and F are `[x]`, the test counts carried no date, and
  `docs/GUI_REQUIREMENTS.md` did not record
  the window's Language menu. The dated session handoff's "Partially implemented"
  entry for decoding said the same, and was corrected with it. The `AGENTS.md`
  line about the registered engines is now stale in the same way (it predates
  the lyrics engine) and was left alone as the instruction file.
* Resolved on 2026-10-08: the "no Qt code in `src/`" claims in `README.md`,
  `docs/GUI_REQUIREMENTS.md` and `docs/ARCHITECTURE.md`
  (the window exists now), the stale `README.md` test badge again, and the
  `docs/DEPENDENCY_MATRIX.md` §2.1/§8 rows that still spoke of PyQt6 and Qt
  Multimedia as future work.
* Resolved on 2026-10-06/07: the stale `README.md` test badge, the description
  of the old `[*]` marker convention in `README.md`/`AGENTS.md`, the "no
  analysis engine exists yet" wording, and the `last (phase 15)` GUI row, which
  referenced the pre-reset phase numbering. Counts are re-verified whenever the
  gate is re-run and are stated with their date, so they can never be read as
  live numbers.

---

## 2. Phase A — Audio Input and Playback Foundation **[P]**

**Objective:** load an audio file, decode it to samples, play it, and answer
"what is the current playback position?" — the substrate for everything after.

**Current status:** `[x]` — the two `[~]` tasks below (one decode owner) were
closed on 2026-10-16, which is what the acceptance criteria were waiting on.

### Tasks

- [x] Input validation and safe path handling (`audio/validation.py`)
- [x] Metadata probing: ffprobe + WAV fallback (`audio/probe.py`)
- [x] FFmpeg discovery, no-shell invocation, install hints (`audio/ffmpeg.py`)
- [x] Decoding to samples for **analysis** — every DSP engine decodes through
  the shared service below: `chroma_baseline.py`, `key_krumhansl.py` and
  `tempo_librosa.py` were switched over on 2026-10-16 (each keeps its own
  sample rate, mono downmix, offset/duration window and output; verified by
  comparing engine output before and after on real sample files)
- [x] Shared application-level decode service (path → mono/stereo samples +
  sample rate): `audio/decode.py` exposes `decode_audio()` with a librosa/soundfile
  backend and a dependency-free stdlib WAV backend, and returns one flat
  interleaved float buffer plus its sample rate. Tests: `tests/unit/test_decode.py`
  (WAV half runs in the core venv) and `tests/integration/test_decode_integration.py`
  (a real compressed transcode). It is the only decode path: the four engines,
  the player and the session's waveform fallback all call it, and each engine's
  unit suite pins the call it makes (`test_the_audio_comes_from_the_shared_decode_service`)
- [x] Playback abstraction: player interface with `load`, `play`, `pause`,
  `seek`, `position()`, `duration()`, `state` callbacks (no Qt types in it).
  `audio/playback.py`: a `Player` Protocol, a pure `PlaybackTimeline` (position
  state machine driven by an injectable clock) and `SoundDevicePlayer`
- [x] Playback backend decision: **`sounddevice`** chosen over Qt Multimedia.
  MIT, optional, behind the `playback` extra; licensed and justified in
  `docs/DEPENDENCY_MATRIX.md` §2.1. Confirmed in Phase D (2026-10-08): the window
  reuses `SoundDevicePlayer` through `SongSession` rather than adding a Qt
  Multimedia backend, so the CLI and the GUI share one tested audio path, and
  the `Player` Protocol still allows that backend later
- [x] Waveform peak data extraction for the timeline (downsampled min/max per pixel
  bucket): `audio/peaks.py` (`waveform_peaks()`, `peaks_of()`, `WaveformPeaks`),
  dependency-free (no numpy import) and frame-aligned, so the same reduction
  serves the stdlib WAV backend and the DSP one. Reached by the window through
  `SongSession.waveform_peaks(buckets)`, which reuses the samples the player
  already decoded and caches the result per resolution. Tests:
  `tests/unit/test_peaks.py`
- [x] Tests: unit tests with committed WAV fixtures, a fake-PortAudio stream test
  for the headless contract, and a real-device integration test that plays,
  pauses, resumes and seeks a short file (`tests/integration/test_playback_integration.py`,
  skipped when no output device exists). The decode half landed earlier
  (`tests/unit/test_decode.py`, `tests/integration/test_decode_integration.py`)
- [x] Works with a real MP3 file, not only WAV: `decode_audio()` reads a real
  compressed file through soundfile/librosa, and the E2E analysis test runs the
  whole pipeline on an MP3 transcode of its generated fixture

### Files / modules

`src/song_chord_lyrics_analyzer/audio/` (new `decode.py`, `playback.py`),
`models/audio.py`, `pyproject.toml` (optional extra), `tests/`.

### Acceptance criteria

The phase is complete only when: (1) a real MP3 is decoded through one shared
service; (2) a player can play, pause, seek and report its position in seconds;
(3) waveform peak data can be produced for a rendered timeline; (4) tests cover
the workflow and the gate stays green.

### Dependencies / blockers

Requires a playback library choice (small, license-audited). No other blocker.

### Must NOT be considered complete

Decoding that only works inside engines; a player that works only on the
developer's machine; position polling that is not tested.

---

## 3. Phase B — Functional Chord Analysis **[P]**

**Objective:** the existing baseline engine reliably turns real audio into
timestamped chord events exposed through the application service.

**Current status:** `[x]` — the engine and its output exist and were verified on
real audio during the audit; per-chord confidence landed on 2026-10-20 and the
JSON serialization contract was written down on 2026-10-31
([`docs/SERIALIZATION.md`](docs/SERIALIZATION.md)), so every task in this phase
has landed. What remains open in this area is accuracy (Phase I), not the
contract or the algorithm.

### Tasks

- [x] Existing `chroma-baseline` engine (templates, majority + Viterbi decoders)
- [x] Existing chord normalization (`normalization/chords.py`)
- [x] Existing temporal decoder with measured penalty (`engines/decoding.py`)
- [x] Timestamped `ChordEvent` output with `start`, `end`, `label`
- [x] Serialization through the canonical JSON codec (schema version 1)
- [x] Exposed via `run_analysis()` and `songlab analyze --json`
- [x] Verified manually on a real MP3 song (2026-10-06): 76 timestamped events, exit 0
- [x] Committed end-to-end integration test: real audio file → `run_analysis()`
  → assert timestamped chord events cover the duration (fixture audio committed
  or generated deterministically; must not depend on a private submodule).
  `tests/integration/test_analysis_e2e.py` writes a deterministic C–G–F–C WAV,
  runs the real default registry and, where FFmpeg exists, the same file as an
  MP3 transcode; skips honestly without the DSP stack.
- [x] Per-chord confidence from the baseline (score margin), so `confidence` is
  a measured number instead of always `unknown`. `segment_margins()` averages
  the emitted label's margin over the event's frames (negative where the
  decoder overrode a frame), `margin_confidence()` maps it with a logistic
  fitted on GuitarSet, and both are covered by `tests/unit/test_chroma_baseline.py`;
  the calibration, risk–coverage curve and refit (`--fit-confidence`) are in
  `docs/ENGINE_COMPARISON.md` §6
- [x] Document the stable JSON serialization contract (fields of a chord event,
  units, edge cases: `N`, `?`, overlaps) in `docs/` — landed 2026-10-31 as
  [`docs/SERIALIZATION.md`](docs/SERIALIZATION.md): the six JSON writers and
  their wrapping, the top-level and `ChordEvent` field tables, the unit table,
  the `N` / `?` rendering rules, open-ended `end`, permitted overlaps, the
  closed enumerations, the required-key list, paths/encodings, and the version
  rules. Its §8–§9 record what the contract deliberately does *not* promise
  (`raw`, `metadata`, message wording, float equality) while §4 promises one
  thing hard: no `NaN` or infinite number can reach a document, because the
  model, the CLI time flags and the chroma merge option all refuse it
  (closed 2026-10-31, the same day the gap was written down). The version gap it
  found is closed too, the same day: `schema.encode_document` stamps a top-level
  `schema_version` onto the bare shape that `info`/`analyze`/`chords`/`lyrics
  --json` and `export --format json` write, so every writer carries the version.
  The stamp is a marker, not a second reader — `from_json` still expects the
  envelope, and `decode` ignores the unknown key as §9 promises.

### Files / modules

`engines/chroma_baseline.py`, `analysis/service.py`, `models/music.py`,
`schema/codec.py`, `tests/integration/`, `docs/`.

### Acceptance criteria

The phase is complete only when: (1) a real MP3 loads; (2) the chord engine
analyzes it; (3) timestamped chord events are produced and cover the file
duration; (4) the result is exposed through `run_analysis()`/the CLI;
(5) an automated test verifies the workflow.

### Dependencies / blockers

None. Phase A's shared decode service is a nice-to-have here, not a blocker
(the engine decodes today).

### Must NOT be considered complete

The manual audit run alone (without a committed test); events without
timestamps; confidence claimed but unmeasured.

---

## 4. Phase C — First End-to-End Vertical Slice **[P] — FIRST PRODUCT MILESTONE**

**Objective:** the whole product path works on one real song, from file to a
chord that changes on screen as the song plays.

```text
REAL AUDIO → chord analysis → timestamped chord events → usable JSON/domain
representation → playback timeline → synchronized chord display
```

**Current status:** `[x]` — reached on 2026-10-07, as a **terminal display**: all
seven acceptance criteria work, verified on a real device and headless in CI.
The display is deliberately the smallest honest surface (one line of text over
`SessionSnapshot`); the desktop window that renders the same frame with widgets
is Phase D and is *not* part of this milestone.

This is the **first product milestone**. It is deliberately small: the first
version does not need perfect chord recognition — it needs to be real,
executable, testable, understandable, integrated, synchronized, and replaceable
by better engines later. Accuracy work happens in Phase I, **after** this works.

### Tasks

- [x] A single application session/service: open file → decode → analyze →
  player → `chord_at(position_seconds)` lookup (binary search over events).
  `app/session.py`: `SongSession` owns the player, keeps the chord events and
  answers `chord_at`/`current_chord`; no Qt, no ML imports
- [x] Playback timeline model: song duration, playhead position, current event
  — `SessionSnapshot` (frozen dataclass returned by `session.snapshot()`)
- [x] Deterministic test of the synchronization logic (fake clock: at t=0..n the
  right chord is returned; boundary and `N`/`?` handling defined). Half-open
  intervals `start <= t < end`; before the first event, inside a gap and at/past
  the last end return `None`; `N` is returned as a claim of silence, not skipped.
  `tests/unit/test_session.py` drives a fake clock; `tests/integration/test_session_integration.py`
  runs the real pipeline (and real playback where a device exists)
- [x] Minimal display surface showing the current chord, updating with
  playback: `app/display.py` (presenter + console renderer + refresh loop) and
  `songlab play`. Deliberately the first slice the Phase D window reuses: the Qt
  view renders the same `DisplayFrame`, which keeps the synchronization logic
  dependency-free and testable
- [x] One scripted demo path: real song file in → chord list + playback + live
  chord out, documented in the README with honest wording (the transcript is
  captured from a generated fixture and says so)

### Files / modules

`src/song_chord_lyrics_analyzer/app/` (`session.py`, `display.py` — session and
presenter layer, no Qt, no ML imports), `cli/commands/play.py`,
`audio/playback.py` (Phase A), `analysis/service.py`, tests.

### Acceptance criteria — **First Product Milestone**

A user can provide a real MP3/audio file and the application can:

1. load it,
2. analyze it,
3. produce timestamped chords,
4. play the audio,
5. determine the current playback timestamp,
6. display the corresponding chord,
7. update the displayed chord as playback advances.

**Until all seven work, the project must not be described as a functional
Chordify/Chord AI-style application.** It is an analysis laboratory.

**Status: all seven work (2026-10-07).** They were verified by running the code:
`songlab play` on a real device while the chord changed with the playhead, and a
headless integration test asserting that every rendered frame carries exactly
the chord the session claims for that position. The claim being made is
*synchronization*, not accuracy, and it is made about a **terminal** display —
the desktop application is Phase D.

### Dependencies / blockers

Depends on Phase A (playback) and Phase B (chord pipeline). No research task
may block this phase.

### Must NOT be considered complete

Analysis without playback; playback without synchronization; a demo that only
works on one hard-coded file; unverified claims in the README.

---

## 5. Phase D — Minimal PyQt6 GUI **[P]**

**Objective:** the smallest usable desktop application around the Phase C
vertical slice.

**Current status:** `[x]` — the minimal window landed **2026-10-08** as
`songlab gui`, verified by running it (offscreen, `QT_QPA_PLATFORM=offscreen`) on
a generated song: the waveform timeline, the chord strip and the playhead are
drawn, the transport plays/pauses/stops/seeks, and every refresh shows exactly
the chord `chord_at()` claims for that position - on a real device too
(`tests/integration/test_gui_integration.py`).

### Tasks

- [x] PyQt6 dependency (optional extra; core stays dependency-free) — license
  noted in `docs/LICENSE_AUDIT.md` (GPL compatible). `pyproject.toml` extra
  `gui`; `gui/` imports Qt lazily, so a Qt-free install still runs every other
  command and `songlab gui` reports a dependency error with the install hint
- [x] Main window consuming the **application session layer only**
  (hard rule: GUI never imports librosa, engines, numpy, or `analysis/` internals).
  `gui/main_window.py` imports `app/` (session, display frame, timeline, summary)
  and Qt, nothing else
- [x] Minimal Viable GUI, exactly:
  - [x] open an audio file (dialog + an optional file argument)
  - [x] play / pause
  - [x] seek (click/drag on timeline, plus back/forward actions and arrow keys)
  - [x] show current time (and track length)
  - [x] show detected chords (a big label for the playhead, a band per event in
    the timeline strip)
  - [x] synchronize chord display with playback (one `snapshot()` per timer tick,
    turned into the same `DisplayFrame` the terminal display renders)
- [x] Show key, tempo, engine name and provenance summary (cheap, already
  available): `app/summary.py` produces the rows, `gui/analysis_panel.py` shows
  them, skipped/failed engines included
- [x] Waveform/timeline rendering from Phase A peak data: `audio/peaks.py`
  (min/max per bucket, frame-aligned, no numpy import) reached through
  `SongSession.waveform_peaks(buckets)`, cached per resolution and redrawn on
  resize; the playhead and the bands are placed with the same presenter
  (`app/timeline.py`) the widget uses
- [x] Headless test strategy for GUI logic (logic in plain-Python presenters;
  Qt widgets thin and tested with `QT_QPA_PLATFORM=offscreen`):
  `tests/unit/test_gui_main_window.py` (fake player + fake clock),
  `tests/integration/test_gui_integration.py` (real engine, real file, real
  device where one exists) and `tests/unit/test_gui_command.py`. CI installs the
  `gui` extra in the DSP job and runs them offscreen; the core matrix stays
  Qt-free

- [x] Manual launch verified by the user on MX Linux 25 (2026-10-18): the
  window opened an MP3, drew the waveform, the lyrics panel, the analysis
  information and the changing chords during playback (user-reported; see §1).
  The launch commands and screenshot are in the README.

### Files / modules

New `src/song_chord_lyrics_analyzer/gui/` (`main_window.py`, `timeline.py`,
`analysis_panel.py`, `__init__.py`), new presenters `app/timeline.py` +
`app/summary.py`, new `audio/peaks.py`, `cli/commands/gui.py`, plus `app/` from
Phase C. Two modules the plan (`docs/GUI_REQUIREMENTS.md`) listed were folded in
rather than split: there is no `gui/player.py` because the window drives the
session's existing `SoundDevicePlayer` instead of adding a Qt Multimedia
backend, and no `gui/waveform.py` because the waveform, the chord strip and the
playhead share one widget (`gui/timeline.py`) and one `x_at` mapping.

### Acceptance criteria

A user can launch the app, open a song, see its waveform timeline, play it,
seek, and always see the chord for the current position. **Met on 2026-10-08**
(`songlab gui`; verified offscreen, on a generated song the real engine
analyses, and on a real output device).

### Dependencies / blockers

Phases A + C. Nothing else.

### Must NOT be considered complete

A window that only loads files; widgets importing engines directly; the full
feature list below — that is `[F]` work, added after the minimal GUI works.

### Later GUI features (progressive, `[F]`)

Delivered from this list, in order: the lyrics view (2026-10-09, `app/`
lyrics-view presenter + `gui/lyrics_view.py`, active segment and active word on
the same snapshot the chord label reads; see `docs/GUI_REQUIREMENTS.md` §5.1);
chord/lyric editing with undo/redo (2026-10-10..12); transpose and chord
simplification (2026-10-13); the Export document... save dialog over the
Phase H exporters (2026-10-13); and the **chord-over-lyrics chart** (2026-10-21,
`app/chord_lyrics.py` + the rewritten `gui/lyrics_view.py`: each chord above the
timed word it changes on, instrumental gap rows, active chord highlighted). Still
open: translations. The window's layout is already prepared for them (`app/`
produces the data, the widgets only render).

---

## 7. Phase E — Lyrics Integration adopted **[P]**

**Objective:** the recorded lyrics research became a real, registered
`ParakeetLyricsEngine` through `onnx-asr`: timestamped words from real audio,
chunked at 20 s, `unknown` confidence, model provenance recorded.

**Current status:** `[x]` — adopted on 2026-10-08; all six tasks above are
`[x]` and the engine flows through `run_analysis()`, `songlab lyrics` and both
front ends. The investigation is preserved in `docs/ENGINE_COMPARISON.md` (the
English result: WER 0.3722 vs 0.3799; RTF 0.20 vs 0.95) and the phase-4
open-questions are listed there.

### Tasks — all `x`

- [x] Lyrics engine adapter implementing `LyricsEngine` (`engines/lyrics_parakeet.py`),
  injected transcriber so the pipeline is testable without a model
- [x] Chunked transcription pipeline (`engines/lyrics_chunking.py`): windowing,
  timestamp reassembly, overlap handled by the documented "earlier window wins"
  rule
- [x] Register the engine; `songlab lyrics` command; `run_analysis()` gains a
  lyrics step with the same honest skipped/failed status handling
- [x] Integration test on committed fixture audio (`samples/vocadito_6.wav`,
  CC-BY-4.0): real weights and real voice on the committed sample, structural
  honesty only (no new WER claim)
- [x] Honour the contract: `README.md` and `docs/GUI_REQUIREMENTS.md` updated;
  `utils/text.py` holds the shared English agreement helper
- [x] Remaining phase-4 questions: overlap semantics, second candidate, language
  tag

### Files / modules

`engines/lyrics_chunking.py`, `engines/lyrics_parakeet.py`,
`cli/commands/lyrics.py`, `utils/text.py`, `analysis/service.py`,
`pyproject.toml` (optional `lyrics` extra), `tests/`; docs `ENGINE_COMPARISON.md`,
`README.md`, `CHANGELOG.md`, `DEPENDENCY_MATRIX.md`, `LICENSE_AUDIT.md`.

### Acceptance criteria

A real audio file produces timestamped lyric words through the same application
service and CLI pattern as chords, with model provenance (name, license,
version) recorded in the document.

### Dependencies / blockers

Optional DSP extra (onnx-asr, onnxruntime, huggingface-hub, numpy, librosa,
soundfile) — must stay optional; core and its tests never require it. Download
of the model happens once, on first use, into the Hugging Face cache, and
`test_lyrics_integration.py` never triggers it.

### Must NOT be considered complete

WER numbers from the old harness; an adapter that only runs on one machine;
un-timestamped transcripts; a `lyrics` extra that can be installed without
decoding (numpy/librosa), which the decoder and the engine both need.

**Pre-adoption status (history):** research measured, models/libraries known,
`engines/lyrics_chunking.py` (windowing, reassembly) and `metrics/lyrics.py`
existed; `LYRICS -> []` until **2026-10-08**, when `ParakeetLyricsEngine` was
registered through `onnx-asr` (MIT runtime, CC-BY-4.0 weights), chunked at 20 s,
behind the `lyrics` extra.

### Tasks

- [x] Lyrics models (`models/lyrics.py`) and WER/CER + word-timestamp metrics (`metrics/lyrics.py`)
- [x] Research already done (see §15 — do not repeat): Parakeet-1B-v3 via
  `onnx-asr` beats faster-whisper small on English (WER 0.3722 vs 0.3799);
  both are MIT; **long-audio chunking (~20 s windows) is mandatory**;
  stems do **not** improve transcription by default
- [x] Lyrics engine adapter implementing `LyricsEngine` (`engines/lyrics_parakeet.py`),
  injected transcriber so the pipeline is testable without a model
- [x] Chunked transcription pipeline (`engines/lyrics_chunking.py`: windowing,
  timestamp reassembly, overlap handled by the documented "earlier window
  wins" rule)
- [x] Register the engine; `songlab lyrics` command; `run_analysis()` gains a
  lyrics step with the same honest skipped/failed status handling
- [x] Integration test on committed fixture audio (`samples/vocadito_6.wav`,
  CC-BY-4.0) with the real weights when the local cache holds them; structural
  honesty only (no new WER claim)
- [x] Honest output: word timestamps carry `unknown` confidence unless measured;
  `lyrics_label()` keeps the two front ends in agreement

### Files / modules

New `engines/lyrics_chunking.py`, `engines/lyrics_parakeet.py`,
`cli/commands/lyrics.py`, change in `analysis/service.py`, new
`utils/text.py` (the English agreement helper), `pyproject.toml` (optional
`lyrics` extra), `tests/`.

### Acceptance criteria

A real audio file produces timestamped lyric words through the same application
service and CLI pattern as chords, with model provenance (name, license,
version) recorded in the document.

### Dependencies / blockers

Optional DSP extra (onnx-asr, onnxruntime, huggingface-hub, numpy, librosa,
soundfile) — must stay optional; core and its tests never require it. No
dataset research required. The heavy model downloads on first use; tests never
trigger it.

### Must NOT be considered complete

WER numbers from the old harness; an adapter that only runs on one machine;
un-timestamped transcripts; a `lyrics` extra that can be installed without its
decoding stack.

---

## 7. Phase F — Synchronized Lyrics + Chords **[P]**

**Objective:** show lyrics and chords together on the same playback clock.

**Current status:** `[x]` — the clock-sharing work landed and was tested
(2026-10-10, on top of the 2026-10-09 lyrics view): `SongSession.lyric_at()` /
`word_at()` answer the lyrics layer exactly the way `chord_at()` answers the
chords layer, and the window's refresh feeds both widgets from one snapshot.
The external timed-text alignment landed 2026-10-14: `alignment/lrc.py` and
`alignment/srt.py` parse a `.lrc`/`.srt` file into the same canonical
`LyricSegment` rows the lyrics engine produces, `songlab analyze --lyrics-from
FILE` takes the layer from a file instead of the engine, and the window loads
one with Ctrl+L (`with_lyric_base` swaps the tape's lyric base, keeping the
chord work and persisting the new base to the Phase G sidecar). The
**chord-over-lyrics chart** landed 2026-10-21: every chord is seated above the
timed word it starts on, instrumental gaps get chord-only rows, the active
chord is highlighted, and flat keys are respelled for display. The **plain-text
chart import** landed 2026-10-27: Edit → Load chord chart... uses the chart's
chords and lyrics while taking their times from the detected chord sequence and
the transcript's timed words.

### Tasks

- [x] Lyric timeline model aligned to the same position clock as chords
  (`app/lyrics_view.py` presenters, 2026-10-09)
- [x] `lyric_at(position)` + `word_at(position)` alongside `chord_at(position)`
  in the session layer (`app/session.py`, 2026-10-10); the same half-open
  `start <= position < end` coverage, the same `None` = "no claim"
- [x] GUI: lyric line display synchronized with playback (active word
  highlighted when word timestamps exist). The widget takes the session's
  answers (`set_active(segment, word)`) and decides nothing about the clock
- [x] Alignment rules when lyrics come from an external timed-text file
  (`.lrc`/`.srt`) — `alignment/lrc.py` + `alignment/srt.py` in the shared
  `alignment/` package (2026-10-14), one entry point (`parse_timed_text`)
  for both front ends:
  * LRC: `[mm:ss.xx]` with the fraction padded **on the right** to ms,
    repeated stamps repeating the text, `[offset:±ms]`, metadata tags
    consumed as annotations, enhanced A2 word stamps, a line's `end` = the
    next line's `start`, the last line open-ended, untimed lines kept but
    never active
  * SRT: `HH:MM:SS,mmm --> HH:MM:SS,mmm` (dot also accepted) with trailing
    position markers ignored, internal line breaks joined into one display
    line, empty blocks skipped as silence markers, inverted timings reported
  * CLI: `songlab analyze --lyrics-from FILE` replaces the lyrics layer
    (the file wins) and records it in the step summary + provenance
  * GUI: the Edit menu's "Load lyrics from file..." (Ctrl+L) swaps the
    lyric base; the file's lines are saved by Ctrl+S like any other edit
- [x] Tests: fake-clock synchronization for both streams; boundary cases
  (`TestLyricLookup` in `tests/unit/test_session.py` pins the same edges as
  `chord_at`; `TestTheLyricsViewFollowsTheSameClock` asserts both front-end
  views read one snapshot)
- [x] **Chord chart over the lyrics** (2026-10-21): `app/chord_lyrics.py` is the
  pure presenter (`chord_lyric_lines`, `ChordLyricLine`, `PlacedChord`). A chord
  is seated above the timed word whose `start <= chord.start < end`; without
  word timestamps the line falls back to a proportional column; a chord that
  starts in an instrumental gap gets its own chord-only row, grouped by the
  lyric line it precedes; a chord merely spanning into a line is not repeated;
  two chords on one word are nudged apart rather than overwritten; canonical
  labels are respelled for a flat key through `normalization/spelling.py`.
  `gui/lyrics_view.py` draws each row as one monospace chord line plus one lyric
  line in the same `QTextBlock`, so the right-click-to-display-index mapping the
  lyric commands rely on stays exact. Tests: 16 presenter tests
  (`tests/unit/test_chord_lyrics.py`), 17 offscreen widget tests
  (`tests/unit/test_gui_lyrics_view.py`) and a window test that the chart is
  built from the effective layers (`TestChordsAboveTheLyrics`)
- [x] **Plain-text chart import** (2026-10-27): `app/chart_import.py` parses the
  chart's chord sequence, chord columns and sung lines. A chord written above a
  lyric word takes that word's start; instrumental runs are distributed between
  the surrounding anchors, and every chart chord gets a positive slot. Chart
  words are aligned to the transcript's timed words, keeping the chart text and
  interpolating unmatched words; the detected sequence is the fallback when the
  chart has no word anchors. Title/artist lines before the first section/chord
  line are excluded. The window's
  **Edit → Load chord chart...** (`Ctrl+Shift+L`) replaces both bases through
  `with_chart_bases` (old commands dropped), reports unmatched layers in the
  status bar, and saves the chart base to the sidecar. Tests: 14 importer
  tests (`tests/unit/test_chart_import.py`) and 6 window tests
  (`TestImportingAChordChart`). Verified on the private 5:27 song: 86 timed
  chart chords, 36 correct lyric lines, 83/182 chart words anchored to the
  transcript (2026-10-27). Limitation: the timing is column/word-based, not
  beat-level; chart sections are not used for timing, and the chart file path is
  not yet recorded in provenance.

### Acceptance criteria

While a song plays, both the current chord and the current lyric line update in
sync, from one timestamped source of truth. **Met for the engine-transcribed
lyrics on 2026-10-10, for an external `.lrc`/`.srt` lyric base on 2026-10-14,
for the chord-over-lyrics chart on 2026-10-21, and for the plain-text chart
import on 2026-10-27** (the parsed rows carry
`start`/`end` in the same clock the chord layer uses, the session's `lyric_at`
does not care where they came from, and the chart's placed chords read the same
effective layers the playback clock does). The chart positions chords at the
word whose onset the chord changes on; a chord change inside a long held word
therefore lands on that word, which is the resolution the word timestamps
support. It is **not** a claim of sub-word or beat-level alignment.

### Dependencies / blockers

Phases C + D + E.

### Must NOT be considered complete

Lyrics shown without timestamps; two unsynchronized position clocks.

---

## 8. Phase G — Editing and User Corrections **[P]**

**Objective:** the user can fix what the engines got wrong, without losing the
original analysis.

**Current status:** `[x]` — the chord-editing core landed 2026-10-10
(`app/editing.py`: command-pattern edits over an immutable engine base,
`SetChordLabel`/`SplitChord`/`MergeChords`/`TrimChord`/`DeleteChord`/
`InsertChord` + a `CommandStack` undo/redo tape; the window edits the chord
under the clicked position and undoes/redoes with the standard shortcuts)
and the edited layer persists 2026-10-11 (`app/persistence.py`: a sidecar
`song.songlab.json` storing the engine base + the ordered commands, replayed
through `rebuild_stack()` on load with the same validation as a live push;
wired to the window as `Ctrl+S` + an auto-replay on `open_file`; a corrupt or
stale sidecar is reported and the engine layer kept). Lyric editing landed
2026-10-12 and closes the phase: four commands (`SetLyricText` /
`SetLyricTiming` / `DeleteLyric` / `InsertLyric`) over an immutable lyric
base, riding the **same** undo tape as the chords, so one `Ctrl+Z` walks back
through both layers in the order they were made. Lines are addressed by
their *display index* - a line may carry no timestamp at all - and
`effective_lyrics()` re-establishes display order after every command, so an
index always resolves against exactly the list it was validated against,
live and when a saved tape replays. The sidecar stores the engine lyric base
beside the chords (`edits_version` stays `"1"`: a pre-lyric sidecar loads
with an empty lyric layer, and a build that predates the commands rejects a
sidecar containing one loudly instead of dropping it). The timeline context
menu now offers all six chord commands (edit/split/trim-start/trim-end/
merge/delete/insert, each addressing the chord under the click) and the
lyrics view's context menu the five lyric ones (edit text/set start/set
end/insert line/delete line, addressed by the line under the click, with
enable states from the effective layer - "set end" waits for a start);
closing with unsaved edits offers Save/Cancel/Discard - the answer is exact,
since the tape is compared with the last save, so undoing back to the saved
state closes silently, and a lyric edit counts as unsaved like any chord
edit.

### Tasks

- [x] Editable document layer: user edits are a separate overlay over the
  engine output (raw engine results are never overwritten — provenance stays).
  `CommandStack.base` returns the engine layer untouched after any edit;
  user-produced events carry `source="user"`/`"user-merge"`
- [x] Chord editing: change label, split/merge/trim/delete/insert — six
  commands exist and are tested (vocabulary frozen 2026-10-11); all six are
  in the timeline context menu (2026-10-11), each addressed by the chord
  under the click, with enable states computed from the effective layer
- [x] Lyric editing: correct words and timings (`SetLyricText` replaces a
  line's words, `SetLyricTiming` moves a boundary or gives an untimed line a
  start, `DeleteLyric`/`InsertLyric` cover the structural fixes; the engine's
  word timestamps ride along as evidence and the engine layer itself is never
  touched. Lines are addressed by display index; the view's context menu
  offers every command. Per-word (re)editing is deliberately *not* in this
  vocabulary - it needs word addressing and would extend the schema, so it is
  a later, separate decision)
- [x] Undo/redo command stack (`CommandStack`: push/undo/redo, redo tape
  discarded on a new push, a failed push leaves the tape as it was)
- [x] Persistence of the edited document (`app/persistence.py`, 2026-10-11:
  `save_edits()`/`load_edits()`/`rebuild_stack()` over a sibling
  `song.songlab.json` that stores the engine chords + the ordered commands in
  canonical JSON; the engine layer is recoverable from the file untouched, a
  stale command fails loudly on replay, the edits format has its own
  `edits_version: "1"`. Wired into the window the same day: `Ctrl+S` /
  "Save Edits" writes the sidecar, `open_file` replays it automatically, and
  a corrupt or stale sidecar is reported with the engine layer kept)
- [x] GUI integration (edit from the timeline): the timeline's context menu
  offers "Edit chord here..."; Undo/Redo on `Ctrl+Z`/`Ctrl+Shift+Z`; the chord
  label and the strip redraw from the effective layer
- [x] Tests: command-level undo/redo, overlay round-trip, persistence —
  `tests/unit/test_editing.py` (82 tests, Qt-free: the chord vocabulary, the
  lyric vocabulary, the fold and the one-tape-both-layers behaviour),
  `tests/unit/test_persistence.py` (25 tests: round-trip of both layers,
  engine-layer recoverability, provenance, loud stale/corrupt rejection,
  pre-lyric sidecar compatibility), and the GUI flow in
  `tests/unit/test_gui_main_window.py::TestEditingTheChordLayer`,
  `TestPersistingTheEdits` and `TestEditingTheLyricsLayer` (14 tests: menu
  enable states, every lyric command, the mixed-layer undo order, the
  delete-refill gap flow, save/reopen of lyric edits, the widget-to-menu
  chain; offscreen, dialogs mocked) plus `tests/unit/test_gui_lyrics_view.py::TestTheRightClickNamesTheLine`
  (3 tests: the right-click to display-index mapping)

### Acceptance criteria

A user can correct a chord and a lyric line, undo and redo those edits, save,
reload, and the engine's original output is still recoverable.

### Dependencies / blockers

Phase C (document + session layer); GUI parts need Phase D.

### Must NOT be considered complete

In-place mutation of engine output; edits lost on reload; no undo.

---

## 9. Phase H — Transpose, Simplification and Export **[P]**

**Objective:** musically useful transformations and export of the analysis.

**Current status:** `[x]` — **Delivered 2026-10-13.** Library transposition plus
the whole-document `TransposeDocument` / `SimplifyDocument` commands in
`app/editing.py` (GUI "Transpose all chords..." / "Simplify all chords" and the
CLI's flag-first `songlab export --transpose/--simplify`, both riding the edit
tape), and the `export/` package with `songlab export` (JSON / ChordPro /
Markdown) that honours the saved sidecar so what is exported is what was
edited.

### Tasks

- [x] Library-level transposition (`normalization/chords.py`)
- [x] Transpose workflow: apply semitone offset to the whole document (CLI flag
  first, GUI control after); chords displayed/transposed, originals preserved
- [x] Chord simplification: reduce extensions/alterations to simpler voicings
  (define the reduction table, test it, expose as a workflow) — reduced on top
  of the documented `contract_chord_label()` table in `normalization/chords.py`
- [x] `songlab export` command with formats: canonical JSON (exists), ChordPro,
  simple Markdown/tabular; exporters live in `export/`, never in the model
- [~] Round-trip tests: export → parse → same data — **honest scope, corrected by
  the 2026-11-02 completeness audit (section 12).** The canonical JSON document
  does round-trip and is tested that way (`tests/unit/test_codec.py`,
  `tests/integration/test_analysis_e2e.py`: write, reload, same model). ChordPro
  and Markdown have **no reader** in the package — `export/chordpro.py` and
  `export/markdown.py` expose `render_*` only — so their tests assert the rendered
  text (chord placement, line folding, timing), not a parse back to the model. The
  `[x]` here claimed more than the tests establish; the reader that would make it
  true is Phase L work, not a re-marking of this line.

### Acceptance criteria

From one analyzed song the user can transpose it, simplify its chords, and
export the result to at least JSON + ChordPro, with tests.

### Dependencies / blockers

Phase C for the document workflow; nothing else.

### Must NOT be considered complete

Exporters that write fields the model does not have; simplification without a
documented, tested rule table.

---

## 10. Phase I — Accuracy Improvements and Additional Engines **[P] — PRIMARY**

**Objective:** improve chord recognition **above everything else in this
roadmap**. Since 2026-11-02 this phase is the project's first priority: the
product's usefulness is the accuracy of the chords it reports, and no packaging,
backlog or parity work may take its place. Improvements are still only adopted on
evidence — "do not simply add more algorithms without measuring whether they
improve the actual results".

**Current status:** `[~]` — measured with the committed harness: **CSR 0.6312**
(raw) / **0.6384** (triad-reduced), segment overlap 0.8454, change-F1 0.8553 on
180 GuitarSet comping takes (2026-10-27, `docs/ENGINE_COMPARISON.md` §8). The
previous front end measured 0.6121 / 0.6183 (2026-10-20, §7), the first scoring
step measured 0.6283 / 0.6356 (2026-10-21), 0.6029 with the front-end default
before that (2026-10-19, §2), and the previously cited 0.4260 did not reproduce
and is retired. No second chord engine is registered. A
read-only audit of the implementation was completed on **2026-10-18** and its
prioritized plan is [`docs/CHORD_DETECTION_AUDIT.md`](docs/CHORD_DETECTION_AUDIT.md);
P1 (the measurement harness), P2 (per-chord confidence) and P3 (the front-end
sweep) are implemented, and the 2026-10-21 template/compression pass is the
measured continuation of P3. P4–P6 and P8 are not, and P7 was measured rather
than built: its shared-decode half was priced and rejected, its shared-chroma
half is blocked on key ground truth (2026-11-01, task below). The ceiling of this
template pipeline has been probed: a 109-class CRNN reference available only as
`external/` weights scored **0.2555 triad CSR** raw on 30 takes and was
rejected, a held-out MLP on chroma context added only ~0.03, and the open
pretrained chord models that do score well are non-commercial (BTC /
Isophonics-derived weights are CC-BY-NC-SA), so the next real step is a
licence-clean learned engine with its own held-out measurement, not another
template tweak.

**Re-audited 2026-11-02** for the accuracy-first strategy
([`docs/CHORD_DETECTION_AUDIT.md`](docs/CHORD_DETECTION_AUDIT.md) §16). Two
structural gaps decided the queue below, and both are verifiable omissions rather
than opinions: **no numeric acceptance criterion for chord recognition exists
anywhere in the project** — the criteria in this file were procedural ("every
change ships with before/after numbers"), which grades the process and not the
product, and `docs/BENCHMARK.md` defines metric *formulas* and no target — and
**the measured loss has never been decomposed**: how much of the gap to 1.0 is a
wrong root, a wrong quality, a boundary that moved, or a wrong no-chord decision
is not known, even though the harness already writes the per-take columns needed
to answer it. Everything else about the current state follows from those two: one
corpus, one instrument, one annotation convention, measured on Linux, pinned by a
vector that transcribes §8 instead of re-measuring it.

### Tasks

**Ordered 2026-11-02.** A0–A4 come first because they define and locate the
problem; P4–P8 are the candidate fixes and each must now be justified by the
answer A1 produces, not picked because it is next in a list.

- [ ] A0 — **ratify a numeric acceptance bar for chord recognition** (the table
  in "Acceptance criteria" below is the proposal). Until a number is agreed, this
  phase cannot reach `[x]` and no accuracy work can be called finished. Ratifying
  it is a decision plus a command, not a measurement: `scripts/chord_benchmark.py`
  on the pinned set, with `benchmark/regression.py` as the regression gate.
- [ ] A1 — **decompose the measured error** on the 180 pinned takes: classify
  every reference-vs-hypothesis disagreement as wrong root, wrong quality (given
  the root), boundary/timing, false no-chord vs missed chord, and report the share
  of the lost CSR per class plus the per-class rate. Deliverable: a script in
  `scripts/` reusing `evaluation/guitarset.py` and `metrics/segmentation.py`, its
  output recorded in `docs/ENGINE_COMPARISON.md` with environment and date, and
  unit tests on synthetic label pairs. The largest class names the next task; a
  fix that does not address a class is not adopted on CSR alone.
- [ ] A2 — **a second, licence-audited chord corpus** with real audio, beyond the
  GuitarSet solo-guitar comping case. Requirement: a redistribution-or-local-use
  licence recorded in `docs/LICENSE_AUDIT.md` first, a pinned manifest in the same
  SHA-256 shape as `tests/fixtures/guitarset_comp_manifest.json`, an entry in
  `docs/DATASET.md`, and a scored vector on it. Without this, every generalisation
  claim (mixed sources, other instruments, other genres) is untested and must not
  be made.
- [ ] A3 — **re-measure and re-pin the reference vector from a live run** against
  the real GuitarSet audio, so that `benchmark/reference/chroma_baseline-instructed.json`
  holds a measurement and not a transcription of §8 (its own `notes` say so today),
  and so that the 180-take comparison path is exercised on a real corpus rather
  than on synthetic ones. Blocked on downloading the 462 MB corpus, which is a
  maintainer decision, not an autonomous step.
- [ ] A4 — **a real-mix long-file check of the windowed chord pass**: the seam
  rules are tested (section 13) but only on a generated 480 s fixture; measure
  whether a seam on real audio invents or drops a boundary, and report the wall
  time and memory of a full-length song in the GUI. This is the accuracy-relevant
  half of the long-song work; the memory half is already delivered.

Delivered and measured history — do not re-run these without a new question:

- [x] Read-only chord-detection audit (2026-10-18): traced the real path from
  decode → CQT chroma → 24 triad templates → Viterbi → segments → GUI, mapped
  the tests, and recorded evidence-based proposals without changing code
  (`docs/CHORD_DETECTION_AUDIT.md`)
- [x] P1 — reproducible comparison harness and fixed reference set, so every
  later chord change reports before/after on the same audio (audit §10 P1):
  `scripts/chord_benchmark.py` + the SHA-256-pinned
  `tests/fixtures/guitarset_comp_manifest.json` (180 comp takes) + the scoring
  and corpus modules `evaluation/guitarset.py`, with the full audit §11 vector
  written to `per_take.jsonl` / `aggregate.json` / `aggregate.md`; the
  generated-fixture and synthetic-corpus paths are tested offline in
  `tests/unit/test_chord_benchmark_harness.py`
- [x] P2 — per-chord confidence from the score margin (the Phase B task),
  exposed in the existing panel/tooltip without inventing a probability
  (audit §10 P2). Implemented 2026-10-20: `segment_margins()` +
  `margin_confidence()` in the engine, the logistic fitted on 90 GuitarSet takes
  and measured on the other 90 (Brier 0.1436, ECE 0.0206), the full calibration
  and risk–coverage tables in `docs/ENGINE_COMPARISON.md` §6, the refit command
  `scripts/chord_benchmark.py --fit-confidence`, and the Viterbi run now records
  `match_threshold_used`/`smoothing_window_used` instead of implying either
  shaped the labels. The 180-take per-take vector is bit-for-bit unchanged
- [x] P3 — front-end robustness measured one variable at a time (tuning, HPSS,
  energy gate, CENS); no change is adopted without the P1 numbers
  (audit §10 P3). Implemented 2026-10-20: `front_end_settings()` /
  `compute_chroma()` expose four independent options, the harness gained
  `--option KEY=VALUE` and records what ran, and the full sweep is measured on
  the same 180 takes (`docs/ENGINE_COMPARISON.md` §7). `tuning=zero` gained
  +0.0092 CSR (paired, ±0.0033) against the old default and **was adopted**;
  HPSS (−0.0139, 6.7× the CPU) and CENS (−0.0554) were measured and rejected;
  the −40 dB energy gate is within noise and stays an option.
- [x] P3 continuation — **harmonic templates, sqrt chroma compression and a
  0.50 s minimum-duration merge**, measured 2026-10-21..27 on the same 180 takes
  (audit §10 P3/P6 groundwork). `frame_scores`/`decode_labels` gained
  `weighting`, `apply_feature_transform()` gained `sqrt`/`log`, and the
  engine gained `min_segment_seconds`. The adopted defaults are
  `weighting="harmonic"` (root/third/fifth 1.00/0.95/0.85, opposite third
  −0.35), `feature_transform="sqrt"`, `change_penalty=0.40` and
  `min_segment_seconds=0.5`: **CSR 0.6121 → 0.6312**, triad 0.6183 → 0.6384,
  overlap 0.8343 → 0.8454, change F1 0.8296 → 0.8553, median boundary error
  0.168 → 0.158 s. The paired CSR gain against the previous defaults is +0.0191
  (95 % CI +0.0052..+0.0329). The first scoring step used 0.30 s and measured
  0.6283 / 0.6356; moving to 0.50 s after the real-song chart check gained a
  further +0.0028 ± 0.0007 CSR and +0.0206 change F1 without losing a chart
  chord. The binary templates and raw chroma remain selectable, and the
  confidence logistic was refitted on the new margin scale (Brier 0.1485, ECE
  0.0363). The change penalty was re-swept, closing the 2026-10-20 open item.
- [ ] P4 — bass-aware feature and slash-chord output, reported separately from
  the triad label (audit §10 P4)
- [ ] P5 — duration-aware transition model (and metrical alignment once a beat
  engine exists), scored on boundary error and change F1 as well as CSR
  (audit §10 P5)
- [ ] P6 — vocabulary phase 2 (sevenths, suspensions, diminished/augmented)
  only after the triad baseline is measured; accept only if the triad-reduced
  view does not regress (audit §10 P6)
- [ ] P7 — share decode/chroma work between the chord and key engines; output
  equality first, latency/memory second (audit §10 P7). **Measured 2026-11-01 on
  Windows 10 (`scripts/analysis_cost_probe.py`, `docs/ENGINE_COMPARISON.md` §10):
  the premise is real — three identical decodes per run — and the shared-decode
  half is not adopted, because the repeats it could remove cost 0.05–0.20 s of a
  steady-state run and 0.9–2.8 % of a cold one; its memory half is unassessed
  (peak RSS is POSIX-only). The shared-chroma half is the bigger prize (~0.55 s
  per warm 120 s run, the whole key step) and stays open, blocked on committed
  key ground truth: with the adopted defaults the two engines' `chroma_cqt`
  requests differ only by `tuning`, so sharing the array changes the key label
  and must be scored before it lands (`docs/DATASET.md`: the key category is not
  yet a versioned dataset entry).
- [ ] P8 — evaluate an alternative engine behind `ChordEngine` only after
  P1–P3 and a licence audit (audit §10 P8)

- [x] Keep `docs/ENGINE_COMPARISON.md` as the measurement record; every
  accuracy claim states environment + date. **Traceability gap found by the
  2026-10-18 audit** (the file began at section 4, so the chord measurement's
  method table was missing): sections 1–3 were restored on 2026-10-19 together
  with the method table, the three measured runs and the note that retired the
  0.4260
- [~] Baseline improvements with measured deltas — **partly delivered**
  2026-10-21 (harmonic templates, sqrt chroma, minimum-duration merge; above).
  Not delivered: bass templates/slash output (P4), duration-aware transitions
  (P5) and the phase-2 vocabulary (P6). The conservative seventh pass that was
  measured emitted sevenths on 21–53 % of the duration against a 13.4 %
  reference, so it was not adopted; a hierarchical decision needs the bass
  evidence first.
- [ ] Candidate engines (Chordino via Sonic Annotator, madmom, Guitariz-style
  ensembles, `external/` references) evaluated only with a **product reason**:
  "users need X and the baseline fails X". A first probe on 2026-10-21
  measured the 109-class ONNX reference under `external/Guitariz` at 0.2555
  triad CSR on 30 takes (raw argmax, no smoothing), which is far below the
  registered engine; it is **not** adopted and no `external/` code or weights
  are used by the package. The strong public BTC checkpoints are
  CC-BY-NC-SA and conflict with this project's licence, so they are out.
- [ ] **Learned chord engine, licence-clean and measured held out** — the
  measured next step for accuracy. Requirements: a dataset whose audio and
  annotations permit redistribution or local use, a training script that lives
  in `scripts/` (not the wheel), a compact inference path behind
  `ChordEngine` with an optional extra, the same 180-take (or better,
  multi-corpus) before/after vector, and a documented train/held-out split.
  Do not ship weights of unknown provenance and do not train and test on the
  same takes. GuitarSet (CC BY 4.0) is a legitimate start for the solo-guitar
  case; full-mix generalisation needs a second, licence-audited corpus.
- [ ] Fusion only if single-engine accuracy plateaus (`fusion/` is reserved)

### Acceptance criteria

The procedural rule, unchanged: any accuracy change ships with before/after
numbers on the same evaluation set; engines ship behind `ChordEngine`, registered
and selectable via `--engine`.

**Proposed 2026-11-02 — a numeric bar, awaiting ratification (task A0).** These
are *targets*, not results: every "now" figure is the measured 2026-10-27 vector
in `docs/ENGINE_COMPARISON.md` §8, and none of the "bar" values has been reached.
The verifier is the same in every row: `scripts/chord_benchmark.py` on the
SHA-256-pinned 180-take instructed set, judged by `benchmark/regression.py`, with
the environment and date recorded in the measurement file.

| Measure | Bar | Now | What it guards |
| --- | --- | --- | --- |
| triad-reduced duration CSR | ≥ 0.70 | 0.6384 | the product's headline chord correctness |
| duration CSR (all 25 labels) | ≥ 0.68 | 0.6312 | phase-2 vocabulary paying for itself |
| triad-reduced CSR after a vocabulary change | no loss > 0.005 | — | P6 cannot trade the simple view away |
| segment overlap | ≥ 0.86 | 0.8454 | how long each chord is held |
| change-detection F1 | ≥ 0.88 | 0.8553 | where the changes land in time |
| median boundary error (ref→hyp) | ≤ 0.12 s | 0.158 s | the frame the listener sees |
| held-out ECE of per-chord confidence | ≤ 0.05 | 0.0363 | the label stays honest as the scorer changes |
| second corpus, triad CSR | reported, bar set with the corpus | not measurable | generalisation — needs task A2 first |

Phase I is `[x]` only when the four CSR/overlap/F1/boundary rows are met in a run
recorded with its environment and date, the error decomposition (A1) is on file
and shows no unowned dominant class, and the second-corpus row carries a real
number rather than an absence. `docs/ENGINE_COMPARISON.md` §8 remains the single
measurement record. **No row may be satisfied by a confidence score: calibrated
confidence is reported alongside accuracy and never instead of it.**

### Must NOT be considered complete

Unmeasured "improvements"; new engines that are not registered/tested;
benchmark growth that does not serve the product.

---

## 11. Phase J — Benchmarking and Validation **[S] — the gate**

**Objective:** decide, by measurement, whether Phase I's accuracy work and Phase
L's completeness work are true. Validation stays a **service** — it is never the
main development path, and no new dataset or metric may be built for its own
sake — but since 2026-11-02 it is the gate: a claim of "complete", "stable" or
"accurate" without a run recorded here is not a claim this project accepts.
Priority C of section 0 is this phase plus the integration half of Phase L.

**Current status:** `[x]` (infrastructure) / `[~]` (coverage of the product path —
a committed real-file case exists since 2026-11-01; the fixed chord set now has
a committed accuracy vector that every harness run is checked against
(2026-11-01), though that vector transcribes §8 rather than re-measuring it)

### Tasks

- [x] Metric suite (`metrics/`, `evaluation/`) with pinned oracles
- [x] `songlab benchmark` with kind-agnostic runner and `--engine`
- [x] Dataset policy + GuitarSet adoption (`docs/DATASET.md`)
- [x] Benchmark case for the real-file product workflow (feeds Phase B/C tests)
  (2026-11-01): `samples/cases/vocadito_6.json` — a real committed recording (the
  CC-BY-4.0 vocadito excerpt, 23.832 s), the dataset's own lyric annotation as the
  reference, and a hypothesis plus run cost produced by the registered
  `parakeet-onnx` engine and measured here (WER 0.0541, CER 0.0333, real-time
  factor 0.9800 on Windows 10, CPython 3.12, CPU int8; environment and date also
  recorded in `docs/BENCHMARK.md`). No ground truth is invented: vocadito
  annotates lyrics and records no word timestamps, chords, key or tempo for this
  excerpt, so the lyrics text is the only scored family, and a missing family is
  absent from the report rather than zero. Tests:
  `tests/integration/test_benchmark_product_path.py` — the stored-pair half
  (loading, the audio really is the committed sample, the reference really is the
  sidecar, `score_case` agrees with `metrics/lyrics.py`, all three report formats,
  the `songlab benchmark` command) needs no optional dependency and runs in the
  `dev`-only CI environment; the `--engine` half re-runs the real weights behind
  the same model-cache skip the lyrics integration tests use. It deliberately
  asserts the chain, not an accuracy threshold.
- [x] Local hand-chart agreement check (2026-10-27): `evaluation/chart.py`
  parses the plain-text chart format and aligns chart chords to detected chords
  with Needleman–Wunsch on triads; `scripts/chord_chart_check.py` reports
  matches, substitutions, missing and extra chords (human and `--json`).
  Tests: `tests/unit/test_chart_agreement.py` (parser/alignment) and
  `tests/unit/test_chart_check_command.py` (command wiring). A private 5:27
  recording against an 86-chord hand chart matched 84 chart chords in order
  (97.7%), 2 substitutions, 15 extra detections, 2026-10-27; that is a local
  sequence check, not a timed benchmark, and the song/chart are not committed.
- [~] Track accuracy on the same fixed evaluation set when engines change (Phase I)
  (2026-11-01): `benchmark/regression.py` holds an `AccuracyVector` — the metrics
  of one measured run plus the set, settings, environment and date that produced
  it — and `compare_run()` reads a harness `aggregate.json` against a committed
  vector, refusing anything not measured on that set before it judges a number.
  The chord set is pinned in `benchmark/reference/chroma_baseline-instructed.json`
  (the §8 adopted row: CSR 0.6312, triad 0.6384, overlap 0.8454, change F1 0.8553,
  13.07 hypothesis chords per take, means over the 180 instructed takes). Every
  `scripts/chord_benchmark.py` run now compares itself with that vector and exits
  **3** on a regression (`--no-check-vector` measures without tracking,
  `--write-vector` adopts a run as the new vector); the set is identified by the
  manifest's *content* digest so a Windows checkout with CRLF bytes is the same
  set, and a subset or the other annotation prints why it is not comparable.
  Tests: `tests/unit/test_benchmark_regression.py` (vector loading and refusal
  rules, the evaluation-set guard, the verdict band, report and adoption — no
  optional dependency, so it runs in the `dev`-only CI environment) and five
  end-to-end cases in `tests/unit/test_chord_benchmark_harness.py` behind the DSP
  marker. **Still missing for `[x]`:** a run against the real GuitarSet audio —
  the corpus is not in the repository and is not on this machine, so the pinned
  vector transcribes §8 (its `notes` say so) instead of re-measuring it, and the
  180-take comparison has only been exercised on synthetic corpora.

### Must NOT be considered complete

New datasets/benchmarks added without a product-driven question.

---

## 12. Phase L — Product Completeness and Stabilization **[P]**

**Objective:** Priority B — make every feature the project has *already designed*
work, be tested, and be described honestly, so that the application is complete
when launched from source. The source of truth for the intended feature set is
[`docs/GUI_REQUIREMENTS.md`](docs/GUI_REQUIREMENTS.md), Phases A–H above and the
parity backlog in section 18. Nothing here invents a requirement: where the audit
found a capability no design document asks for, the task is to decide that in the
open, not to build it.

**Current status:** `[~]` — audited in full on **2026-11-02** (read-only, every
verdict checked against the module that owns the behaviour). The core chain —
load → decode → analyse → display → edit → persist → transpose / simplify →
export — is implemented and covered by tests, and each of the nine `songlab`
subcommands has its own test file. The gaps are not a list of missing features
but three shapes of gap: **claims that outgrew their tests** (two, and both now
corrected where they were made — the export round-trip in section 9, and
`docs/INTERNATIONALIZATION.md` still describing `i18n/` as an empty package
although it ships the language wiring); **designed work left open** (translations
ship no catalogue, so the Language menu is wiring rather than translation; the
plain-text chart import carries its own list of unfinished details); and
**robustness holes only a user meets** (a failed or offline model download, no
way to stop an analysis already running, no audio-output-device choice, window
state not restored between launches, and a GUI whose human verification is one
manual session on Linux plus offscreen tests).

### The 2026-11-02 inventory

| Area | Verdict | Evidence | What is missing |
| --- | --- | --- | --- |
| Audio load, probe, validation, FFmpeg discovery | `[x]` | `audio/{validation,probe,ffmpeg}.py`, one decode owner `audio/decode.py`, `test_decode.py`, MP3 end-to-end in `test_analysis_e2e.py` | — |
| Playback | `[x]` | `audio/playback.py` (`load`/`play`/`pause`/`stop`/`seek`/`close`, `is_available()`, `DependencyError`), real-device tests, Windows 10 run 2026-10-31 | choosing the output device — not in the design (L6) |
| Waveform, chord strip, seeking | `[x]` | `audio/peaks.py`, `gui/timeline.py` (click and drag to seek) | zoom / scroll navigation, which no document asks for yet |
| Chord under the playhead, in sync | `[x]` | `app/display.py`, the GUI tick on the same `DisplayFrame`, `test_display_integration.py` incl. the playhead-monotonic regression | — |
| Analysis panel (confidence, key, tempo) | `[x]` | `app/summary.py`, `gui/analysis_panel.py` | — |
| Lyrics: ASR, `.lrc`/`.srt`, chord-over-lyrics chart | `[x]` | `engines/lyrics_parakeet.py` + chunking, `alignment/{lrc,srt}.py`, `app/chord_lyrics.py`, 33+ window tests | recovery when the model download fails or the network is absent (L4) |
| Plain-text chart import | `[~]` | `app/chart_import.py` (20 tests) | the open details section 8 already lists for it (L9) |
| Editing, undo/redo, sidecar persistence | `[x]` | `app/editing.py` (10 commands, 82 tests), `app/persistence.py`, corrupt-sidecar recovery | — |
| Transpose, simplify | `[x]` | `TransposeDocument`/`SimplifyDocument` on the tape, `normalization/{chords,spelling}.py`, `export --transpose/--simplify` | — |
| Exports | `[~]` | `export/{chordpro,markdown}.py`, `test_codec.py` | a **reader** for those two formats: only JSON round-trips (section 9, L10) |
| Progress, errors, exit codes | `[x]` | `analysis/progress.py`, `--progress` on stderr, the exit-code table in `docs/ARCHITECTURE.md`, close-with-unsaved-edits | cancelling a running analysis (L5) |
| CLI surface | `[x]` | `cli/main.py` (info, doctor, chords, analyze, lyrics, play, export, gui, benchmark), `docs/USAGE.md` | — |
| GUI stability | `[~]` | the offscreen suites, `gui/analysis_worker.py`, the 2026-10-16 playhead crash fix | restored window geometry, checked per-DPI behaviour, a person's look-check on Windows (L7) |
| Preferences / settings store | `[ ]` | nothing in `src/` — no `QSettings`, no platformdirs, no cache dir | `docs/DEVELOPMENT.md` promises "(later) the settings dialog" and no document says what it would hold (L8) |
| Translations | `[~]` | `i18n/`, the Language menu, `test_gui_language_menu.py` | no compiled catalogue ships, so nothing is translatable in practice (L3) |
| Long files | `[~]` | windowed chord analysis, 20 s lyric chunks, RTF measured 2026-10-31 | a full-length real song through the window, with its time and memory (task A4, section 10) |

### Tasks

- [x] L1 — remove the claims drift the audit found, done in the same change that
  recorded it (2026-11-02): `docs/INTERNATIONALIZATION.md` said `i18n/` "exists as
  an empty, documented package", which stopped being true on 2026-10-14 when the
  catalogue discovery and `install_translator()` wiring landed — that section now
  describes the wiring, the 85 translation call sites in the window, and the real
  open half (no `.qm` ships); and the export round-trip line in section 9 was
  re-marked `[~]` with its actual scope, because `export/chordpro.py` and
  `export/markdown.py` have no reader. `docs/ENGINE_COMPARISON.md` §11 and
  `docs/BENCHMARK.md` now say in their own words what the measurement record does
  and does not support. Documentation-only, but this is the kind of drift that
  lets an agent mark a phase `[x]` on a read.
- [ ] L2 — **validate the features together, from source**: one recorded session
  in which a real file is opened in the window, analysed, played, edited, saved,
  reloaded, exported (JSON + ChordPro + Markdown) and re-imported, plus the same
  song through `songlab analyze`/`export`, with the results compared. This is
  Priority C item 7 and it is an **entry criterion for section 14**: packaging
  work may not start on a feature set that has never been exercised as a whole on
  one machine by one person.
- [ ] L3 — translations: produce and commit at least one real `.qm` catalogue (the
  documented first target is Spanish, `docs/INTERNATIONALIZATION.md` phase 17), so
  the Language menu becomes a feature rather than wiring, and record the
  `lrelease` build step in the gate. The "remember which language I picked" half
  depends on L8: there is no store to write to yet.
- [ ] L4 — test the lyrics failure paths that a user actually meets: the Parakeet
  weights not yet downloaded and the network unavailable, or a download that
  stops halfway. Today `engines/lyrics_parakeet.py` raises `DependencyError` when
  the stack is missing, which is tested; the download path itself has no
  regression test and no documented recovery.
- [ ] L5 — let the user stop an analysis: a cancel on the window's worker and an
  honest statement of what `Ctrl+C` does mid-analysis on the CLI (exit 130 is
  documented, partial results are not). The chord pass is the long one; cancelling
  it must not leave a half-written sidecar.
- [ ] L6 — decide, in `docs/GUI_REQUIREMENTS.md`, whether audio output-device
  selection is a requirement. `SoundDevicePlayer` uses the default device and no
  document has ever asked for a picker; the parity table calls playback `[x]`, and
  that is correct **for the documented feature**, not for a device chooser.
- [ ] L7 — window state a person would notice: restore the last geometry and
  splitter sizes, check the layout at more than one DPI/scale factor, and do the
  one thing never done — open it on Windows 10 and confirm how the waveform, chord
  bands and chord-over-lyrics chart *look*, then record it in section 1 the way
  the 2026-10-18 Linux session was.
- [ ] L8 — preferences. `docs/DEVELOPMENT.md` says user-facing configuration
  "belongs in explicit CLI options and (later) the settings dialog", and the audit
  found no settings store anywhere in `src/` (no `QSettings`, no platformdirs, no
  cache directory), so the promise exists and the requirement does not. First write
  down which settings the product commits to remember — language (L3), last folder,
  display spelling, chord chunk size — in
  [`docs/GUI_REQUIREMENTS.md`](docs/GUI_REQUIREMENTS.md); only then build the store
  behind `app/`, offscreen-testable, never inside a widget.
- [ ] L9 — finish the plain-text chart import against the open items section 8
  already admits (section-aware timing, provenance of the imported path,
  beat-level placement), each with the test that proves it.
- [ ] L10 — a ChordPro reader, or an explicit descoping note: with no reader in
  `export/`, the round-trip claim in section 9 can only be half true. Choose one —
  implement `parse_chordpro()` behind the same typed model, or state in
  `docs/USAGE.md` that ChordPro and Markdown are output-only formats.

### Acceptance criteria

Phase L reaches `[x]` when every `[~]` and `[ ]` row of the inventory is either
delivered with tests or explicitly descoped in the document that owns it, L2's
cross-feature session is recorded with its environment and date, and no `[x]`
marker in this file claims more than a test establishes. Feature *ideas* are not
accepted here: a new requirement enters through
[`docs/GUI_REQUIREMENTS.md`](docs/GUI_REQUIREMENTS.md) first.

### Dependencies / blockers

L2 gates the entry criteria of section 14. L3's persistence half and L7's
restored state depend on L8. L4–L6 and L9–L10 are independent of Phase I, which
is why they can be picked up while an accuracy measurement is waiting to run —
but none of them may displace section 10's queue.

### Must NOT be considered complete

A feature proven only offscreen and never opened by a person on the platform it
will ship to; a re-marked `[x]` without the code or doc change behind it; an
invented requirement presented as Priority B work.

---

## 13. Phase K — Performance and Cross-Platform Source Compatibility **[P]**

**Objective:** the application, run **from source**, works on Linux, Windows and
macOS. Shipping a frozen bundle is no longer part of this phase: the packaging and
distribution work moved to section 14 on 2026-11-02, and cross-platform
*source* compatibility remains an ongoing requirement.

**Current status:** `[~]` — portable code + platform-aware discovery exist and
CI runs on the gate; the long-song strategy landed 2026-10-14 (windowed chord
analysis + progress reporting); **Windows 10 was verified by running the gate
and the product path there on 2026-10-31** (§1), and the full product path's
real-time factor was measured on that machine the same day
(`docs/ENGINE_COMPARISON.md` §9); `songlab doctor` reports the optional extras
and per-engine availability since 2026-11-01 (task below). What has **not** been
done from source is a recorded Linux or macOS run of the full gate on this
project's current tree: CI is the only evidence for those platforms, so this
phase stays `[~]` and the honest platform matrix in the README says which systems
were actually run.

**CI note (2026-10-31).** The most recent completed run on `main` (2026-10-27)
had only "Lint and type check" pass: all twelve matrix jobs failed their test
step, as did the DSP and integration jobs. The job logs need authentication, so
the failure text is still not readable from here — but the *configuration* is
now reproduced locally. A venv that installs exactly what the matrix installs
(`-e ".[dev]"`, no Qt, no DSP) fails during **collection**: four window test
modules import `song_chord_lyrics_analyzer.gui.*` at module level and those
modules import PyQt6, so `pytestmark = skipif(...)` and `pytest.importorskip(...)`
never get to record a skip and pytest aborts with "Interrupted: 4 errors during
collection" before running a single test. That run then exposed a second class:
six `chroma-baseline` option tests decode audio but carried no
DSP-availability guard. Both are fixed in the tree as of 2026-10-31 — the Qt
guard is now a module-level `pytest.skip(..., allow_module_level=True)` placed
*before* the imports that need Qt, and the decoding tests share a `_requires_dsp`
marker — and the dev-only suite is green on Windows 10: 1930 passed, 109 skipped,
0 failed in 56 s (1880 passed / 110 skipped before the finiteness tests landed,
on the same day). The other CI test configuration was emulated the same way — a third
venv installing `-e ".[dev,dsp,gui]"` with FFmpeg present and no `lyrics` extra,
which is the shape of the `dsp` job — and is green too: **2174 passed / 18
skipped / 0 failed in 150 s** (2026-10-31; 2125 passed / 18 skipped in 142 s
before those tests). The mechanism does not depend on the operating system, so it covers the
Ubuntu and macOS jobs too; only the next push can confirm that CI's failures were
these and nothing else. Alongside them, the fifteen tests that required the
`lyrics` extra fail in the configuration the DSP job installs
(`dev,dsp,gui`), and a type-check job that installs the latest `PyQt6` aborts
inside the vendor stubs before it reads this project's code; both were already
fixed here, and `gui` now caps `PyQt6>=6.5,<6.12`.

### Tasks

- [x] `pathlib`, platform-aware executable discovery, no hard-coded paths
- [x] Cross-platform CI for lint/type/tests
- [x] Windows 10 runtime verification (2026-10-31) — the documented gate and the
  user-facing chain were run on Windows 10 22H2; §1 records the environment, the
  counts and the six fixes it needed. Two were Windows-only bugs in shipped
  code (host separators in the canonical JSON, and the GuitarSet manifest
  absolute-path rule asking only the host flavour); the PyQt6 6.12 stub break,
  the POSIX-only `resource` import, the fifteen `lyrics`-extra tests and the
  window test modules that could not be collected without Qt affect every
  platform, so `gui` now caps `PyQt6>=6.5,<6.12`. The README's
  "On Windows 10 / 11" and "Using it on Windows 10 / 11" sections document the
  install and the day-to-day commands for users.
- [x] The README installation section says which operating system each command
  belongs to (2026-11-01). The block that opens it was the Linux one, so a
  Windows reader had to pick the platform lines out of it and a Fedora or Arch
  reader could not tell which parts transferred. It is now "On Linux: Debian,
  Ubuntu and other `.deb` distributions" — naming the distributions it assumes,
  adding the `sudo apt install python3-venv python3-pip` and
  `sudo apt install ffmpeg` steps those systems need, and stating that on
  `dnf`/`pacman`/`zypper`/`apk` systems only those lines change — beside a short
  "On macOS" section and the existing "On Windows 10 / 11" one, which now opens
  by saying that `apt` does not exist there and `venv` comes from the Python
  installer. `docs/DEVELOPMENT.md` carries the matching note. No command changed.
- [x] songlab's own text output is UTF-8 on every platform (2026-10-31) — a
  seventh Windows-only bug, found while stamping `--json` and recorded in §1: a
  redirected Python stream takes the console code page (`cp1252` measured on this
  machine, ASCII in a POSIX C locale) while the canonical document is written with
  `ensure_ascii=False`, so `analyze --json > doc.json` produced a file that is not
  valid UTF-8 and a character outside that code page raised `UnicodeEncodeError`
  out of an ordinary `info` run. `cli/main.py:configure_utf8_stdio()` states the
  encoding before any command prints; `docs/TROUBLESHOOTING.md` covers what a user
  sees when the *terminal* is the one that cannot render UTF-8.
- [x] Measure and record real-time factor for the full product path on a
  reference machine (§45 harness already exists) — measured on Windows 10 on
  2026-10-31 (`docs/ENGINE_COMPARISON.md` §9, environment and fixtures stated
  there): all four registered layers on a 35.208 s file cost 23.0–27.4 s
  (RTF 1.29–1.53) and on a 281.664 s cost fixture 67.5–88.4 s (RTF 3.19–4.17);
  without the optional `lyrics` extra the same paths run at RTF 4.66–4.83 and
  19.9–26.8. The lyrics engine is 72–84 % of the full path's time, and no
  peak-RSS figure exists on Windows by design.
- [x] Long-song strategy (chunked analysis, progress reporting) — landed
  2026-10-14, **opt-in and honest about its scope**:
  * `analysis/chunking.py` analyses the chord layer in windows
    (`--chord-chunk-seconds`, default off, `plan_chunks` reused from the
    lyrics windowing). The seam rules are the deliverable: an earlier window
    wins, coverage is never lost (a straddling chord keeps its part after the
    previous coverage, so no boundary is invented), a chord split by a seam is
    joined within one frame, and an engine that ignores the time range is
    reported instead of producing a duplicated timeline
  * only chords are windowed: key and tempo need the whole song, and the
    lyrics engine already chunks internally at 20 s
  * `analysis/progress.py`: `run_analysis(..., on_progress=...)` reports each
    step and each window, printed to *stderr* by `songlab analyze --progress`
    and `songlab play --progress`, so `--json` on stdout stays clean
  * the windowing is recorded in provenance (`chords_chunk_seconds`) and the
    run cost is the sum of the windows, never a partial sum
  * measured and recorded in `docs/ENGINE_COMPARISON.md` section 5
    (2026-10-14, environment + date stated): same chord labels and order as the
    whole-file pass on a 480 s fixture with one seam boundary moved by 94 ms;
    peak RSS 996 MB -> 309 MB on a 600 s file, runtime unchanged within noise
  * the GUI half landed 2026-10-14: `gui/analysis_worker.py` runs the
    session's own `open()` on a `QThread` (`ThreadedAnalysis`, the window's
    default runner; `ImmediateAnalysis` keeps the synchronous seam for tests
    and embedders). The window shows the service's `on_progress` events on a
    progress bar and the status line (a fraction only when a step reports
    one), disables every action while the worker owns the session, refuses a
    second song until it ends, and honours a close asked for mid-analysis
    when the analysis ends - the worker thread is joined in the slot that
    reports the outcome, so a window never dies with a running thread.
    Verified offscreen (`TestTheAnalysisRunsOffTheUiThread`) and against the
    real engine (`tests/integration/test_gui_integration.py`)
- [x] `songlab doctor` reports which optional extras are installed and which
  registered engines can run (2026-11-01) — the requirement that packaging
  "clearly report" the optional extras is met from a source install, with no
  bundle involved: `doctor.OPTIONAL_EXTRAS` maps each runtime extra (`dsp`,
  `playback`, `gui`, `lyrics`) to the imports that stand for it and to what a
  user loses without it; `collect_status()` adds an `extras` block (`installed`,
  `missing`, `provides`, `pip`) and marks each registered engine available or
  not, so `Analysis engines` now names the reason instead of listing a bare kind.
  The check is `find_spec`, never an import, so `doctor` stays quick and the core
  install stays Qt-free and DSP-free. Verified on Windows 10 (2026-11-01) in two
  environments: a full install reports all four extras `ok` and all four engines
  `ok`; a `dev`-only install reports all four `missing` with the import list and
  the matching `pip install "song-chord-lyrics-analyzer[extra]"`, and all four
  engines `unavailable here`. Tests: `tests/unit/test_cli.py::TestDoctorCommand`
  (importability decides the verdict, the report prints the pip hint, per-engine
  availability) — all three run without Qt, numpy or librosa.
- Building and distributing a frozen application is **not** this phase's work
  since 2026-11-02: the completed Windows 10 milestone and everything still
  deferred is recorded in section 14.

### Must NOT be considered complete

"Works on my machine"; unverified platform badges.

---

## 14. Final Phase — Cross-Platform Packaging and Distribution **[P] — deferred**

**Objective:** a user who does not install Python can download, launch and use
`songlab` on Linux, Windows and macOS.

**Status:** `[ ]` as a phase — deliberately last. On 2026-11-02 the strategy
changed: standalone distribution moves behind product quality, recognition
accuracy and validated functionality (sections 10, 11 and the Phase L work),
because a polished binary of an analyzer that measures 0.6312 CSR is not a
product increment. Nothing in this section may start early, and the completed
Windows 10 milestone below is kept as a **foundation**, not as licence to expand
packaging.

**Entry criteria — this phase begins only when all of these hold:**

- [ ] Chord recognition meets the acceptance criteria written in section 10 —
  measured, not inferred from confidence scores.
- [ ] The principal application features are implemented and tested (the
  Priority B audit findings in Phase L closed).
- [ ] The application is stable when launched **from source** on the platforms it
  claims.
- [ ] `python scripts/check.py` passes, and the CI matrix is green rather than
  red-with-an-unreadable-log (the 2026-10-31 finding in section 13).
- [ ] Each supported OS has been validated in its normal development environment
  (source install + gate), which is a Phase K claim, not a packaging claim.

### Tasks

- [~] A frozen `songlab` bundle exists and was **built and run on Windows 10**
  (2026-11-01), measured on Windows 10 (10.0.19045) with CPython 3.12.0 and
  PyInstaller 6.22.3 in a `[dev,dsp,playback,gui]` venv:
  `packaging/songlab.spec` (the bundle's shape) + `scripts/build_app.py` (the
  plan, which the spec imports so there is one source of truth) +
  `packaging/songlab_entry.py` (three lines onto `cli.main.main`, so the
  executable and the pip console script cannot drift), behind a new `build`
  extra. One directory, not one file, so the LGPL libraries stay replaceable;
  the lyrics stack is excluded by name so the frozen `songlab doctor` reports
  `lyrics` missing — the artifact says what it is. `THIRD_PARTY_NOTICES.txt` is
  written *from* the archive the build produced (the PYZ table of contents →
  distributions → the licence each wheel declares), the wheels' own licence
  texts are copied into `notices/`, and each `docs/LICENSE_AUDIT.md` §6 row is
  answered by file evidence in the bundle: OpenBLAS, LAPACK, libsndfile (with
  `_soundfile_data/COPYING`) and Qt (`qt6core.dll`) present, libgfortran and
  libquadmath correctly absent from a Windows scipy wheel. Two build defects
  found by running the result, not by reading the docs, and both fixed in the
  spec: an unpatched CPython 3.12.0 `code.replace()` makes PyInstaller emit
  `scipy.stats` with the wrong module scope (`NameError: name 'obj' is not
  defined` at import), so the spec probes that and disables the path
  anonymizer when the probe says broken — it disappears by itself on 3.12.1+;
  and `collect_submodules("numba")` dragged the whole test suite plus pytest,
  pluggy and 340 pygments modules into the product, so the spec drops test
  submodules by name and dev-only trees from the archive, while keeping
  `coverage` because `numba/core/lowering.py` subclasses `coverage.types.Tracer`
  at import time (a bundle without it fails in the chord pass). Verified by
  *running* `dist/songlab/songlab.exe` (1252 files, 358,130 KB, 2304 modules in
  the archive): `--version`, `doctor`, `info` and `chords samples/vocadito_2.wav
  --json` all exit 0 — 28 chord segments, and every field of that JSON except
  the measured performance block is identical to the installed console script's
  output — and `songlab gui` opened offscreen and stayed alive 20 s.
  `docs/DEVELOPMENT.md` §10 is the how-to and the decisions;
  `tests/unit/test_build_app.py` covers the plan, the spec against fake
  PyInstaller objects, the scope probe and the notices. **This is the whole
  packaging record: one platform, run.**
- [ ] The same build executed on Linux and macOS. The script and the spec are
  platform-neutral (no path or marker is Windows-only) but only Windows 10 has
  been run, so no other platform is claimed.
- [ ] Smoke test of the packaged app on each target OS (honest matrix in README)
- [ ] Distribution-specific dependency collection re-audited per platform: the
  §6 licence evidence above is Windows-shaped (a Windows scipy wheel without
  libgfortran/libquadmath); Linux and macOS carry different binaries and need
  their own file evidence, not a copied table.
- [ ] Briefcase, or another standalone distribution system, evaluated **only if**
  the PyInstaller path proves wrong for the product (installers, code signing,
  per-OS update channels). Not started.
- [ ] Installers and portable bundles per OS, with the licence obligations of a
  distributed binary re-checked at the time of distribution.
- [ ] Release packaging and publishing.

### Must NOT be considered complete

A bundle built on one operating system described as cross-platform; a packaged
app shipped before the accuracy acceptance criteria are met; a README that
advertises downloadable builds that do not exist.

---

## 15. Research Backlog **[R]**

Subordinate to the product. Nothing here blocks Phases A–H. Each item needs a
**product reason** to be picked up. Valuable existing research (do not repeat):

* **Datasets** — search completed; GuitarSet (CC BY 4.0) adopted with
  annotation-only fixtures; IDMT/CASD blocked by NC/ND/SA; details in
  `docs/DATASET.md` and `docs/LICENSE_AUDIT.md`.
* **Licensing** — code/model/dataset audit done (`docs/LICENSE_AUDIT.md`,
  `docs/DEPENDENCY_MATRIX.md`); re-open only when a concrete new dependency
  requires it.
* **Lyrics ASR** — Parakeet vs faster-whisper measured (WER/CER/RTF, English vs
  Tagalog/Spanish, both MIT, chunking mandatory, stems not default); corpus
  cached in `.cache/` (gitignored); recorded in `docs/ENGINE_COMPARISON.md`.
* **Stem separation** — Demucs measured: hurts faster-whisper, marginal for
  Parakeet; not default. Revisit only for a user-facing stem feature.
* **Viterbi/chord decoding** — measured, shipped in the baseline engine.
* **Key/tempo** — Krumhansl (0.4278 exact / 0.1333 relative, 360 takes) and
  librosa tempo (22.63 BPM mean error, octave cases kept) measured and shipped.
* Candidate engines and tools investigated: Chordino/Sonic Annotator, madmom,
  beat_this, basic-pitch, Guitariz, musicpractice — all `external/`
  reference-only, never dependencies.
* Open questions: calibrated chord confidence; alignment of independent lyric
  streams; caching/reproducibility (old sections 60–62); i18n (English-first
  until the UI is stable).

---

## 16. Experimental Engines **[R]**

Engines **not** required for the first product. They exist to be read and
compared against, not to be built now:

* `external/` submodules: `chordify`, `Guitariz`, `orchidas-Chord-Recognition`,
  `basic-pitch`, `musicpractice`, `chordify-org/*` — **read-only reference
  material**, never imported, never dependencies (see `AGENTS.md`).
* Possible future in-repo experiments (only under Phase I justification):
  CNN/ONNX chord models, bass-aware decoding, ensemble/fusion decoders.

**Rule:** no experimental engine work before the First Product Milestone
(Phase C) is reached.

---

## 17. Long-Term Features **[F]**

After Phases A–K: song sections/structure detection, multiple display
languages (Qt Linguist), stems view and stem playback, practice features
(loop/speed — see `external/musicpractice` as reference), beat grid display,
additional export formats (MIDI, MusicXML), plugin-style third-party engines,
mobile/web distribution.

---

## 18. Parity Backlog — the features named in the Chordify / Chord AI comparison **[F]**

This is the product gap list, not the accuracy plan (that is Phase I) and not
the core milestone (Phases A–H). Each item is `[ ]` until it exists, runs and is
verified; none of them is a prerequisite for the chord chart or the measured
engine. The order is the order a user would notice the difference.

| Feature | Status | Why it is not done yet / what it needs |
| --- | --- | --- |
| File input, playback, seek, synchronized chords, chord-over-lyrics chart, key/tempo/lyrics, editing, undo/redo, transpose, simplify, export | `[x]` | delivered 2026-10-07..21; see Phases C–H |
| Import a user's plain-text chord chart (chords + lyrics) and align it to the song | `[~]` | implemented 2026-10-27: `app/chart_import.py` + Edit → Load chord chart... (`Ctrl+Shift+L`) anchor chart chords under the chart's chord columns, time lyric lines from the transcript's words, distribute instrumental runs, and save the base to the sidecar. Still open: section-aware timing, recording the chart path in provenance, beat-level placement, and manual correction of a badly aligned line |
| Transposition / capo-style display | `[~]` | transpose is implemented; an explicit capo setting that shifts what the player reads while the sounding chords stay fixed is a small presenter addition, not a new engine |
| Guitar / piano / ukulele chord diagrams | `[ ]` | needs a voicing table and an `app/` presenter; the chord label already exists, and the diagrams must not be generated by inventing finger positions |
| Loop playback (A/B) | `[ ]` | needs a player-side loop over the existing decoded buffer; the `Player` protocol already has `seek`/`play`/`pause` |
| Tempo slowdown without changing pitch | `[ ]` | needs a time-stretch backend behind the `Player` protocol; no dependency is audited yet, and the current `sounddevice` path plays the decoded samples at their own rate |
| Microphone / live input | `[ ]` | needs capture plus a streaming analysis path; `decode_audio()` is file-based today, and the accuracy of a short-window streaming decode is unmeasured |
| YouTube / SoundCloud import | `[ ]` | would be an optional downloader (`yt-dlp`-style) with its own licence, terms-of-service and failure surface; never a core dependency, and never redistributing the downloaded audio |
| 700+ chord vocabulary and slash chords | `[ ]` | Phase I P4/P6; the conservative seventh pass was measured and rejected, so this needs bass/root evidence and a measured triad-reduced non-regression |
| Offline mode (no network at analysis time) | `[~]` | the engines are local once installed; the lyrics model is pulled on first use (CC-BY-4.0) and the learned chord model does not exist yet. Packaging must make the model state explicit |
| Mobile / web clients | `[ ]` | out of scope for the desktop first product; the canonical JSON document is the integration seam if it is ever revisited |
| Translations | `[ ]` | the Language menu ships, no catalogue does; English is deliberately first until the UI is frozen |

**Rules for this backlog.** No item may be taken by copying an `external/`
repository or weights; a new dependency needs the licence audit first; an
accuracy feature needs the Phase I harness; a practice feature needs its own
tests and must not fork the playback clock. The desktop product stays the
priority.

---

## Appendix — Relationship to the old roadmap

The pre-reset roadmap (§1–§125) is archived at
[`docs/archive/ROADMAP-pre-product-reset.md`](docs/archive/ROADMAP-pre-product-reset.md).
Its technical knowledge (section numbers, measurements, decisions) remains
valid and is referenced from the docs listed in §1. Its **sequencing** — research
gates before product work — is obsolete. Use its `[*]`/`[x]`/`[ ]` markers only
as history; the markers in *this* file are the live status.
