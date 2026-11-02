#!/usr/bin/env python3
"""The entry point of the frozen application.

PyInstaller needs a script to start from, and ``songlab`` on a PATH is a
``console_scripts`` wrapper that a frozen build does not have. This file is that
substitute: one import, one ``SystemExit``, no logic -- everything the terminal
does is decided by :func:`song_chord_lyrics_analyzer.cli.main.main`, so the
executable and the installed command cannot drift apart.

It lives in ``packaging/`` and is never imported by the package or the tests.
"""

from __future__ import annotations

from song_chord_lyrics_analyzer.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
