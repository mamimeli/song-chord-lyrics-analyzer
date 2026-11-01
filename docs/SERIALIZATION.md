# The canonical JSON document — serialization contract

Roadmap Phase B asks for the stable JSON serialization contract: the fields of a
chord event, their units, and the edge cases (`N`, `?`, overlaps). This is that
document. It describes what a **reader** may rely on and what a **writer**
guarantees, for every JSON songlab produces from the canonical model.

Related: [`ARCHITECTURE.md`](ARCHITECTURE.md) §4 (the model) and §8 (the codec
seam), [`../ROADMAP.md`](../ROADMAP.md) Phase B.

## 1. One codec, six writers

Everything goes through `schema/codec.py` (`encode`, `encode_document`, `decode`,
`to_json`, `from_json`): dataclass fields in declaration order, no per-model
`to_dict`. What differs is the wrapping and which model is the root, and a reader
must not assume more than this:

| Written by | Root object | Entry point | Shape | Key order |
| --- | --- | --- | --- | --- |
| `songlab analyze --json` | `AnalysisResult` | `json.dumps(encode_document(…))` | bare, stamped | model field order, `schema_version` first |
| `songlab chords --json`, `songlab lyrics --json` | `EngineResult` | same | bare, stamped | model field order |
| `songlab info --json` | `AudioDocument` | same, plus a `sha256` key (`null` without `--hash`) | bare, stamped | model field order |
| `songlab export --format json -o FILE` | `AnalysisResult` | `export.render_json` | bare, stamped | alphabetical (`sort_keys=True`) |
| `benchmark.json` | `AnalysisResult` | `schema.to_json` | `{"schema_version": …, "document": …}` | model field order |
| edits sidecar | `songlab-edits` | `app/persistence.save_edits` | envelope around the edits document | alphabetical |

The *field rules* are identical in all six — same encoder, same names, same
units — but the **root object** differs, so a reader must know which command
wrote the file: an `EngineResult` (one engine's output) has no `run` and no
`provenance`, and an `AudioDocument` has no layers at all. Index by key name and
ignore both ordering and the presence of the envelope — only the sidecar is
version-checked on read (§9).

Every one of them carries `SCHEMA_VERSION`: in the envelope as its own key, in
the bare shape as a top-level `schema_version` written first by
`encode_document`. `songlab doctor --json` is the deliberate exception: it prints
environment diagnostics, not the canonical model, and is not covered here.

An analysis document has no `format` marker; the sidecar carries
`"format": "songlab-edits"`. Distinguish them by that key or by their shape.

## 2. Top level of an analysis document

`AnalysisResult` (`models/analysis.py`). Every key is always present; the ones
marked *nullable* hold `null` when the layer does not exist, and a layer whose
engine was unavailable is reported in `run` and `warnings` rather than by
dropping keys.

| Key | JSON type | Notes |
| --- | --- | --- |
| `provenance` | object | the only required key (§6); reproducibility record |
| `audio` | object or null | technical metadata of the file |
| `lyrics` | array of `LyricSegment` | empty when the lyrics layer is missing |
| `chords` | array of `ChordEvent` | §3 |
| `beats`, `downbeats`, `bars` | arrays | the rhythmic grid; no beat engine exists yet, so usually empty |
| `key` | object or null | `KeyEstimate` |
| `tempo` | object or null | `TempoEstimate` |
| `notes` | array of `NoteEvent` | pitch evidence; no producer yet |
| `stems` | array of `Stem` | separated sources; no producer yet |
| `alignment` | object or null | `AlignmentResult` |
| `engines` | object | engine name → `EngineInfo` |
| `run` | object | status, timestamps, per-step outcomes, warnings, errors |
| `raw` | object | engine-specific evidence, **not** part of the stable contract (§8) |
| `warnings` | array of string | human-readable, unstable wording |

`run.status` is one of `pending`, `running`, `succeeded`, `partial`, `failed`.
A `partial` run is honest: some layers were skipped or failed and `run.steps` /
`warnings` say which.

## 3. A chord event

`ChordEvent` (`models/music.py`). Ten keys, always all present:

| Key | JSON type | Unit / vocabulary | Absent value |
| --- | --- | --- | --- |
| `start` | number | seconds from the start of the file, `>= 0` | required, never null |
| `end` | number or null | seconds; `end >= start` | `null` = the engine gave no boundary |
| `root` | string or null | pitch class name, sharp-spelled (`C`, `F#`, `Bb` accepted) | `null` for `N` and for `?` |
| `quality` | string | one of the `ChordQuality` values (§5) | `unknown` |
| `bass` | string or null | slash-chord bass, only when different from `root` | `null` |
| `extensions` | array of string | intervals/tensions as the engine reported them, unmodified | `[]` |
| `label` | string | the rendered text, always populated | never empty |
| `confidence` | object | `{value, level, source}` | `{"value": null, "level": "unknown", ...}` |
| `source` | string or null | engine or module that produced the event | `null` |
| `metadata` | object | engine evidence, verbatim (e.g. `score_margin`) | `{}` |

### `label`, `N` and `?`

`label` is what the interface shows and it is never empty: the raw text of an
engine survives even when the structured parse failed. The rendering rules
(`ChordEvent.to_label`) are part of the contract:

* `"N"` — explicit **no chord** (`quality: "no_chord"`), built by
  `ChordEvent.silence()`.
* `"?"` — an event with **no evidence**: `root` is `null` and the quality is not
  `no_chord`. Unknown is never reported as silence, so a reader must keep the
  two apart.
* anything else — `root` + the quality suffix (`Gm`, `Cmaj7`, `C/E` when a bass
  note differs from the root). `other` and `unknown` render with no suffix, so
  the structured parts carry the truth and `label` carries the original text.

### Time and overlap

Times are **seconds measured from the start of the audio file**, as floats, and
they are validated at construction: a negative `start` or an `end` before
`start` raises before anything is written. `end: null` means the producer did not
claim a boundary; the consumer's own rule applies (the window draws the chord up
to the next change or the end of the file). Do not read `null` as zero.

The canonical timeline **permits overlapping events**: a sung word may span a
chord change, and one lyric line may carry several chords (roadmap §36, §37).
Chord arrays are not re-sorted or intersected by the codec, so a reader that
needs a partition must build one. In practice `chroma-baseline` emits events in
`start` order without overlaps, and the chunked long-song merge keeps that order
(an earlier window wins; a chord split by a seam keeps its part after the
previous coverage, so coverage is never lost or invented).

## 4. Units

| Field | Unit |
| --- | --- |
| `start`, `end`, `time`, `duration` (chord, beat, word, segment) | seconds, float, from file start |
| `audio.sample_rate` | Hz, integer |
| `audio.bit_depth` | bits per sample, integer, when the container exposes it |
| `audio.bitrate` | bits per second, integer |
| `audio.file_size` | bytes, integer |
| `tempo.bpm`, `tempo.alternatives` | beats per minute, float |
| `notes.pitch_midi` | MIDI note number, integer |
| `notes.velocity` | 0–127, integer |
| `confidence.value` | `[0.0, 1.0]` float or `null` |
| `provenance.created_at`, `run.started_at`, `run.finished_at` | ISO-8601 string with UTC offset |

`confidence.value: null` means *the source did not say*, and
`confidence.level` is `"unknown"` in that case. A numeric value always carries a
`level` **derived from it** (`< 0.2` very_low, `< 0.4` low, `< 0.6` medium,
`< 0.8` high, else very_high): `ConfidenceScore.__post_init__` recomputes the
band, so a reader should treat `value` as authoritative and `level` as a
convenience that can never disagree with it.

**Every number above is finite.** `NaN` and infinity have no JSON literal, and a
`NaN` compares false against every bound, so a sign check alone lets one travel
all the way into a document as the bare token `NaN` — which strict parsers
reject. The model is therefore the refusing boundary:
`models/validate.require_finite` runs in every `__post_init__` that holds a time,
a duration, a confidence or a bpm, and raises `ValueError` before the object
exists. In front of it, the CLI refuses a `--start`, `--end`, `--min-duration`,
`--at`, `--interval`, `--chunk-seconds` or `--overlap-seconds` that is not a
finite number of seconds, and `chroma-baseline` validates its merge length
before decoding instead of after it. A `NaN` in a document is a producer bug:
report it, do not work around it. The hole was real until 2026-10-31; before the
guard, `songlab chords --start nan` on a readable WAV reported "Unsupported or
unreadable audio file ... cannot convert float NaN to integer" (Windows 10).

## 5. Enumerations are closed

Encoded as their `.value` string. A reader on an older version rejects an
unknown value (`SchemaError`), so adding a value is a breaking change for
readers even when it is additive for writers:

| Enum | Values |
| --- | --- |
| `ChordQuality` | `major`, `minor`, `no_chord`, `7`, `maj7`, `m7`, `sus2`, `sus4`, `dim`, `aug`, `add9`, `6`, `m6`, `9`, `m9`, `other`, `unknown` |
| `ChordQuality` fallbacks | `other` keeps an unrecognised suffix verbatim, `unknown` keeps an unparseable label; neither is a silence |
| `ConfidenceLevel` | `unknown`, `very_low`, `low`, `medium`, `high`, `very_high` |
| `KeyMode` | `major`, `minor`, `unknown` |
| `LyricSegmentKind` | `lyrics`, `instrumental`, `non_lexical`, `unknown` |
| `RunStatus` | `pending`, `running`, `succeeded`, `partial`, `failed` |
| `StemName` | `vocals`, `drums`, `bass`, `other`, `piano`, `guitar` |

## 6. Required fields

`decode` fails with `SchemaError` (naming every missing field, sorted) when a
key with no default is absent. Everything else may be omitted and takes its
model default — that is what makes adding an optional field non-breaking:

| Object | Required keys |
| --- | --- |
| `AnalysisResult` | `provenance` |
| `Provenance` | `application_version` |
| `AudioDocument` | `path` |
| `ChordEvent` | `start` |
| `BeatEvent` / `DownbeatEvent` | `time` |
| `BarEvent` | `index`, `start` |
| `NoteEvent` | `start` |
| `LyricSegment` / `LyricWord` | `text` |
| `KeyEstimate` | — (all optional) |
| `TempoEstimate` | `bpm` |
| `Stem` | `name` |
| `EngineInfo` / `EngineResult` | `name`, `kind` / `engine`, `kind` |

Unknown keys are **ignored** and logged at debug level, never an error — a newer
writer stays readable by an older reader as long as it only adds keys.

## 7. Paths, text and encodings

* Every path is written with **forward slashes** on every operating system
  (`utils.paths.canonical_path_str`): a Windows analysis records
  `C:/Users/you/Music/song.mp3`, never `C:\\Users\\...`. That is what makes a
  document written on one machine readable on another, and `provenance.input_path`
  and the sidecar's `input_path` follow the same rule. Relative paths stay
  relative.
* Text is written with `ensure_ascii=False`, so Spanish, Portuguese or English
  lyrics appear literally rather than as `\uXXXX` escapes. That promise needs an
  encoding, and the CLI supplies it itself: `cli.main.configure_utf8_stdio()`
  runs before any command prints, so a redirected `--json` stream is UTF-8 even
  where Python would take the locale code page — cp1252 on Windows, ASCII in a
  POSIX C locale. Both halves of the difference were measured on Windows 10 on
  2026-10-31: before the fix, `songlab analyze … --json > doc.json` wrote a file
  that `json.load(..., encoding="utf-8")` rejected, and printing a name the code
  page has no byte for raised `UnicodeEncodeError` inside the command.
* A file written by `songlab export -o FILE` is UTF-8 **without** a BOM, and its
  line endings are the platform default — CRLF on Windows, LF elsewhere
  (measured on 2026-10-31). That is invisible to any JSON parser but not to a
  checksum: do not compare exported files byte for byte across operating
  systems. On Windows, do not create the file with PowerShell 5.1's `>` operator
  instead: it re-encodes redirected output as UTF-16LE, which JSON readers reject
  (`README.md`, "Using it on Windows 10 / 11").
* Booleans are JSON booleans; `null` is JSON null. No key is ever the string
  `"None"`.

## 8. What is *not* stable

Read these as promises about the structure, not about every value:

* `raw` keeps each engine's own output (frame labels, pitch-class profiles) for
  debugging and re-scoring. Its keys belong to the engines and may change with
  them; `scripts/chord_benchmark.py` and `evaluation/` are the consumers that
  tolerate that.
* `metadata` inside an event is the same deal per engine, e.g. `score_margin`
  from `chroma-baseline`.
* `warnings`, `run.steps` strings and every other human-readable message are
  unstable wording; match on the structured fields instead. `run.steps` entries
  are `kind:engine:status:detail` strings.
* Floats are JSON floats: the codec does not round, quantise or compare them, so
  an exact binary round-trip is guaranteed only within the text a given Python
  writes (`repr`-shortest form). Two engines' times that should be equal may
  differ in the last digits. Finiteness, by contrast, *is* a guarantee (§4): a
  document never carries the bare `NaN` or `Infinity` token an earlier build
  could emit.

## 9. Versioning

`SCHEMA_VERSION = "1"` is a **string**. Every writer in §1 carries it — the
envelope writers as the envelope's own key, the bare writers as a top-level
`schema_version` added by `encode_document`. The rules this project follows:

* Adding an optional key, an object, or a new field with a default is
  non-breaking: unknown keys are ignored, missing optional keys take defaults.
  Do not bump the version for it.
* Renaming or removing a key, changing a unit, or turning a nullable field
  required is breaking: bump `SCHEMA_VERSION`.
* Adding an enumeration value is reader-breaking (§5) even though it looks
  additive; state it in `CHANGELOG.md` and keep a fallback (`other`, `unknown`)
  whenever a vocabulary grows.
* Reading an enveloped **document** whose version differs logs a warning and
  still decodes — the point is to make migration visible, not to refuse the
  user's own file. A bare stamped document is a marker for whoever consumes it:
  `decode` ignores the unknown key, so nothing refuses an old `--json` file.
* `from_json` reads the **envelope** only. For a file written by a `--json`
  command, the reader is `decode(cls, json.loads(text))`; passing the bare shape
  to `from_json` raises `SchemaError` and says so in its hint.
* Reading an **edits sidecar** whose `edits_version` differs
  raises `SchemaError`, because the sidecar must be replayed exactly and a wrong
  assumption there silently changes a user's chords.
* The sidecar nests `format`, `edits_version`, `input_path`, `input_hash`,
  `chords`, `lyrics` (optional) and `commands` inside `document`.

## 10. What locks this contract

`tests/unit/test_codec.py` (the codec both ways, the portable-path rule, unknown
keys, missing required keys, the `encode_document` stamp), `tests/unit/test_paths.py`
(`canonical_path_str`), `tests/unit/test_persistence.py` (sidecar round-trip and
version refusal), `tests/unit/test_models.py` (model validation: negative times,
end before start, non-finite numbers, unknown roots), `tests/unit/test_export.py`
(the export formats), and `tests/integration/test_analysis_e2e.py` (a real
analysis document end to end, with `input_path` in forward slashes). Each `--json`
command pins its stamp on the printed payload — `test_cli.py` for `info`,
`test_analysis.py` for `analyze`, `test_chords_command.py` and
`test_lyrics_command.py` for the single-engine commands — so a writer that stops
stamping fails a test, and `TestStdioEncoding` in `test_cli.py` prints a document
through a cp1252 stream to hold the UTF-8 promise above. The
finiteness guarantee has tests at each boundary: `TestFiniteNumbers` in
`test_models.py` for the model, the non-finite flag cases in
`test_chords_command.py`, `test_lyrics_command.py`, `test_play_command.py` and
`test_analysis_chunking.py` for the command line, and the
`min_segment_seconds` cases in `test_chroma_baseline.py` — the last of which run
without the DSP stack, which is what proves the engine reads that option before
decoding. The Windows end-to-end run that produced the path and encoding
statements above was made on 2026-10-31 in the environment recorded in
[`../ROADMAP.md`](../ROADMAP.md) §1.
