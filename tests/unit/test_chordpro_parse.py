"""Reading a ChordPro sheet back into the untimed chart model (roadmap task L10).

``export/chordpro.py`` turns an analysis into the format musicians share; this
is the other direction, and it is what makes the round-trip claim of roadmap
section 9 testable instead of half true. ChordPro carries **no timestamps**, so
the honest reader returns the same typed model the plain-text reader returns -
``ChordChart`` - and what round-trips is the harmony and the words, not the
clock. What the sheet gives and a plain chart does not: a chord sits inside the
lyric line, immediately before the syllable it lands on, so the reader anchors
it exactly instead of judging a column.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.fake_analysis import DURATION, EVENTS, LYRICS, analysis_outcome
from song_chord_lyrics_analyzer.app.chart_import import import_chart_file
from song_chord_lyrics_analyzer.app.editing import TransposeChords, effective_chords
from song_chord_lyrics_analyzer.evaluation.chordpro import parse_chordpro
from song_chord_lyrics_analyzer.export.chordpro import render_chordpro

SHEET = """\
{title: A test song}
{by artist: An invented artist}

{soc: Intro}
[C]   [G]
{eoc}

{start_of_verse: Verse}
[C]hello [G]old [Am]friend
[F]we [C]meet again
{end_of_verse}
"""


def _exported_sheet() -> str:
    """The fake analysis, printed as the exporter prints it for a user."""
    return render_chordpro(analysis_outcome("song.wav").result)


class TestReadingAChordProSheet:
    def test_the_chords_come_out_in_the_order_the_sheet_writes_them(self) -> None:
        chart = parse_chordpro(SHEET)

        assert chart.chords == ("C", "G", "C", "G", "Am", "F", "C")
        assert not chart.is_empty

    def test_a_chord_lands_on_the_word_written_after_it(self) -> None:
        chart = parse_chordpro(SHEET)

        placed = [
            (token.text, chart.lyric_words[token.lyric_line][token.word_index].text)
            for token in chart.chord_tokens
            if token.lyric_line is not None and token.word_index is not None
        ]
        assert placed == [
            ("C", "hello"),
            ("G", "old"),
            ("Am", "friend"),
            ("F", "we"),
            ("C", "meet"),
        ]

    def test_the_sung_text_is_the_words_without_the_chords(self) -> None:
        chart = parse_chordpro(SHEET)

        assert chart.content_lyrics == ("hello old friend", "we meet again")
        assert [word.text for word in chart.lyric_words[0]] == ["hello", "old", "friend"]

    def test_a_directive_is_never_sung(self) -> None:
        chart = parse_chordpro(SHEET)

        assert chart.lyric_lines == ("hello old friend", "we meet again")

    def test_a_section_directive_tags_the_lines_written_under_it(self) -> None:
        chart = parse_chordpro(SHEET)

        assert chart.sections == ("Intro", "Verse")
        assert chart.line_sections == ("Verse", "Verse")

    def test_an_instrumental_line_keeps_its_chords_without_a_word(self) -> None:
        chart = parse_chordpro(SHEET)

        intro = chart.chord_tokens[:2]
        assert [token.text for token in intro] == ["C", "G"]
        assert all(token.lyric_line is None and token.word_index is None for token in intro)
        assert chart.chord_lines == (("C", "G"),)

    def test_a_trailing_chord_takes_the_last_word_of_its_line(self) -> None:
        chart = parse_chordpro("[C]hello world [G]\n")

        assert chart.chords == ("C", "G")
        assert [token.word_index for token in chart.chord_tokens] == [0, 1]

    def test_a_plain_section_header_line_is_read_as_a_section(self) -> None:
        chart = parse_chordpro("[Intro]\n[C]hello\n")

        assert chart.sections == ("Intro",)
        assert chart.line_sections == ("Intro",)
        assert chart.chords == ("C",)
        assert chart.content_lyrics == ("hello",)

    def test_a_bracket_that_is_not_a_chord_stays_lyric_text(self) -> None:
        chart = parse_chordpro("[ooh] [C]hello\n")

        assert chart.chords == ("C",)
        assert chart.content_lyrics == ("[ooh] hello",)

    def test_the_older_chord_directive_is_read_as_a_chord(self) -> None:
        chart = parse_chordpro("{chord: C}hello\n")

        assert chart.chords == ("C",)
        assert chart.content_lyrics == ("hello",)

    def test_a_tab_block_is_not_sung(self) -> None:
        chart = parse_chordpro("{st}\n0--1--2--3--\n{et}\n[C]hello\n")

        assert chart.content_lyrics == ("hello",)
        assert chart.chords == ("C",)

    def test_a_percent_comment_line_is_not_sung(self) -> None:
        chart = parse_chordpro("% a note to whoever reads this\n[C]hello\n")

        assert chart.lyric_lines == ("hello",)
        assert chart.chords == ("C",)

    def test_a_section_that_names_itself_only_by_kind_keeps_that_name(self) -> None:
        chart = parse_chordpro("{start_of_verse}\n[C]hello\n")

        assert chart.sections == ("Verse",)
        assert chart.line_sections == ("Verse",)

    def test_a_chord_before_the_first_word_belongs_to_that_word(self) -> None:
        chart = parse_chordpro("    [Am]   hello\n")

        assert chart.chord_tokens[0].word_index == 0
        assert chart.chord_tokens[0].column == 0

    def test_an_empty_sheet_is_refused(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            parse_chordpro("  \n\n")

    def test_a_sheet_of_only_words_is_empty_rather_than_rejected(self) -> None:
        chart = parse_chordpro("hello world\n")

        assert chart.is_empty
        assert chart.chords == ()

    def test_the_source_the_sheet_came_from_is_recorded(self) -> None:
        assert parse_chordpro(SHEET, source="song.pro").source == "song.pro"


class TestTheChordProRoundTrip:
    """What the exporter prints, the reader reads back - chords and words only.

    The fake analysis sings "hola mundo" under C and "adios amor" under an
    explicit no-chord, which the exporter renders as
    ``[C]hola [C]mundo`` / ``[N]adios [N]amor``. The sheet has no clock and the
    ``ChordChart`` model has no clock either, which is exactly why the pair
    round-trips: nothing is invented to make the shapes line up.
    """

    def test_the_chords_the_sheet_prints_are_the_chords_it_returns(self) -> None:
        chart = parse_chordpro(_exported_sheet())

        assert chart.chords == ("C", "C", "N", "N")
        assert chart.content_lyrics == ("hola mundo", "adios amor")

    def test_a_chord_is_still_anchored_to_the_word_it_was_printed_over(self) -> None:
        chart = parse_chordpro(_exported_sheet())

        placed = [
            (token.text, chart.lyric_words[token.lyric_line][token.word_index].text)
            for token in chart.chord_tokens
        ]
        assert placed == [("C", "hola"), ("C", "mundo"), ("N", "adios"), ("N", "amor")]

    def test_a_transposed_sheet_reads_back_transposed(self) -> None:
        text = render_chordpro(
            analysis_outcome("song.wav").result,
            chords=effective_chords(EVENTS, [TransposeChords(2)]),
        )

        assert parse_chordpro(text).chords == ("D", "D", "N", "N")

    def test_the_header_directives_round_trip_to_nothing_the_model_cannot_hold(self) -> None:
        chart = parse_chordpro(_exported_sheet())

        # The sheet names a title, a key and a tempo; an untimed chart has no
        # field for them, so the reader drops them instead of filing a key
        # under "lyric" to keep a count looking right.
        assert chart.lyric_lines == ("hola mundo", "adios amor")
        assert chart.sections == ()

    def test_an_exported_sheet_imports_back_over_the_songs_own_clock(self, tmp_path: Path) -> None:
        sheet = tmp_path / "song.pro"
        sheet.write_text(_exported_sheet(), encoding="utf-8")

        imported = import_chart_file(
            sheet, detected_chords=EVENTS, transcript=LYRICS, duration=DURATION
        )

        assert [event.label for event in imported.chords] == ["C", "C", "N", "N"]
        # The times come from the transcript's words, never from the sheet.
        assert [event.start for event in imported.chords] == [0.0, 0.5, 2.0, 2.5]
        assert [line.text for line in imported.lyrics or ()] == ["hola mundo", "adios amor"]
