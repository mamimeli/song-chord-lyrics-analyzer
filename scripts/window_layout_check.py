"""Look at the window the way a person does (roadmap section 12, task L7).

The offscreen suite proves what the window *does*. This records what it *looks
like*: it opens the real window on generated tone audio, drives it the way a
person would - open the song, load the words, move the playhead into a chorus -
and prints the measurements that a broken layout shows: whether the window fits
the screen at this scale factor, how wide each of the three panes ended up
against the floor its own widgets demand, and whether the song actually arrived
on them (chord bands, the chord-over-lyrics rows, the panel's summary).

It is a report, not a gate: it exits 0 and says what it saw. Windows scales its
display by a percentage, and `QT_SCALE_FACTOR` is how that is asked of Qt without
a person changing the control panel; with no `--scale-factor` the desktop's own
setting is what gets looked at. One factor per run, because the variable is read
before Qt starts:

```text
python scripts/window_layout_check.py --scale-factor 1.0
python scripts/window_layout_check.py --scale-factor 1.25
python scripts/window_layout_check.py --scale-factor 1.5
python scripts/window_layout_check.py --scale-factor 2.0
```

The platform plugin follows the environment too, and that changes what the
picture is worth: the offscreen plugin - what the test suite runs under, and
what this script defaults to so it never needs a display - has no fonts, so
every glyph in its PNG is an empty box, and its fake 800x800 screen makes a
960-wide window look like it does not fit anywhere. On Windows 10, setting
`QT_QPA_PLATFORM=windows` shows the real desktop, real text metrics and the
real available geometry, which is the picture a person is compared against.
Nothing is committed: the audio, the invented `.lrc`, the sidecar the window saves
and the PNGs all land in the gitignored cache. The words are invented, the audio
is generated, and the chords are whatever the engine finds in that tone - the
point is the layout, not a measurement of accuracy, and no accuracy claim belongs
in this file's output.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from analysis_cost_probe import make_fixture  # noqa: E402

#: Invented words on invented times: enough of a song to fill the lyric chart,
#: including one long line that is meant to overflow its pane (the design says it
#: scrolls instead of wrapping, and this is where that is judged).
LYRICS: tuple[tuple[float, str], ...] = (
    (0.5, "the first line tells nothing true"),
    (3.0, "it keeps the chord it was written on"),
    (6.0, "a longer line, invented on purpose so the pane has to decide whether to scroll"),
    (9.5, "and here the chorus returns again"),
    (12.0, "the last of the made-up words"),
)

#: Where the playhead is parked for the picture: inside the long line, so the
#: active word, its chord and the gap handling are all on screen at once.
PLAYHEAD_SECONDS = 7.0


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--scale-factor",
        type=float,
        default=None,
        help="ask Qt for this display scale (1.0, 1.25, 1.5, 2.0); the default is "
        "the setting the person's desktop already uses",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=14.0,
        help="length of the generated tone audio (default 14)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / ".cache" / "layout",
        help="where the generated song and the picture are written",
    )
    parser.add_argument(
        "--shot",
        action="store_true",
        help="write a PNG of the window into --out-dir",
    )
    return parser.parse_args(argv)


def _write_lyrics(path: Path) -> Path:
    """The invented lyric file, in the format the window imports."""
    path.write_text(
        "".join(
            f"[{int(seconds // 60):02d}:{seconds % 60:05.2f}]{text}\n" for seconds, text in LYRICS
        ),
        encoding="utf-8",
    )
    return path


def _panes(window: object) -> list[str]:
    """Each pane's width against the floor its own widgets demand."""
    from PyQt6.QtWidgets import QSplitter

    splitter = window.findChild(QSplitter)  # type: ignore[attr-defined]
    assert splitter is not None
    names = ("timeline", "lyrics", "panel")
    rows: list[str] = []
    for index in range(splitter.count()):
        widget = splitter.widget(index)
        width = widget.width()
        # A pane that paints instead of laying out (the timeline) reports no
        # minimum at all: -1 is Qt's way of saying that, not a width of -1.
        floor = widget.minimumSizeHint().width()
        if floor < 0:
            verdict = "paints - no layout floor"
        elif width <= floor:
            verdict = "at its floor - it cannot go narrower"
        else:
            verdict = f"room ({width - floor} spare)"
        rows.append(f"{names[index]:>8} pane: width {width:>4}  minimum {floor:>4}  {verdict}")
    return rows


def _settle(application: object, rounds: int = 3) -> None:
    """Let the window lay itself out, the way an event loop would.

    This script never enters ``QApplication.exec()``, so nothing is laid out
    unless it is asked for: a panel whose rows arrived with no event loop running
    keeps zero-size labels and shows up blank in the picture. That is a window no
    person has ever seen, so every measurement here is taken after the window has
    been allowed to settle.
    """
    for _ in range(rounds):
        application.processEvents()  # type: ignore[attr-defined]


def _lyrics_line_fit(window: object) -> str:
    """Whether the longest lyric row fits its pane, and what the pane does about it.

    The design says a long row scrolls instead of wrapping, so the numbers that
    decide whether the window obeys that are the text width, the viewport width
    and whether a horizontal range exists to scroll through.
    """
    from PyQt6.QtWidgets import QTextEdit

    editor = window.lyrics.findChild(QTextEdit)  # type: ignore[attr-defined]
    assert editor is not None
    text_width = editor.document().size().width()
    viewport_width = editor.viewport().width()
    scroll_bar = editor.horizontalScrollBar()
    return (
        f"lyric rows: text {text_width:>4.0f} wide in a {viewport_width:>4} viewport  "
        f"wrap {editor.lineWrapMode().name}  "
        f"{'scrolls sideways' if scroll_bar.maximum() > 0 else 'fits without scrolling'}"
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)
    # Before QApplication exists: the scale factor is read when the platform
    # plugin starts, and a window built after that is already in logical pixels.
    # With no --scale-factor the desktop's own setting is what gets looked at.
    if args.scale_factor is not None:
        os.environ["QT_SCALE_FACTOR"] = str(args.scale_factor)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    from PyQt6.QtWidgets import QApplication

    from song_chord_lyrics_analyzer.app import SongSession
    from song_chord_lyrics_analyzer.gui.analysis_worker import ImmediateAnalysis
    from song_chord_lyrics_analyzer.gui.main_window import MainWindow

    application = QApplication([])
    screen = application.primaryScreen()
    assert screen is not None

    audio = make_fixture(args.out_dir / f"song-{args.seconds:.0f}s.wav", seconds=args.seconds)
    words = _write_lyrics(args.out_dir / "words.lrc")

    session = SongSession()
    window = MainWindow(session=session, analysis=ImmediateAnalysis(session), input_hash=False)
    window.show()
    if not window.open_file(audio):
        print("the song did not open; nothing to look at")
        return 1
    if not window.load_lyrics_from(words):
        print("the lyric file did not load; the chart cannot be judged")
        return 1
    window.seek(PLAYHEAD_SECONDS)
    window.refresh()
    _settle(application)

    available = screen.availableGeometry()
    frame = window.frameGeometry()
    bands = window.timeline.bands
    rows = window.lyrics.rows

    requested = "the desktop's own setting" if args.scale_factor is None else args.scale_factor
    print(f"scale factor asked for: {requested}")
    print(f"device pixel ratio: {screen.devicePixelRatio()}")
    print(f"logical screen: {available.width()} x {available.height()}")
    print(f"window: {frame.width()} x {frame.height()} at {frame.x()},{frame.y()}")
    print(
        "window fits the screen: "
        f"{'yes' if available.contains(frame) else 'no - it overflows the available area'}"
    )
    for row in _panes(window):
        print(row)
    print(_lyrics_line_fit(window))
    print(f"waveform buckets: {'yes' if window.timeline.peaks else 'no'}")
    print(f"chord bands: {len(bands)}")
    print(f"chord-over-lyrics rows: {len(rows)}")
    print(f"active lyric row: {window.lyrics.active_index}")
    print(f"active word: {window.lyrics.active_word!r}")
    print(f"playhead chord: {window.chord_label.text()!r}")
    print(f"summary rows: {len(window.panel.rows)}")
    print(f"frame drawn: {'yes' if window.frame is not None else 'no'}")
    for name, value in window.panel.text_rows():
        print(f"panel: {name}: {value}")

    if args.shot:
        tag = "desktop" if args.scale_factor is None else f"{args.scale_factor:g}"
        shot = args.out_dir / f"window-{tag}.png"
        print(f"picture: {shot}" if window.grab().save(str(shot)) else "picture: not written")
    # Closing a window with unsaved work asks the person what to do, and an
    # offscreen run has no one to answer: the prompt would hang this script
    # forever. The lyric file is unsaved work by design, so save it - into the
    # gitignored cache, next to the generated song - and close quietly. This
    # also means the check walks the save path a real session ends with.
    print(f"sidecar saved: {'yes' if window.save_edits_sidecar() else 'no'}")
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
