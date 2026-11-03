"""Importing a user's plain-text chart as the timed lyric/chord source.

The chart has the right words and chords but no timestamps; the detector and
the transcript have timestamps but the wrong text. These tests pin the two
alignments that combine them: chart chords take detected times and keep chart
labels, chart words take transcript times and keep chart text.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from song_chord_lyrics_analyzer.app.chart_import import import_chart, import_chart_file
from song_chord_lyrics_analyzer.models.lyrics import LyricSegment, LyricWord
from song_chord_lyrics_analyzer.models.music import ChordEvent, ChordQuality

CHART = """\
A test song
An invented artist

[Intro]
C G

[Verse]
C          G
hello old friend
Am         F
we meet again
"""


def _detected() -> list[ChordEvent]:
    labels = ["C", "G", "C", "G", "Am", "F"]
    return [
        ChordEvent(
            start=float(index * 2),
            end=float(index * 2 + 2),
            root=label.rstrip("m"),
            quality=ChordQuality.MINOR if label.endswith("m") else ChordQuality.MAJOR,
            label=label,
        )
        for index, label in enumerate(labels)
    ]


def _words(spec: list[tuple[str, float, float]]) -> list[LyricWord]:
    return [LyricWord(text=text, start=start, end=end) for text, start, end in spec]


def _transcript() -> list[LyricSegment]:
    return [
        LyricSegment(
            text="hello old friend",
            start=4.0,
            end=7.0,
            words=_words([("hello", 4.0, 5.0), ("old", 5.0, 6.0), ("friend", 6.0, 7.0)]),
        ),
        LyricSegment(
            text="we meet again",
            start=8.0,
            end=11.0,
            words=_words([("we", 8.0, 9.0), ("meet", 9.0, 10.0), ("again", 10.0, 11.0)]),
        ),
    ]


class TestChartImport:
    def test_chart_chords_keep_chart_labels_and_take_detected_times(self) -> None:
        imported = import_chart(CHART, detected_chords=_detected(), transcript=_transcript())

        assert [event.label for event in imported.chords] == ["C", "G", "C", "G", "Am", "F"]
        assert [(event.start, event.end) for event in imported.chords] == [
            (0.0, 2.0),
            (2.0, 4.0),
            (4.0, 6.0),
            (6.0, 8.0),
            (8.0, 10.0),
            (10.0, 12.0),
        ]
        assert all(event.source == "chart" for event in imported.chords)

    def test_chart_lyrics_replace_the_transcript_text_but_keep_its_timings(self) -> None:
        imported = import_chart(CHART, detected_chords=_detected(), transcript=_transcript())

        assert imported.lyrics is not None
        assert [line.text for line in imported.lyrics] == ["hello old friend", "we meet again"]
        first = imported.lyrics[0]
        assert first.start == 4.0
        assert first.end == 7.0
        assert [word.text for word in first.words] == ["hello", "old", "friend"]
        assert [(word.start, word.end) for word in first.words] == [
            (4.0, 5.0),
            (5.0, 6.0),
            (6.0, 7.0),
        ]
        assert all(word.source == "chart" for word in first.words)

    def test_title_and_artist_before_the_first_section_are_not_sung(self) -> None:
        imported = import_chart(CHART, detected_chords=_detected(), transcript=_transcript())

        assert imported.chart.content_lyrics == ("hello old friend", "we meet again")
        assert "test song" not in " ".join(line.text for line in imported.lyrics or ())

    def test_a_chart_chord_with_no_detection_still_has_a_word_anchor(self) -> None:
        # The final chart F has no detected event at all, but the chart puts it
        # over a timed word, so the chart-first timeline still places it.
        detected = _detected()[:-1]
        imported = import_chart(CHART, detected_chords=detected, transcript=_transcript())

        assert [event.label for event in imported.chords] == ["C", "G", "C", "G", "Am", "F"]
        assert not any("interpolated" in warning for warning in imported.warnings)
        assert all(
            event.start is not None and event.end is not None and event.end > event.start
            for event in imported.chords
        )

    def test_a_word_anchor_wins_over_a_later_detected_boundary(self) -> None:
        detected = _detected()
        detected[2] = ChordEvent(
            start=5.0,
            end=9.0,
            root="C",
            quality=ChordQuality.MAJOR,
            label="C",
        )
        imported = import_chart(CHART, detected_chords=detected, transcript=_transcript())

        assert imported.chords[2].start == 4.0

    def test_instrumental_chords_are_distributed_between_the_anchors(self) -> None:
        chart = "[Verse]\nC          G\nhello old friend\nD E\nAm\nwe meet again\n"
        imported = import_chart(chart, detected_chords=_detected(), transcript=_transcript())

        assert [event.label for event in imported.chords] == ["C", "G", "D", "E", "Am"]
        assert [round(event.start, 3) for event in imported.chords] == [
            4.0,
            6.0,
            6.667,
            7.333,
            8.0,
        ]

    def test_a_detector_substitution_does_not_change_the_chart_label(self) -> None:
        detected = _detected()
        detected[4] = ChordEvent(
            start=8.0,
            end=10.0,
            root="A",
            quality=ChordQuality.MAJOR,
            label="A",
        )
        imported = import_chart(CHART, detected_chords=detected, transcript=_transcript())

        assert imported.chords[4].label == "Am"
        assert imported.chords[4].start == 8.0

    def test_a_transcript_with_typos_still_anchors_the_matching_words(self) -> None:
        transcript = [
            LyricSegment(
                text="helo old frend",
                start=4.0,
                end=7.0,
                words=_words([("helo", 4.0, 5.0), ("old", 5.0, 6.0), ("frend", 6.0, 7.0)]),
            ),
            LyricSegment(
                text="we meet again",
                start=8.0,
                end=11.0,
                words=_words([("we", 8.0, 9.0), ("meet", 9.0, 10.0), ("again", 10.0, 11.0)]),
            ),
        ]
        imported = import_chart(CHART, detected_chords=_detected(), transcript=transcript)

        assert imported.lyrics is not None
        words = imported.lyrics[0].words
        assert [(word.text, word.start) for word in words] == [
            ("hello", 4.0),
            ("old", 5.0),
            ("friend", 6.0),
        ]

    def test_long_misspelled_words_still_anchor(self) -> None:
        transcript = [
            LyricSegment(
                text="satisfascer",
                start=2.0,
                end=3.0,
                words=_words([("satisfascer", 2.0, 3.0)]),
            )
        ]
        chart = "[Intro]\nC\nsatisfacer\n"
        imported = import_chart(chart, detected_chords=_detected(), transcript=transcript)

        assert imported.lyrics is not None
        assert imported.lyrics[0].words[0].start == 2.0

    def test_no_timed_transcript_keeps_the_chart_chords_and_returns_no_lyrics(self) -> None:
        imported = import_chart(CHART, detected_chords=_detected(), transcript=[])

        assert imported.chords
        assert imported.lyrics is None
        assert any("no timed transcript" in warning for warning in imported.warnings)

    def test_a_chart_with_lyrics_can_be_timed_without_detected_chords(self) -> None:
        imported = import_chart(CHART, detected_chords=[], transcript=_transcript())

        assert [event.label for event in imported.chords] == ["C", "G", "C", "G", "Am", "F"]
        assert imported.warnings == ()

    def test_no_detected_chords_and_no_lyrics_means_no_timed_chords(self) -> None:
        imported = import_chart("[Intro]\nC G\n", detected_chords=[], transcript=[])

        assert imported.chords == ()
        assert any("no detected chords" in warning for warning in imported.warnings)

    def test_a_chord_only_chart_keeps_the_transcript(self) -> None:
        imported = import_chart(
            "[Intro]\nC G\n", detected_chords=_detected(), transcript=_transcript()
        )

        assert imported.chords
        assert imported.lyrics is None
        assert any("no lyric lines" in warning for warning in imported.warnings)

    def test_an_empty_chart_is_refused(self) -> None:
        with pytest.raises(ValueError, match="no chord line"):
            import_chart("[Intro]\n", detected_chords=_detected(), transcript=_transcript())


CHART_WITH_REPEAT = """\
[Verse]
C          G
hello old friend
Am         F
we meet again

[Chorus]
G          C
you are the song
F          C
the song we keep
"""


def _line(text: str, start: float, per: float = 1.0) -> LyricSegment:
    """One transcript line, its words one second apart from ``start``."""
    tokens = text.split()
    return LyricSegment(
        text=text,
        start=start,
        end=start + per * len(tokens),
        words=[
            LyricWord(token, start + index * per, start + (index + 1) * per)
            for index, token in enumerate(tokens)
        ],
    )


def _transcript_sung_twice() -> list[LyricSegment]:
    """The song sings the chorus twice; the chart above writes it once."""
    return [
        _line("hello old friend", 4.0),
        _line("we meet again", 8.0),
        _line("you are the song", 12.0),
        _line("the song we keep", 16.0),
        _line("you are the song", 24.0),
        _line("the song we keep", 28.0),
    ]


class TestASectionTheSongSingsAgain:
    """Section-aware timing: a chart writes a chorus once, the song sings it twice.

    The chart is the person's statement of the *words and chords*, the transcript
    is the statement of *when*. When the two disagree about how many times a
    section is sung, neither may be silently overwritten: the section is anchored
    at its first singing (where a chart in performance order says it belongs),
    the repeat gets the chart's words at the transcript's own times, and a warning
    says the chart does not cover the repeat's chords.
    """

    def _import(self) -> object:
        return import_chart(
            CHART_WITH_REPEAT,
            detected_chords=_detected(),
            transcript=_transcript_sung_twice(),
            duration=32.0,
        )

    def test_a_chorus_written_once_is_timed_at_its_first_singing(self) -> None:
        imported = self._import()
        assert imported.lyrics is not None

        chorus = [line for line in imported.lyrics if line.text == "you are the song"]
        assert float(chorus[0].start) == 12.0

        # The verse's last chord yields to the chorus at that first singing,
        # instead of holding across the whole chorus because the anchor was
        # picked up twelve seconds later.
        verse_f = next(event for event in imported.chords if event.label == "F")
        assert float(verse_f.end) == 12.0

    def test_the_singing_the_chart_does_not_write_gets_the_chart_words(self) -> None:
        imported = self._import()
        assert imported.lyrics is not None

        assert [(str(line.start), line.text) for line in imported.lyrics] == [
            ("4.0", "hello old friend"),
            ("8.0", "we meet again"),
            ("12.0", "you are the song"),
            ("16.0", "the song we keep"),
            ("24.0", "you are the song"),
            ("28.0", "the song we keep"),
        ]
        repeat = imported.lyrics[-2]
        assert [word.text for word in repeat.words] == ["you", "are", "the", "song"]
        assert [float(word.start) for word in repeat.words] == [24.0, 25.0, 26.0, 27.0]
        assert all(word.source == "chart" for word in repeat.words)

    def test_the_repeat_is_reported_because_its_chords_are_not_in_the_chart(
        self,
    ) -> None:
        imported = self._import()

        assert any("Chorus" in warning and "again" in warning for warning in imported.warnings)

    def test_a_chart_that_writes_both_singings_is_not_duplicated(self) -> None:
        """The chart's own repeat is respected: six lines, not seven.

        Here the person wrote the chorus twice, so the two singings in the
        transcript are already covered and nothing may be added a third time.
        """
        chart = (
            CHART_WITH_REPEAT
            + "\n[Chorus]\nG          C\nyou are the song\nF          C\nthe song we keep\n"
        )
        imported = import_chart(
            chart,
            detected_chords=_detected(),
            transcript=_transcript_sung_twice(),
            duration=32.0,
        )
        assert imported.lyrics is not None

        chorus = [str(line.start) for line in imported.lyrics if line.text == "you are the song"]
        assert chorus == ["12.0", "24.0"]
        assert not any("again" in warning for warning in imported.warnings)

    def test_a_single_word_section_is_not_read_as_a_repeat(self) -> None:
        """One word is not evidence: it matches everywhere or nowhere.

        The chorus below is one word, and the transcript sings that word three
        times. Guessing which of them is "the repeat" would invent a timeline, so
        the chart stays as written and no extra line appears.
        """
        chart = "[Verse]\nC G\nhello old friend\n[Chorus]\nAm F\nfire\n"
        transcript = [
            _line("hello old friend", 4.0),
            _line("fire", 12.0),
            _line("fire", 20.0),
            _line("fire", 26.0),
        ]

        imported = import_chart(
            chart, detected_chords=_detected(), transcript=transcript, duration=30.0
        )
        assert imported.lyrics is not None

        assert [line.text for line in imported.lyrics].count("fire") == 1

    def test_a_song_that_sings_a_section_once_changes_nothing(self) -> None:
        transcript = [
            _line("hello old friend", 4.0),
            _line("we meet again", 8.0),
            _line("you are the song", 12.0),
            _line("the song we keep", 16.0),
        ]

        imported = import_chart(
            CHART_WITH_REPEAT,
            detected_chords=_detected(),
            transcript=transcript,
            duration=20.0,
        )

        assert imported.warnings == ()


class TestReadingTheChartFile:
    """The import that opens a file knows which file it opened (L9).

    A window that reads the text itself cannot say where the layer came from, and
    hashing belongs to the code that read the bytes - so ``import_chart_file`` does
    both: it reads, digests what it read and parses it. ``import_chart`` stays the
    text-level entry and honestly reports no provenance.
    """

    def test_the_file_is_named_and_digested(self, tmp_path: Path) -> None:
        chart = tmp_path / "song.txt"
        chart.write_text(CHART, encoding="utf-8")

        imported = import_chart_file(
            chart, detected_chords=_detected(), transcript=_transcript(), duration=20.0
        )

        assert imported.provenance is not None
        assert Path(imported.provenance.path).name == "song.txt"
        assert Path(imported.provenance.path).is_absolute()
        assert imported.provenance.digest == hashlib.sha256(chart.read_bytes()).hexdigest()

    def test_the_layers_are_the_same_as_the_text_import(self, tmp_path: Path) -> None:
        chart = tmp_path / "song.txt"
        chart.write_text(CHART, encoding="utf-8")

        from_file = import_chart_file(
            chart, detected_chords=_detected(), transcript=_transcript(), duration=20.0
        )
        from_text = import_chart(
            CHART, detected_chords=_detected(), transcript=_transcript(), duration=20.0
        )

        assert [(event.start, event.label) for event in from_file.chords] == [
            (event.start, event.label) for event in from_text.chords
        ]
        assert from_text.provenance is None

    def test_the_chart_keeps_its_own_name_for_the_report(self, tmp_path: Path) -> None:
        chart = tmp_path / "song.txt"
        chart.write_text(CHART, encoding="utf-8")

        imported = import_chart_file(chart, detected_chords=_detected(), transcript=_transcript())

        assert imported.chart.source == "song.txt"

    def test_a_chart_that_cannot_be_read_raises_for_the_caller_to_report(
        self, tmp_path: Path
    ) -> None:
        """No file is the person's mistake to see, not the importer's to hide."""
        with pytest.raises(OSError):
            import_chart_file(
                tmp_path / "nope.txt", detected_chords=_detected(), transcript=_transcript()
            )

    def test_a_chart_that_cannot_be_decoded_keeps_its_text_an_error(self, tmp_path: Path) -> None:
        chart = tmp_path / "song.txt"
        chart.write_bytes(b"\xff\xfe not utf-8 at all")

        with pytest.raises(ValueError):
            import_chart_file(chart, detected_chords=_detected(), transcript=_transcript())
