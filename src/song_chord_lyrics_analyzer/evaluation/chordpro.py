"""Read a ChordPro sheet back into the untimed chart model (roadmap Phase L, task L10).

:mod:`export.chordpro` writes the format musicians share; this module reads it,
and it is what turns the round-trip promise of roadmap section 9 from a half
claim into a test. Two facts shape the design:

* **A ChordPro sheet has no timestamps.** Neither has a plain-text chart, so the
  reader returns the very same :class:`~evaluation.chart.ChordChart`, and the
  existing import supplies the clock from the song. Nothing here invents a time.
* **A chord is printed inside the lyric line**, immediately before the syllable
  it lands on - ``[G]Let it [C]be``. That is stronger evidence than a plain
  chart's indentation, so the chords come back anchored to the exact word.

The grammar covered is the one the exporter emits plus what a person writing (or
downloading) a sheet actually uses: ``[Chord]`` brackets, ``{directive: value}``
headers, ``{start_of_chorus: Chorus}``-style sections in their short and long
spellings, the older ``{chord: G}`` spelling of a chord, ``{start_of_tab}`` and
``{start_of_grid}`` blocks, which are played rather than sung and therefore
contribute no lyric, a whole line starting with ``%``, which is ChordPro's
comment character, and a ``[Intro]`` written as a whole line by itself, which
names a section the same way a plain chart does. A section that gives no name
takes its kind (``{start_of_verse}`` is "Verse"), so a sheet whose verses must be
told apart is best written as ``{start_of_verse: Verse 1}``.

The reader is deliberately conservative, like the plain chart's. It never turns
lyric text into a chord, and a directive it does not know - a title, a key, a
tempo, a credit - is dropped rather than stored somewhere it does not belong:
an untimed chart has no field for a key, and filing ``{key: C major}`` under
"lyric" to make a count look right would be the kind of invention this project
documents against.
"""

from __future__ import annotations

import re
from bisect import bisect_left
from dataclasses import dataclass, field

from song_chord_lyrics_analyzer.evaluation.chart import (
    ChartChord,
    ChartWord,
    ChordChart,
    is_chord_token,
)

__all__ = ["parse_chordpro"]

#: A chord bracket or a directive, in the order they appear on a line.
_SPAN = re.compile(r"\[([^\]]*)\]|\{([^}]*)\}")

#: Section openers, with the name they carry when the sheet gives none. ChordPro
#: spells each one two ways.
_SECTION_OPEN = {
    "soc": "Chorus",
    "start_of_chorus": "Chorus",
    "sob": "Bridge",
    "start_of_bridge": "Bridge",
    "sov": "Verse",
    "start_of_verse": "Verse",
    "sos": "Section",
    "start_of_section": "Section",
}

#: Section closers: after one, a line belongs to no section until the next
#: header, which is what keeps a written-once chorus from claiming the verse.
_SECTION_CLOSE = frozenset(
    {"eoc", "end_of_chorus", "eob", "end_of_bridge", "eov", "end_of_verse", "eos", "end_of_section"}
)

#: Blocks that are played, not sung (tablature, rhythm grids). Their text is
#: fret numbers and dashes, never a word the window should put above a chord.
_UNSUNG_OPEN = frozenset({"st", "start_of_tab", "grid", "start_of_grid"})
_UNSUNG_CLOSE = frozenset({"et", "end_of_tab", "end_of_grid"})

#: The older spelling of a chord, before brackets existed.
_CHORD_DIRECTIVES = frozenset({"chord", "chordline"})


@dataclass
class _SheetLine:
    """One sheet line as the reader sees it.

    Attributes:
        text: The sung text, with chords and directives removed and the
            indentation stripped.
        chords: Each bracketed chord with its character offset inside ``text``,
            which is where it takes effect.
        section: The section this line opens, when a directive (or a whole-line
            ``[Intro]``) names one.
        section_closed: A directive on this line ended the current section.
        unsung_opened: A tab/grid block starts here.
        unsung_closed: A tab/grid block ends here.
    """

    text: str = ""
    chords: list[tuple[str, int]] = field(default_factory=list)
    section: str | None = None
    section_closed: bool = False
    unsung_opened: bool = False
    unsung_closed: bool = False


def _spanned_words(text: str) -> tuple[ChartWord, ...]:
    """Words with their zero-based columns, in the sheet's own coordinate system."""
    return tuple(ChartWord(match.group(), match.start()) for match in re.finditer(r"\S+", text))


def _directive(body: str) -> tuple[str, str]:
    """The lowercase name and the argument of one ``{name: argument}`` directive."""
    name, _, argument = body.partition(":")
    return name.strip().lower().replace("-", "_"), argument.strip()


def _scan_line(raw: str) -> _SheetLine:
    """Split one sheet line into its sung text, its chords and its structure.

    Chord offsets count the text as it is being built, so a chord keeps the
    position where the syllable after it will start; the leading indentation is
    then subtracted, because it is not part of the sung line.
    """
    result = _SheetLine()
    pieces: list[str] = []
    cursor = 0
    whole_line = raw.strip()
    for match in _SPAN.finditer(raw):
        pieces.append(raw[cursor : match.start()])
        cursor = match.end()
        built = len("".join(pieces))
        bracketed, braced = match.group(1), match.group(2)
        if bracketed is not None:
            if is_chord_token(bracketed):
                result.chords.append((bracketed, built))
            elif whole_line == match.group():
                result.section = bracketed.strip()
            else:
                pieces.append(match.group())
            continue
        name, argument = _directive(braced or "")
        if name in _SECTION_OPEN:
            result.section = argument or _SECTION_OPEN[name]
        elif name in _SECTION_CLOSE:
            result.section_closed = True
        elif name in _UNSUNG_OPEN:
            result.unsung_opened = True
        elif name in _UNSUNG_CLOSE:
            result.unsung_closed = True
        elif name in _CHORD_DIRECTIVES and is_chord_token(argument):
            result.chords.append((argument, built))
    pieces.append(raw[cursor:])
    text = "".join(pieces)
    stripped = text.strip()
    leading = len(text) - len(text.lstrip())
    result.text = stripped
    result.chords = [
        (label, min(max(position - leading, 0), len(stripped))) for label, position in result.chords
    ]
    return result


def parse_chordpro(text: str, *, source: str | None = None) -> ChordChart:
    """Read a ChordPro sheet into the same typed chart a plain-text chart gets.

    Args:
        text: The sheet's contents.
        source: Optional file name recorded in the result.

    Returns:
        The parsed chart: chords in sheet order, each anchored to the word
        written after it (the last word of its line when it trails one), the
        sung lines with their words, and the section each line was written
        under. A sheet with chords but no sung text - an instrumental chart - is
        returned as is; a sheet with no chord at all arrives with
        :attr:`ChordChart.is_empty` true, for the caller to report with the file
        name it knows.

    Raises:
        ValueError: When ``text`` is empty. An empty file is a wrong argument,
            not a song of silence.
    """
    if not text.strip():
        raise ValueError("the chord sheet is empty")
    chords: list[str] = []
    chord_lines: list[tuple[str, ...]] = []
    chord_tokens: list[ChartChord] = []
    sections: list[str] = []
    lyric_lines: list[str] = []
    content_lyrics: list[str] = []
    lyric_words: list[tuple[ChartWord, ...]] = []
    line_sections: list[str | None] = []
    current_section: str | None = None
    content_started = False
    in_unsung_block = False

    for raw in text.splitlines():
        if raw.lstrip().startswith("%"):
            # ChordPro's own comment character: a note to the reader, never a
            # word to sing and never a chord to place.
            continue
        sheet = _scan_line(raw)
        if sheet.unsung_opened:
            in_unsung_block = True
        if in_unsung_block:
            if sheet.unsung_closed:
                in_unsung_block = False
            continue
        if sheet.section:
            current_section = sheet.section
            sections.append(current_section)
        if sheet.section_closed:
            current_section = None
        if not sheet.text and not sheet.chords:
            continue
        if sheet.chords or sheet.section:
            content_started = True
        words = _spanned_words(sheet.text)
        starts = [word.column for word in words]
        content_index: int | None = None
        if words:
            lyric_lines.append(sheet.text)
            if content_started:
                content_index = len(content_lyrics)
                content_lyrics.append(sheet.text)
                lyric_words.append(words)
                line_sections.append(current_section)
        elif sheet.chords:
            chord_lines.append(tuple(label for label, _ in sheet.chords))
        for label, column in sheet.chords:
            word_index = None
            if content_index is not None and starts:
                # ChordPro places the chord itself, so two of them over one
                # syllable is what the sheet wrote - unlike a plain chart's
                # approximate columns, nothing here has to be forced apart.
                word_index = min(bisect_left(starts, column), len(words) - 1)
            chords.append(label)
            chord_tokens.append(
                ChartChord(
                    text=label,
                    column=column,
                    lyric_line=content_index,
                    word_index=word_index,
                )
            )
    return ChordChart(
        chords=tuple(chords),
        chord_lines=tuple(chord_lines),
        sections=tuple(sections),
        lyric_lines=tuple(lyric_lines),
        content_lyrics=tuple(content_lyrics),
        chord_tokens=tuple(chord_tokens),
        lyric_words=tuple(lyric_words),
        line_sections=tuple(line_sections),
        source=source,
    )
