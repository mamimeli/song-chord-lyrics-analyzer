# Engine comparison

This file is the measurement record. Every number in it was produced by a run whose
environment and date are stated next to it, and every accuracy claim elsewhere in the
repository points back here. Sections 4 and 5 cover lyrics and the chunked-analysis
experiment, §6 covers per-chord confidence, §7 the front-end sweep that moved the
default tuning handling, §9 the cost of the whole product path on Windows 10 and §10
where that cost sits (decode versus warm-up), which is what settles audit §10 P7.
**Read §11 first when the question is "is it accurate enough?"** — it states what
this record does not measure, and the acceptance bars live in ROADMAP §10.
Sections 1–3 — the chord measurement — were lost in an
earlier edit and were **rebuilt on 2026-10-19** together with the harness that produces
them (`scripts/chord_benchmark.py`) and the committed corpus definition
(`tests/fixtures/guitarset_comp_manifest.json`).

## 1. Chord engines — method (2026-10-19)

**Corpus.** GuitarSet v1.1.0 (Zenodo <https://doi.org/10.5281/zenodo.3371780>,
CC BY 4.0): the 180 comping takes, `audio_mono-mic`, 461.3 MiB / 5,484.2 s of audio.
The manifest pins every take by the SHA-256 of its audio file *and* of its JAMS, and
the harness refuses a corpus whose bytes differ, so a run cannot quietly describe a
different corpus. Audio stays in the gitignored cache (`docs/DATASET.md`); only the
manifest (62 KiB: take names, file names, durations and digests) is committed.

**Reference.** One annotation view per run, never mixed in one number:
`--reference instructed` reads JAMS `chord` index 0 (the instructed lead sheet),
`--reference performed` reads index 1 (the performed voicings). Harte spellings are
converted by `evaluation.chords.harte_to_label`; observations with a non-positive
duration occupy no time and are dropped.

**Hypothesis.** The registered engine through its public call,
`ChromaBaselineEngine.analyze()` (`chroma-baseline` 0.1.0), with default options:
mono 22.05 kHz, CQT chroma, hop 2048 (92.879 ms), cosine similarity against the 24
major/minor triad templates plus an `N` state, Viterbi with a flat change penalty of
0.80. Hypothesis segments come from `metrics.adapters.chord_segments()`, which
completes a missing end from the next event or the measured duration and raises rather
than inventing one.

The front end has one knob per measured variable (audit P3) and every run records the
ones it used: `tuning` (`zero` since 2026-10-20, `auto` or `estimate`), `feature`
(`cqt`/`cens`), `harmonic` (HPSS before chroma) and `energy_gate_db`. §7 is the
one-variable-at-a-time comparison that moved the tuning default, and it carries the
table for both settings.

**Metrics** — the implemented definitions, not parallel ones (audit §11):

* `evaluation/chords.py:duration_csr` — duration-weighted CSR, raw and triad-reduced
  (the triad view reduces *both* sides);
* `metrics/segmentation.py:segment_overlap` — MIREX mean segmentation;
* `metrics/segmentation.py:chord_change_detection` — change-point P/R/F1, 0.5 s
  tolerance;
* `metrics/segmentation.py:timing_error` — median boundary distance in both
  directions;
* chord counts, engine wall time, real-time factor and peak RSS (the process
  high-water mark from `performance.py`).

**Protocol.** Same audio, same reference, same hop, one annotation view per run; both
decoders in separate processes; the whole vector is reported, not one number; no take
is excluded, and a hypothesis label with no counterpart still occupies time and is
scored as a miss (`N` included). Each run keeps `per_take.jsonl` (all hypothesis rows,
so a later default change can still be compared against these segmentations),
`aggregate.json` and `aggregate.md` under the gitignored `.cache/`.

**Reproducing it.**

```bash
python scripts/chord_benchmark.py --limit 180 --out .cache/chords/benchmark-viterbi-180
python scripts/chord_benchmark.py --limit 180 --decoder majority --out .cache/chords/benchmark-majority-180
python scripts/chord_benchmark.py --reference performed --out .cache/chords/benchmark-viterbi-180-performed

# §7: one front-end variable at a time, then the adopted default
python scripts/chord_benchmark.py --option tuning=auto --out .cache/chords/p3-baseline
python scripts/chord_benchmark.py --option tuning=zero --out .cache/chords/p3-tuning-zero
python scripts/chord_benchmark.py --option harmonic=true --out .cache/chords/p3-harmonic
python scripts/chord_benchmark.py --option feature=cens --out .cache/chords/p3-cens
python scripts/chord_benchmark.py --option energy_gate_db=-40 --out .cache/chords/p3-energy-gate
python scripts/chord_benchmark.py --fit-confidence --out .cache/chords/benchmark-zero-tuning
```

`scripts/chord_benchmark.py --write-manifest PATH` regenerates the pinned manifest from
a downloaded corpus.

**Environment (the three runs above).** Linux x86_64, kernel 7.0.10-1-liquorix,
CPython 3.13.5, numpy 2.5.3, librosa 1.0.0, soundfile 0.14.0, `chroma-baseline` 0.1.0,
CPU only, commit `53ebb60`, **2026-10-19 (UTC)**. The §7 sweep was run on the same
machine on **2026-10-20** at commit `f72c8a9` and at the commit that carries the
front-end options; its own environment line is inside each run's `aggregate.md`.

## 2. Chord engines — measurement (2026-10-19)

Means over the 180 comping takes; per-take minima and maxima are in each run's
`aggregate.json`. These runs were made with the then-default front end
(`tuning=auto`, librosa's internal estimate); §7 moved the default to `tuning=zero`
and both tables are kept, because a default change is only believable if the
measurement behind it is reproducible.

| Reference | Decoder | CSR | CSR (triad) | Segment overlap | Change F1 | Boundary err. ref→hyp | Boundary err. hyp→ref | Hyp chords | Ref chords |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| instructed | Viterbi, penalty 0.80 | 0.6029 | 0.6091 | 0.8298 | 0.8270 | 0.178 s | 0.187 s | 12.89 | 12.00 |
| instructed | Majority smoother | 0.5300 | 0.5388 | 0.5428 | 0.4033 | **0.056 s** | 0.486 s | 56.86 | 12.00 |
| performed | Viterbi, penalty 0.80 | 0.5186 | 0.5954 | 0.8298 | 0.8270 | 0.178 s | 0.187 s | 12.89 | 12.00 |

Change precision / recall: Viterbi 0.8197 / 0.8585; majority 0.2694 / 0.9923. Summed
engine wall time over the takes was 73.7 s (Viterbi) and 66.6 s (majority) for 5,484.2 s
of audio; peak RSS 303 MiB in each process (the harness's own overhead is not in
either figure). The performed run has identical boundary metrics to the instructed
one because GuitarSet gives both annotation views the same change points — only the
labels differ, which is why the raw CSR drops while the triad view stays near the
instructed score.

**What the numbers say.**

* Viterbi wins on CSR (both views), segment overlap and change F1, and on the
  hypothesis→reference boundary error. The direction of the 2026-10-05 comparison is
  therefore reproduced by an independent run.
* The majority smoother's better reference→hypothesis boundary error is an artefact of
  over-segmentation: 56.86 chords per take against a 12.00-chord reference puts a
  boundary almost everywhere, so every reference boundary has one nearby. Its change
  precision (0.27) and segment overlap (0.54) price that in. This is the case the
  audit's "report the whole vector" rule was written for: a single timing figure would
  have made the worse decoder look better.
* The Viterbi hypothesis is close to the reference in size (12.89 vs 12.00 chords per
  take), which is the behaviour expected from a triad engine on clean solo-guitar
  audio, and it is the main reason CSR is as high as it is.

**Traceability note — the previously cited 0.4260 does not reproduce.**

The repository cited CSR 0.4260 on 180 GuitarSet takes (recorded 2026-10-05, described
as *Viterbi at penalty 0.80*). Running exactly that configuration through the
registered engine on the pinned corpus gives **0.6029**, and the difference is not the
metric: the scoring semantics are pinned by `tests/fixtures/csr_oracle.json`, and
re-scoring a stored hypothesis from the gitignored cache reproduced the old harness's
per-take values exactly (0.6709 instructed, 0.2621 performed for
`00_BN1-129-Eb_comp`). The difference is the hypothesis. The surviving 2026-09-29 sweep
(`.cache/chords/guitarset_all.jsonl`, still on disk) averages 0.4569 with 10.62 chords
per take, while the 2026-10-05 comparison records 17.06 (Viterbi) and 67.65 (majority)
chords per take — three different segmentations, only one of which (12.89) is produced
by the code in `engines/chroma_baseline.py`. The 0.4260 is therefore kept as a
historical measurement of a front end that is no longer in the tree, and **retired as
the registered engine's accuracy figure**. This is exactly the traceability gap the
2026-10-18 audit flagged; the harness and the manifest are what close it.

## 3. Chord engines — verdict

**The registered engine's measured accuracy was CSR 0.6121 (0.6183 triad-reduced) on
180 GuitarSet comping takes against the instructed lead sheet, 2026-10-20** —
the default front end after the §7 sweep. The same engine measured 0.6029 / 0.6091
on 2026-10-19 with the previous default (`tuning=auto`); the difference is the
§7 measurement, not a different metric. The complete vector is in §7 and §2;
quote the date and the reference view with the number. **The current default**
measures **0.6312 / 0.6384** in §8 (2026-10-27), which supersedes both figures.

What this result does **not** establish:

* accuracy on a mixed commercial recording — GuitarSet is one clean acoustic guitar
  with a permissive licence, and the user's ~75 % manual observation is still not a
  measurement (audit §9);
* robustness to reverb, compression or vocals — none of those variables is in this
  corpus (audit P3's remaining proposals are what would measure them; the §7 sweep
  covers tuning, HPSS, CENS and an energy gate);
* that every chord comes with a trustworthy number: each event does carry a
  confidence (§6), but it is a probability *on GuitarSet*, not a guarantee
  elsewhere, and a `G` over `G7` still counts as a miss in the agreement it predicts.

**Consequence for the plan.** Audit P1 is satisfied: there is now a committed harness
(`scripts/chord_benchmark.py`), a fixed reference set
(`tests/fixtures/guitarset_comp_manifest.json`), a scoring path pinned by tests, and an
offline generated-fixture run in `tests/unit/test_chord_benchmark_harness.py`. Every
later chord proposal (P2–P8) reports a before/after vector on this audio instead of an
argument.

---

## 4. Lyrics engines — verdict

**Verdict: `onnx-asr` + Parakeet TDT 0.6B v3 (int8 ONNX) is the first lyrics
engine and was adopted in 2026-10-08 (roadmap Phase E).**

The representative implementation is ``src/song_chord_lyrics_analyzer/engines
/lyrics_parakeet.py`` behind the optional ``lyrics`` extra: it is the only
candidate that merged **accuracy on English (0.08 WER), CPU speed (real-time
factor 0.20), a verified licence and a decidable install**. The measured
quantities live in `docs/ENGINE_COMPARISON.md`s section 25/26 tables; this
section records only the decision and the rules the implementation follows.

* **Speed — the load-bearing requirement.** The bundled model cannot take a
  whole song (``recognize()`` on a 272 s file returned 8 garbled words) and the
  upstream speech VAD returns *nothing* on singing. Every implementation here
  therefore chunks long audio; the section 45 performance numbers belong to the
  engine, not to this table.
* **Weights never leave the cache.** The model is fetched by ``onnx-asr``
  itself, into the Hugging Face cache, and is never stored in this repository,
  never committed and never advertised as a dependency that can be reproduced
  offline.
* **No fake confidence.** The model reports no calibrated per-word confidence;
  ``LyricWord`` keeps ``ConfidenceScore.unknown``. Only a measured value belongs
  in the document, and a WER number only appears with its measurement artifact
  (file, reference, harness).
* **Word timestamps come from the model's own tokens.** A word's end is the next
  word's start; the last word of a window keeps ``end=None`` because the audio
  carries on past it and no boundary was reported.

### Remaining open questions (phase 4)

* **A second candidate is still untested end to end**: faster-whisper
  ``small`` (WER 0.3799, RTF 0.95) beats Parakeet on Tagalog and Spanish —
  whether that transfers to English is not established and would need a
  phase-3 measurement.
* **Chunk boundaries**: a word clipped at a window edge is attributed to the
  earlier window and can be lost; the `--overlap-seconds` option re-hears the
  seam but does not currently repair a clipped word. Whether overlap should be
  turned on by default is the only remaining implementation question.
* **Language detection** is not reported by this backend; a user-level tag can
  be recorded with the `--language` flag.

---

## 5. Chunked chord analysis — measurement (roadmap Phase K, 2026-10-14)

**Why measure at all:** windowing the chord layer (`analysis/chunking.py`,
`songlab analyze --chord-chunk-seconds`) changes what the engine is shown, so
the whole-file pass stays the default and the flag is opt-in until a measurement
says otherwise. These numbers are that measurement.

**Environment:** the machine this repository is developed on, Linux x86_64,
CPython 3.13.5, `chroma-baseline` 0.1.0, numpy 2.x/librosa from the `dsp`
extra, CPU only. Each row's wall time and `ru_maxrss` come from a **separate
process** measuring only the chord layer, so the two modes do not share a
high-water mark.

| Fixture | Mode | Chord call wall | Real-time factor | Peak RSS |
| --- | --- | --- | --- | --- |
| 180 s generated tone | whole file | 3.919 s | 45.93 | 448.2 MB |
| 180 s generated tone | 60 s windows (3) | 3.880 s | 46.40 | 309.3 MB |
| 600 s generated tone | whole file | 8.409 s | 71.35 | 996.2 MB |
| 600 s generated tone | 60 s windows (10) | 8.027 s | 74.75 | 309.3 MB |

**What the numbers say.** Window length, not song length, fixes the working
set: the 10-window run peaks at the same 309 MB as the 3-window one, while the
whole-file pass grows with the decode (448 MB at 3 minutes, 996 MB at 10
minutes — a 3.2x reduction at 10 minutes). Runtime is unchanged within noise,
so the memory is bought for free on these fixtures rather than traded against
speed.

**What it costs in output.** On a 480 s tonal fixture (C-Am-F-G, 8 s each,
generated by `tests/fixtures/audio.py`) a whole-file pass and a 60 s windowed
pass produced **the same 60 chords in the same order with the same labels**, and
one boundary of sixty moved by 94 ms — at a 60 s seam, because a change inside a
window's first frame is attributed to the window's own start. Both runs finished
`succeeded`; the windowed run records `chords_chunk_seconds: 60` in provenance
and `60 chords, 8 windows` in its step line. Timing for that pair was measured
in one process (windowed second, warm page cache), so its 8.8 s vs 5.7 s is
reported as *not slower*, not as a speed-up.

**Open question.** Whether a chord-heavy mix (rather than a synthetic triad
progression) shifts more than one boundary per seam is not established here:
the benchmark corpus in `benchmark/` is the place for that, and no accuracy
claim should be made from these three fixtures.

---

## 6. Per-chord confidence — measurement (roadmap Phase I P2, 2026-10-20)

> **Historical record (updated 2026-10-21).** The constants in this section
> (slope 23.4861 / intercept 0.1973) describe the binary-template front end
> measured on 2026-10-20. The **shipped** constants after the §8 change are
> slope **28.7942** / intercept **−0.0738**, with held-out Brier **0.1485** and
> ECE **0.0363**. The 2026-10-20 tables are kept because they document the
> method and the calibration before the scoring-stage change; do not quote them
> as the current engine's numbers.

**What is reported.** `ChordEvent.confidence` is no longer `unknown`. For every
event the engine averages, over the frames the event covers, the **score margin**
of the label it emitted: that label's cosine similarity minus the best similarity
any other state reaches on the same frame, `N` included
(`engines/chroma_baseline.py:segment_margins`). A frame the Viterbi decoder kept
on its label against the frame's own preference contributes a *negative* margin,
so a smoothed boundary is visible in the number instead of hidden by it. The raw
margin is kept in `ChordEvent.metadata["score_margin"]`, so the derived number
can always be audited against its evidence.

**How a margin becomes a probability.** A logistic,
`p = sigmoid(23.4861 * margin + 0.1973)` (`margin_confidence`), fitted by
duration-weighted IRLS on the events of the **90 even-indexed takes** of the
committed manifest and measured on the **90 odd-indexed takes**, which never
influenced the constants. Agreement is the rule `duration_csr` applies: exact
label equality over the overlapping time, `N` only matching `N`.

**Reproducing it.**

```bash
python scripts/chord_benchmark.py --fit-confidence --out .cache/chords/benchmark-zero-tuning
```

**Fit and held-out result** (from `confidence_fit.json`; the same 90/90 split,
run over the §7 default front end):

| Split | Takes | Events | Duration | Accuracy | Brier | ECE |
| --- | --- | --- | --- | --- | --- | --- |
| fitted (even takes) | 90 | 1,163 | 2,738.7 s | 0.5736 | 0.1579 | 0.0227 |
| held out (odd takes) | 90 | 1,160 | 2,745.5 s | 0.5836 | 0.1420 | 0.0161 |

The fit converged in 6 Newton steps to slope 23.4861 / intercept 0.1973; the
engine carried exactly those on 2026-10-20, and §8 refitted them for the
current front end. **The constants follow the front end:** the
§7 sweep moved the tuning default from `auto` to `zero`, which changed the
chroma and therefore the margins, so the logistic was refitted on the same
corpus. The pre-sweep fit (`tuning=auto`) was slope 24.2814 / intercept 0.1552
with held-out Brier 0.1436 / ECE 0.0206 — kept here so a reader can see the
two numbers describe two different front ends, not a re-tune of the same one.

**Calibration of the whole run** (all 180 takes, 2,323 events, 5,484.2 s; every
event reported a confidence, so no duration is unknown):

| Reported band | Events | Duration | Accuracy | Mean confidence |
| --- | --- | --- | --- | --- |
| very low (below 0.2) | 134 | 385.0 s | 0.100 | 0.154 |
| low (0.2–0.4) | 467 | 1,123.9 s | 0.340 | 0.310 |
| medium (0.4–0.6) | 674 | 1,423.8 s | 0.500 | 0.505 |
| high (0.6–0.8) | 596 | 1,362.9 s | 0.736 | 0.698 |
| very high (0.8–1.0) | 452 | 1,188.7 s | 0.873 | 0.885 |

Pooled accuracy 0.5786, Brier 0.1500, expected calibration error 0.0234. A band's
accuracy and its mean confidence track within about 0.04 everywhere, which is what
"calibrated" means here.

**Risk–coverage.** The useful question is not only "is the number calibrated?" but
"if the user ignores low-confidence chords, how much is left and how good is it?":

| Confidence at least | Coverage | Accuracy |
| --- | --- | --- |
| 0.50 | 0.608 | 0.734 |
| 0.60 | 0.465 | 0.800 |
| 0.70 | 0.339 | 0.843 |
| 0.80 | 0.217 | 0.873 |
| 0.90 | 0.083 | 0.890 |

Held out, the same thresholds give coverage 0.629 / 0.472 / 0.364 / 0.248 / 0.097 at
accuracy 0.732 / 0.808 / 0.861 / 0.881 / 0.887 — indistinguishable within the
sampling noise of 90 takes. Roughly half the duration can be shown with more than
four chords in five right; that is the user-facing value of the number.

**P2 changed no labels.** The confidence work alone (2026-10-20, before the §7
sweep) reproduced the §2 run's per-take scores, counts, boundaries and timing
exactly (0 differences over the ten scored fields, row by row against
`.cache/chords/benchmark-viterbi-180`). The §7 front-end change *does* move the
labels — it is a different chroma — which is why that sweep is measured, not
assumed.

**Two different ways to average, stated once.** §7's 0.6121 is the *mean of
per-take CSR*; the 0.5786 above pools every event's duration across the corpus,
so a long take weighs what it lasts. Neither replaces the other: the table
answers "how well does a run do on a typical take?", §6 answers "over this hour
of audio, how much is right?".

The harness's own wall clock around `analyze()` summed to 43.2 s for 5,484.2 s of
audio (decode included), with a 260.4 MiB process high-water mark across the 180
takes and no harness-side errors.

**Environment.** Linux x86_64, kernel 7.0.10-1-liquorix, CPython 3.13.5, numpy
2.5.3, librosa 1.0.0, soundfile 0.14.0, `chroma-baseline` 0.1.0, CPU only, commit
`f72c8a9` plus this change, **2026-10-20 17:11 UTC**. The manifest digest
was `de6338fb…` (the pinned corpus).

**Verdict.** The number is calibrated on the corpus it was fitted on, and its
risk–coverage curve is monotone and wide enough to be useful. What it is *not*:

* **Not transferable as a probability.** GuitarSet is one clean acoustic guitar; on a
  mixed commercial recording the ordering still holds, the probabilities do not.
* **Not measured for `N`.** GuitarSet has no notated silence, so an event claiming
  silence gets the same mapping by extrapolation, not by evidence.
* **Not a verdict on extension chords.** The reference is the exact label, so a `G`
  detected over a `G7` scores as a miss even though a player would accept it. The
  triad-reduced CSR (0.6183) shows how small that effect is on this corpus.
* **Not fused with the decoder.** The confidence is computed after decoding and never
  feeds back into it; a future change that uses it (automatic correction, fusion)
  must publish a new measurement on this harness, not just a claim.

---

## 7. Front-end robustness — one variable at a time (roadmap Phase I P3, 2026-10-20)

> **Historical record (updated 2026-10-21).** This section measures the front
> end with the binary templates and raw chroma of its day. §8 supersedes its
> scoring stage; the `tuning=zero` adoption and the HPSS/CENS rejections remain
> the current front-end decision.

**Why this exists.** The audit's P3 asks whether the chroma front end — which until
2026-10-20 was just `librosa.feature.chroma_cqt(y, sr, hop_length=2048)` with no
explicit tuning, no harmonic attenuation and no energy gate — is throwing accuracy
away. Each option is measured alone, with everything else at its default, and each
run records what it used, so a reader can reproduce a row rather than trust it.

```bash
python scripts/chord_benchmark.py --option tuning=auto     --out .cache/chords/p3-baseline
python scripts/chord_benchmark.py --option tuning=zero     --out .cache/chords/p3-tuning-zero
python scripts/chord_benchmark.py --option tuning=estimate --out .cache/chords/p3-tuning-estimate
python scripts/chord_benchmark.py --option harmonic=true   --out .cache/chords/p3-harmonic
python scripts/chord_benchmark.py --option feature=cens    --out .cache/chords/p3-cens
python scripts/chord_benchmark.py --option energy_gate_db=-40 --out .cache/chords/p3-energy-gate
```

| Front end | CSR | CSR (triad) | Segment overlap | Change F1 | Boundary err. ref→hyp | Hyp chords | Wall | Peak RSS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `tuning=auto` (previous default) | 0.6029 | 0.6091 | 0.8298 | 0.8270 | 0.178 s | 12.89 | 69.5 s | 303.9 MB |
| **`tuning=zero` (new default)** | **0.6121** | **0.6183** | **0.8343** | **0.8296** | **0.168 s** | 12.91 | 55.2 s | 260.5 MB |
| `tuning=estimate` | 0.6062 | 0.6123 | 0.8313 | 0.8271 | 0.170 s | 12.93 | 60.8 s | 304.8 MB |
| `harmonic=true` (HPSS) | 0.5890 | 0.5953 | 0.8267 | 0.8103 | **0.139 s** | 13.74 | 464.1 s | 373.4 MB |
| `feature=cens` | 0.5475 | 0.5538 | 0.7228 | 0.7315 | 0.649 s | 8.91 | 58.2 s | 303.9 MB |
| `energy_gate_db=-40` | 0.6046 | 0.6107 | 0.8318 | 0.8284 | 0.178 s | 12.77 | 66.7 s | 304.6 MB |

All six runs: 180 comping takes, instructed lead sheet, Viterbi at penalty 0.80,
same manifest, same machine as §2 (Linux x86_64, CPython 3.13.5, numpy 2.5.3,
librosa 1.0.0, CPU only), **2026-10-20**, at the commits stated in each run's
`aggregate.md`.

**Paired deltas against `tuning=auto`.** Each row below is the mean of the 180
take-wise differences (the runs are paired by take, so the noise cancels) with
the standard error of that mean:

| Front end | Δ CSR (± SE) | Δ change F1 (± SE) | Takes with higher CSR |
| --- | --- | --- | --- |
| `tuning=zero` | **+0.0092 ± 0.0033** | +0.0027 ± 0.0028 | 65 / 180 |
| `tuning=estimate` | +0.0033 ± 0.0023 | +0.0001 ± 0.0014 | 24 / 180 |
| `energy_gate_db=-40` | +0.0017 ± 0.0010 | +0.0015 ± 0.0022 | 9 / 180 |
| `harmonic=true` | **−0.0139 ± 0.0051** | **−0.0167 ± 0.0055** | 64 / 180 |
| `feature=cens` | **−0.0554 ± 0.0094** | **−0.0955 ± 0.0122** | 54 / 180 |

The gate and HPSS win on more takes than they lose yet lose in duration: a few
takes suffer a large regression that a mean over takes hides and a duration
average surfaces. That is exactly the reason the audit asks for the whole vector
and not one number.

**What each row says.**

* **`tuning=zero` was adopted as the default.** In librosa 1.0,
  `chroma_cqt(tuning=None)` (what `tuning=auto` does) *estimates the recording's
  tuning from the signal* and shifts the CQT filters by that fraction of a bin,
  while `tuning=0.0` keeps the A440 grid. On GuitarSet — which measures 4–10
  cents sharp on every take checked — trusting A440 gains +0.0092 CSR with no
  metric worse, and it is also ~20 % less CPU and ~43 MB less memory because
  the tuning estimate is skipped. The mechanism is unproven; the measurement is.
* **`tuning=estimate` does not beat `zero` and barely beats `auto`.** It
  measures the deviation explicitly (`estimate_tuning`, recorded in cents as
  `tuning_cents`) and passes the same shift `auto` would have applied, so its
  +0.0033 over `auto` is within noise, and it stays 0.006 below `zero`.
  GuitarSet being in tune is the likely explanation, and no corpus here tests
  detuned audio.
* **HPSS is a loss, and a big cost.** The harmonic component costs 464 s of wall
  time for the same corpus (6.7× the default) and drops both CSR (−0.0139) and
  change F1 (−0.0167). On solo guitar the percussive component carries the
  attack the change detector uses; removing it blurs boundaries. Not adopted.
* **CENS is worse at everything except speed.** −0.0554 CSR and −0.0955 change
  F1, with the hypothesis collapsing to 8.91 chords per take against a 12.00
  reference: CENS's temporal smoothing swallows short chords. Its boundary error
  (0.649 s) is the worst in the table. Not adopted.
* **The −40 dB energy gate changes almost nothing** (+0.0017, within noise) and
  does not make GuitarSet emit a single `N`: there is no notated silence in it.
  It stays an option, because the audit's stated purpose — honest `N` in
  near-silence — cannot be measured on this corpus at all.

**Cross-check against the second annotation view.** Re-running the adopted default
on the `performed` voicings (JAMS `chord` index 1) and pairing it against the
recorded `tuning=auto` run for that view gives the same direction: CSR
0.5186 → **0.5250** (+0.0064 ± 0.0019), triad CSR 0.5954 → **0.6019** (+0.0064
± 0.0034), segment overlap +0.0045 ± 0.0020, change F1 +0.0027 ± 0.0028. The
improvement is a property of the front end, not of one reference view.

**What this does *not* establish.** That `tuning=zero` is better in general. Every
take in this corpus is played on a tuned instrument; a detuned recording is the
case where `auto` should win, and this corpus cannot express it. `tuning=auto`
stays one `--option` away for exactly that reason. The reverb, compression,
vocal-mix and onset variables of P3 are still unmeasured; the change penalty
itself (0.80 here) was fitted on the *old* front end and was re-swept in §8 to
0.40.

**Consequence for the recorded numbers at that date.** The default then produced
CSR **0.6121** / **0.6183** triad / overlap **0.8343** / change F1 **0.8296**
against the instructed lead sheet, and the §6 confidence was refitted for it
(Brier 0.1420, ECE 0.0161 held out). §8 supersedes both for the current
engine. The §2 numbers remain the record of the previous default;
both are in this file so that "what changed" is a diff between two measurements,
not a story.

## 8. Harmonic templates, chroma compression, the change penalty and the minimum segment (roadmap Phase I, 2026-10-21; 2026-10-27 addendum)

**Question.** The §7 sweep left the engine's *scoring* untouched (binary triads,
raw chroma) and explicitly noted that the change penalty had not been re-swept
for the new front end. Can the same 180-take measurement carry a better scoring
stage without a learned model? A real-song check on 2026-10-27 then asked a
second question: how much of the remaining clutter is genuine harmony and how
much is sub-second decoder flicker?

**Method.** Same manifest, corpus and reference as §1/§2: 180 GuitarSet comping
takes, **instructed** lead sheet (JAMS `chord` index 0), SHA-256-verified audio,
no time range, one process, same machine (Linux x86_64, CPython 3.13.5, numpy
2.5.3, librosa 1.0.0, CPU only), **2026-10-21**, with the minimum-duration
addendum measured **2026-10-27**. The hypothesis comes from the registered
`chroma-baseline` engine through `analyze()`; scoring uses
`evaluation.guitarset.score_take` and the §11 vector. The harness omits
`--change-penalty` by default so an unpassed flag means *the engine's measured
default*, not a stale script constant; the effective value is recorded in every
row and in the aggregate.

Reproduce the adopted run with:

```bash
python scripts/chord_benchmark.py --corpus-dir .cache/chords/guitarset \
  --limit 180 --out .cache/chords/bench-v3-default
```

and the confidence fit with `--fit-confidence` on the same run.

The adopted row's figures are pinned as a committed accuracy vector,
`benchmark/reference/chroma_baseline-instructed.json` (CSR 0.6312, triad 0.6384,
overlap 0.8454, change F1 0.8553, 13.07 hypothesis chords per take, means over
the 180 instructed takes), so the reproduce command above also *checks* the
engine: it prints one line per tracked metric against this table and exits 3 if
one regressed. That vector was transcribed from this section on 2026-11-01, not
re-measured — its `notes` say so, and its environment block records the Linux
run of 2026-10-27 that produced the numbers. Boundary-error columns are
deliberately absent: this section does not say whether that column is a mean or
a median, and pinning the wrong statistic would make every later comparison a
lie. See [DEVELOPMENT.md](DEVELOPMENT.md) §3 for the flags.

**Adopted configuration.**

| Parameter | Previous default | Adopted default | Option to restore |
| --- | --- | --- | --- |
| Chroma compression | none (raw) | `sqrt` | `feature_transform=raw` |
| Triad templates | three bins at 1.0 | root 1.00, third 0.95, fifth 0.85, opposite third −0.35 | `template_weighting=binary` |
| Viterbi change penalty | 0.80 | 0.40 | `change_penalty=0.8` |
| Minimum segment | none | **0.50 s** | `min_segment_seconds=0` |

**Measured runs (all 180 takes, same corpus and reference).**

| Run | CSR | CSR (triad) | Segment overlap | Change F1 | Boundary err. ref→hyp | Hyp chords | Wall |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Previous defaults (§7, measured 2026-10-20) | 0.6121 | 0.6183 | 0.8343 | 0.8296 | 0.168 s | 12.91 | 43.2 s |
| First scoring step (0.30 s, 2026-10-21) | 0.6283 | 0.6356 | 0.8403 | 0.8347 | 0.154 s | 13.84 | 64.0 s |
| **Adopted (sqrt + harmonic + p=0.40 + 0.50 s, 2026-10-27)** | **0.6312** | **0.6384** | **0.8454** | **0.8553** | **0.158 s** | 13.07 | 53.3 s |
| Ablation: 0.70 s minimum | 0.6316 | 0.6384 | 0.8464 | 0.8577 | 0.169 s | 12.35 | 45.7 s |
| Ablation at 0.30 s: no minimum merge | 0.6273 | 0.6345 | 0.8384 | 0.8279 | 0.154 s | 14.16 | 57.2 s |
| Ablation at 0.30 s: binary templates | 0.6219 | 0.6289 | 0.8431 | 0.8389 | 0.137 s | 13.39 | 50.7 s |
| Ablation at 0.30 s: raw chroma | 0.6194 | 0.6268 | 0.8147 | 0.7956 | 0.110 s | 16.98 | 52.0 s |
| Ablation at 0.30 s: change penalty 0.60 | 0.6266 | 0.6332 | 0.8330 | 0.8457 | 0.199 s | 11.94 | 50.7 s |
| Ablation at 0.30 s: change penalty 0.80 | 0.6189 | 0.6252 | 0.8128 | 0.8382 | 0.264 s | 10.69 | 51.8 s |

The wall column is the sum of the per-take `analyze()` times in each run's
aggregate (decode included), not the shell's elapsed time and not a machine
benchmark; the baseline row is the 2026-10-20 run of the previous defaults with
the same harness, which is why its wall differs from the §7 table's shell
elapsed figure. The component ablations were measured at a 0.30 s minimum
because that was the default then; they answer "which component contributes",
not "what does 0.50 s do to this component".

**Paired deltas (mean of the 180 take-wise differences ± standard error).**

| Comparison | Δ CSR | Δ change F1 | Wins / losses in CSR |
| --- | --- | --- | --- |
| Adopted vs previous defaults | **+0.0191 ± 0.0071** (95 % CI +0.0052..+0.0329) | **+0.0257 ± 0.0068** | 108 / 62 |
| Adopted vs the 0.30 s step | +0.0028 ± 0.0007 (95 % CI +0.0014..+0.0042) | +0.0206 ± 0.0027 | 45 / 11 |
| Adopted vs 0.70 s | −0.0004 ± 0.0013 (within noise) | −0.0024 ± 0.0016 | 18 / 22 |
| At 0.30 s: harmonic vs binary templates | +0.0065 ± 0.0064 | −0.0042 ± 0.0032 | 95 / 71 |
| At 0.30 s: sqrt vs raw chroma | +0.0089 ± 0.0044 | +0.0391 ± 0.0075 | 98 / 65 |
| At 0.30 s: adopted vs p=0.80 | +0.0095 ± 0.0044 | −0.0035 ± 0.0040 | 72 / 57 |

**Reading the result.** The adopted combination is a measured win on the target
metric, with overlap, change F1 and median boundary error all better than the
previous defaults; the 95 % interval on the CSR delta excludes zero. The
minimum-duration change is small on CSR (+0.0028) but large on change F1
(+0.0206) and overlap (+0.0052): the extra chords it removes are the sub-second
flicker that used to reach the chart. 0.70 s is statistically indistinguishable
on CSR and slightly better on F1, but it costs 0.011 s of median boundary error
and risks swallowing genuine fast changes; 0.50 s is the balanced measured
choice. The component ablations are noisier: harmonic templates alone are within
one standard error of the binary set, so the CSR gain is the *combined* effect,
not a claim that every component is individually significant. Raw chroma loses
0.0089 CSR and 0.039 change F1 — without compression the scores are dominated by
the loudest partial and the decoder changes far more often (16.98 chords per
take against 13.07). The change penalty remains a trade-off: 0.60 gives the best
change F1 (0.8457) but a slightly lower CSR.

**Real-song sequence check (local, 2026-10-27).** A private 5:27 Spanish worship
recording and its hand-written chart were used as a *sequence* reference (chart
order, no timestamps): `scripts/chord_chart_check.py` parsed 86 chart chords and
aligned them to 101 detections. **84 of 86 chart chords were found in order
(97.7 %), with 2 substitutions and 15 extra detections**; the 0.50 s minimum
reduced the extras from 16 to 15 without losing a chart chord, while a 1.0 s
minimum lost a chart chord. This is sequence agreement, not duration accuracy,
and the song/chart are not committed (copyright); it is a product signal that
the harmony is mostly right on a real full-band mix and that the visible
clutter is largely short transitions. It is not a replacement for the GuitarSet
number and is not quoted as one. The tool is
`scripts/chord_chart_check.py`; its semantics are in `evaluation/chart.py` and
`docs/BENCHMARK.md`.

**The 109-class reference probe (rejected).** The `external/Guitariz` submodule
ships a small CRNN exported to ONNX (`backend/chord_model.onnx`, 109 classes,
MIT repository). It was read as reference material only and evaluated on 30
GuitarSet takes with a throwaway script that reproduced the project's log-CQT
front end and took the raw argmax, with no smoothing: **0.2159 raw CSR / 0.2555
triad CSR**. That is far below the registered engine and it is a 30-take probe,
not a harness run, so it is not a like-for-like number. The weights were not
copied, the model is not a dependency, and it is not adopted. The strong public
BTC checkpoints are CC-BY-NC-SA (Isophonics/Robbie Williams/UsPop2002 training
data) and conflict with this project's GPL-3.0-or-later distribution, so they
are out. A held-out MLP on chroma context trained on 90 takes and tested on the
other 90 added roughly +0.03 triad CSR over the template baseline in the same
throwaway harness, but it was not converted into a shipped engine: it would
need its own licence-audited feature/inference path and a real generalisation
check beyond solo guitar. That remains the Phase I next step.

**Confidence refit.** Every change above moves the score-margin scale, so the
logistic was refitted on the 90 even-indexed takes and measured on the 90
odd-indexed takes with `--fit-confidence`: **slope 28.7942, intercept −0.0738**,
held-out **Brier 0.1485**, **ECE 0.0363**, and accuracy **0.809** on events
scoring at least 0.60 (coverage 0.476). The previous constants (29.8735 /
−0.1484, Brier 0.1497, ECE 0.0357) described the 0.30 s step; the earlier
23.4861 / 0.1973 binary-template fit is in §6 as history. The mapping is still a
probability *on GuitarSet*, not a universal guarantee.

**What this does not establish.** That the engine is 93 % accurate on arbitrary
songs. It is 0.6312 by duration CSR on a solo-acoustic-guitar corpus with a
strict lead-sheet reference; a proprietary app's published percentage uses a
different corpus, a different matching rule and a learned model, and the two
numbers are not comparable. It also does not establish anything about detuned
recordings, vocals, drums or full-band mixes: the corpus is one instrument. The
next measured step is a licence-clean learned engine, not a larger vocabulary
bolted onto the template matcher (the conservative seventh pass emitted sevenths
on 21–53 % of the duration against a 13.4 % reference and was not adopted).

---

## 9. Full product path cost — measured on Windows 10 (roadmap Phase K, 2026-10-31)

**Why measure this.** Phase K asks for the real-time factor of the *product
path*, not of one engine: what a person waits for when `songlab analyze` runs
every registered layer on one file. The §45 harness already computes the number
(`performance.real_time_factor` = audio seconds ÷ processing seconds, so above
1.0 is faster than real time); it had only ever been reported per layer.

**Environment.** Windows 10 22H2 build 19045.6466, Intel Core i5-7200U @ 2.50
GHz, 8 GB RAM, CPython 3.12.0 (AMD64), numpy 2.5.4, librosa 1.0.0, soundfile
0.14.0, onnx-asr 0.12.0 with onnxruntime 1.31.1, FFmpeg and ffprobe 9.0.2 from
winget, CPU only, GUI not involved. Measured 2026-10-31. Two stacks were used on
purpose: the full one (`.[gui,dsp,playback,lyrics]`, where the lyrics layer
runs) and the one a `.[dsp]`-only install gets (`.venv-dspjob` = `.[dev,dsp,gui]`,
where the lyrics step reports `skipped`).

**Fixtures.** `samples/vocadito_2.wav` (committed: 35.208 s, pcm_s16le, mono,
44.1 kHz) and a **cost fixture** — the same file looped eight times with the
stdlib `wave` module to 281.664 s, written to the machine's temp directory, used
once per row and deleted. It is not a song and no output of it is quoted; only
its length matters, because the cost of every layer here is per second of audio.

| Path | Fixture | Runs (total processing) | Real-time factor |
| --- | --- | --- | --- |
| chords + lyrics + key + tempo | 35.208 s | 23.035 / 26.781 / 27.375 s | 1.53 / 1.31 / 1.29 |
| chords + lyrics + key + tempo | 281.664 s | 88.380 / 67.518 s | 3.19 / 4.17 |
| without the `lyrics` extra | 35.208 s | 7.283 / 7.556 s | 4.83 / 4.66 |
| without the `lyrics` extra | 281.664 s | 10.521 / 11.119 / 14.136 s | 26.77 / 25.33 / 19.93 |

**Where the time goes** (one run of each fixture, the service's own per-step
lines): on the 35.208 s file, chords 4.144 s, lyrics 16.690 s, key 0.329 s,
tempo 1.873 s; on the 281.664 s file, chords 5.172 s, lyrics 56.779 s, key
2.030 s, tempo 3.537 s. **The lyrics engine is the product path's cost**: 72 % of
the first total and 84 % of the second, and it is the reason the full path runs
near real time on a short clip while the same machine analyses chords, key and
tempo at 20–27x.

**The chord layer barely grows with the file.** Alone (`songlab chords`), the
35.208 s clip cost 4.280–4.663 s (RTF 7.55–8.23) and the 281.664 s fixture
5.633–6.021 s (RTF 46.8–50.0): eight times the audio for 1.4 times the time, so
a per-run fixed cost dominates a short clip and the real-time factor rises with
song length. That matches §5's Linux numbers (45.9 at 180 s, 71.4 at 600 s on
generated tones) rather than contradicting them. The probe's separate
`startup_time_seconds` — the engine's own import — was ~0 on every row because
the CLI had already imported the front end before the probe started, so the
fixed part sits inside the processing window, not in startup.

**No peak-RSS column.** `performance.peak_rss_bytes` is POSIX-only by design
(`resource.getrusage`), so on Windows it is `null` and no figure is reported —
the §5 memory comparison stays a Linux measurement.

**What this does not establish.** Speed on any other machine, on GPU, or inside
the window (the GUI runs the same service on a worker thread and is not timed
here). It does not say the transcription is good, and it is not an extrapolation:
a longer file would need its own run. The spread between the two long full-path
runs is 31 % (lyrics 56.8 s vs 73.8 s), so these are single-digit-count
measurements on a laptop, not constants.

---

## 10. Where an analysis spends its time — audit §10 P7 measured (Windows 10, 2026-11-01)

**Why measure this.** `docs/CHORD_DETECTION_AUDIT.md` §10 P7 proposes an
application-level cache of decoded samples, keyed by path and decode parameters,
on the evidence that "a song is decoded at least three times (chords, key,
tempo)". The premise was never timed, and P7 promises two things with it:
latency and less peak memory. A refactor of the orchestration — a cache object
with an invalidation policy, a memory bound and thread-safety against the GUI's
worker — is not worth paying for an unmeasured saving.

**Tool.** `scripts/analysis_cost_probe.py` (developer tooling, committed 2026-11-01).
It runs `run_analysis()` three times in one process and reports, per run, the
wall total, each engine's own section 45 processing time, and every decode the
engines performed — timed by wrapping `decode_audio` in each engine module for
the duration of one run and removing it again, and recorded as the cache would
key it (file plus effective parameters with the service's own defaults filled
in). `--chroma` adds the *other* half of P7: one bare
`librosa.feature.chroma_cqt(y, sr, hop_length=2048)` call of the request the key
engine makes, timed after the analyses, so warm. `--make-fixture` writes the
generated tone file, so no recording is needed. Reproduce with:

```bash
python scripts/analysis_cost_probe.py --make-fixture .cache/cost_fixture.wav --seconds 120
ffmpeg -i .cache/cost_fixture.wav -b:a 192k .cache/cost_fixture.mp3   # FFmpeg 9.0.2 (winget)
python scripts/analysis_cost_probe.py .cache/cost_fixture.wav samples/vocadito_2.wav --runs 3 --chroma
python scripts/analysis_cost_probe.py .cache/cost_fixture.mp3 --runs 3 --chroma
```

The `--json` record stays in the gitignored cache; nothing the probe writes is a
shipped artefact.

**Environment.** Windows 10 build 19045 SP0 AMD64, CPython 3.12.0, numpy 2.5.4,
librosa 1.0.0, soundfile 0.14.0, onnx-asr 0.12.0, FFmpeg 9.0.2, CPU only, commit
`e24a425`. Measured 2026-11-01. The lyrics engine is unregistered by default, so
the layers under test are chords, key and tempo; `input_hash` is off because
provenance hashing is not the subject.

**Inputs.** a generated 120.000 s tone file (C–G–A minor–F loop, 22 050 Hz mono
PCM_16) and its 192 kbit/s MP3 transcode, each probed in its own fresh process;
and `samples/vocadito_2.wav` (35.208 s, committed), probed *second* in the WAV
process — that ordering is itself one of the findings, so it is stated, not
hidden.

| Input | Run | Total | chords | key | tempo | decodes | decode s | share | repeats s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WAV 120 s | 1 (cold) | 7.03 | 4.16 | 0.63 | 2.00 | 3 | 1.59 | 22.7 % | 0.06 |
| WAV 120 s | 2 | 1.65 | 0.67 | 0.60 | 0.32 | 3 | 0.08 | 4.9 % | 0.05 |
| WAV 120 s | 3 | 1.62 | 0.67 | 0.56 | 0.32 | 3 | 0.08 | 5.1 % | 0.05 |
| MP3 120 s | 1 (cold) | 7.15 | 4.11 | 0.71 | 2.09 | 3 | 1.79 | 25.0 % | 0.20 |
| MP3 120 s | 2 | 1.84 | 0.73 | 0.66 | 0.39 | 3 | 0.30 | 16.1 % | 0.20 |
| MP3 120 s | 3 | 1.81 | 0.72 | 0.63 | 0.39 | 3 | 0.30 | 16.4 % | 0.20 |
| `vocadito_2.wav` 35.2 s (warm process) | 1 | 0.70 | 0.27 | 0.24 | 0.11 | 3 | 0.08 | 11.3 % | 0.05 |
| `vocadito_2.wav` 35.2 s (warm process) | 2 | 0.71 | 0.27 | 0.25 | 0.11 | 3 | 0.08 | 11.4 % | 0.06 |
| `vocadito_2.wav` 35.2 s (warm process) | 3 | 0.72 | 0.27 | 0.23 | 0.14 | 3 | 0.08 | 10.4 % | 0.05 |

`repeats s` is every decode after the first — the only part a cache could remove.

**The premise holds, exactly as the audit says.** Every run decodes the file
three times, once each for chords, key and tempo, and all three are *one*
request: `sample_rate=22050, mono=True, offset=0.0, duration=None, backend=auto`
for the same file. They only compare equal once the service's defaults are
filled in — the chord engine writes `offset`/`duration` explicitly
(`engines/chroma_baseline.py:1035-1042`), the key and tempo engines omit them
(`engines/key_krumhansl.py:223`, `engines/tempo_librosa.py:142`). Each of those
decodes materialises 10.1 MiB of float32 samples for 120 s (3.0 MiB for 35.2 s).

**The decode half of P7 is small.** The repeats cost 0.05–0.07 s of a 1.62 s
steady-state WAV run (3–4 %), 0.20 s of a 1.81 s MP3 run (11 %), 0.05–0.06 s of
a 0.72 s run of the committed sample (7 %), and 0.06 / 0.20 s of the ~7 s cold
runs (0.9 % and 2.8 %). A cache cannot remove the *first* decode, which is why
the cold run's 1.59 / 1.79 s decode total collapses to 0.08 / 0.30 s once warm:
that first decode pays for opening the file, the decoder and the resampler, and
it is paid in full whatever the orchestration looks like.

**The cold run is warm-up, and it is once per process.** The step that dominates
run 1 is the chord engine: 4.16 s against 0.67 s in steady state, with the tempo
engine at 2.00 s against 0.32 s. Subtracting the measured decodes from those
steps (arithmetic on the table, not a separate probe): the cold run's first
decode costs 1.53 s on the WAV and 1.59 s on the MP3, and it falls inside the
chord engine's own step, so of the chord engine's cold 4.16 s about 1.5 s is the
decoder and resampler starting up and about 1.9 s is the engine's own first call
into librosa/numba; the tempo engine's ~1.65 s of cold overhead is its first call
alone. `samples/vocadito_2.wav`, analysed *second* in the same process, shows no
cold run at all: 0.70 s total for 35.2 s of audio, while §9 measured 4.28–4.66 s
for `songlab chords` alone on that same file in a fresh process. Same engine,
same file, 6× the time — the difference is the interpreter's first call, which
lands inside the processing window (§9's startup note) and which no cache
touches. For the CLI that is once per invocation; for the window, once per
session.

**The chroma half is the bigger prize, and it is not a cache.** One
`chroma_cqt` call of the key engine's request costs 0.54 / 0.56 / 0.55 s on the
120 s WAV, 0.55 / 0.56 / 0.54 s on the MP3 and 0.21 / 0.21 / 0.20 s on the
35.2 s sample — all measured after the analyses, so warm. The key step's whole
steady-state cost is 0.56–0.66 s on the long files, so it is essentially that
one call: computing the chromagram once and handing it to both engines would
remove something like a third of a warm run, 6–10× what the decode cache is
worth. It is not free, though. With the adopted defaults (HPSS off, energy gate
off, `sqrt` applied after `compute_chroma`), the two requests differ **only** by
`tuning`: the chord engine passes `tuning=0.0` because that is its measured
default (§7), and the key engine omits the keyword, which asks librosa to
estimate it. Sharing the array therefore means changing what the key engine
sees, which is a label-affecting change — exactly the risk P7 itself names, and
the reason its validation rule is "output equality first".

**No memory claim.** `performance.peak_rss_bytes` is POSIX-only, so this Windows
run reports `null`: P7's memory half is recorded here as *not assessed*, not as a
saving. The three buffers are produced one after another and each engine
releases its copy, so the peak is certainly not 3 × 10.1 MiB — and how far below
that it sits is a `resource.getrusage` question on Linux, not an arithmetic one.

**Verdict.** P7's **shared-decode** half is measured and **not adopted**: at most
0.2 s of a warm run and 2.8 % of a cold one on this machine, against a cache
lifecycle, an invalidation policy and a thread-safety contract with the GUI
worker. P7's **shared-chroma** half stays open (`[ ]`) and is *blocked on key
ground truth*, not on orchestration: the saving is real (~0.5 s of a warm 120 s
run) but it requires the key engine to adopt `tuning=0.0`, and there is no
committed licensed key annotation to score that against (`docs/DATASET.md`: the
key category is still uncollected as a versioned dataset entry), so the change
cannot be validated today. What this section does *not* establish: any number on
another machine or OS, peak RSS, GPU, the window's worker-thread path, the full
path with the lyrics layer (that is §9), or any accuracy claim at all.


## 11. What this record does not measure (2026-11-02)

Added with the priority change, because the honest scope of a measurement record
belongs in the record itself. Everything above stays as measured; this section
only says what it cannot support.

**One corpus, one instrument, one annotation view.** Every chord number in §2, §7
and §8 is 180 GuitarSet **solo-guitar comping** takes scored against the
instructed lead sheet. Nothing here measures a mixed source, another instrument,
another genre, or a "performed voicings" reference (`--reference performed` exists
and has never been the headline figure). A generalisation claim about real songs
with drums, bass and vocals is **not** supported by any row in this file.

**One platform.** The accuracy runs were made on Linux (CPython 3.13.5, numpy
2.5.3, librosa 1.0.0); the Windows 10 sections (§9, §10) measure **cost**, and the
2026-11-01 frozen-build check compared chord JSON for one committed sample. So the
pipeline is known to behave identically across those two platforms *for that
sample*, which is a reproducibility result, not a cross-platform accuracy result.

**The pinned vector is a transcription.**
`benchmark/reference/chroma_baseline-instructed.json` holds the §8 adopted row,
and its own `notes` say the values were transcribed from §8 rather than re-derived
by a live run. The regression mechanism around it is tested — including its refusals
— but the 180-take comparison itself has only been exercised on synthetic corpora.
ROADMAP §11 keeps that task `[~]` for this reason and task A3 in §10 is the way to
close it.

**Confidence is not accuracy.** §6 measures calibration (Brier, ECE, risk–coverage
on held-out takes). A mean confidence printed by the window — the 0.58 the
maintainer saw on a real MP3 (ROADMAP §1, 2026-11-02) — says the engine is not sure;
it does not say how many chords are right. Only a run against verified annotations
says that.

**Never computed, therefore unknown:** the share of the lost CSR that is a wrong
root, a wrong quality, a boundary that moved, or a wrong no-chord decision (the
per-take columns needed for the split are already written — task A1); suspended,
diminished and augmented chords (unrepresentable in the phase-1 vocabulary, which
raises `InputError` on a request beyond it); chord behaviour at the seams of the
windowed long-song pass on real audio; and whether `N` is reported in silence as
often as it should be, which needs a corpus that annotates no-chord regions.

**No acceptance bar existed until today.** §1–§10 measured changes against the
previous measurement, which answers "is this better?" and never "is this good
enough?". ROADMAP §10 now proposes the numbers — and they are targets, recorded as
targets, with the harness as their verifier. No row of that table is satisfied by
anything in this file.
