# Troubleshooting

Start with the environment report; it answers most questions immediately:

```bash
songlab doctor
```

## Exit codes

| Code | Meaning | Typical cause |
| --- | --- | --- |
| `0` | success | — |
| `1` | unexpected internal error | a bug; re-run with `--debug` for the traceback |
| `2` | invalid input | wrong path, a directory instead of a file, unknown command, corrupt audio |
| `3` | missing dependency | FFmpeg/ffprobe not found for a non-WAV file |
| `130` | interrupted | `Ctrl+C`, or the window's Cancel |

`130` is not an error and not a partial result. An interrupted run writes
nothing: the document is assembled only once every layer finished, and the files
the application does overwrite - the `.songlab.json` sidecar and an export - are
staged beside the target and renamed, so an interrupt inside a write leaves the
previous version readable. The stop takes effect between units of engine work,
so on a long recording the analysis that can be stopped is the windowed one
(`--chord-chunk-seconds`; see [USAGE.md](USAGE.md)).

Run any command with `--debug` to get full logging plus a traceback. Use
`--verbose` for debug logging without tracebacks and `--quiet` for warnings and
errors only.

## "FFprobe was not found" / exit code 3

Only WAV metadata can be read without FFmpeg. To inspect MP3, FLAC, M4A, OGG and
friends, install FFmpeg:

```bash
# Debian / Ubuntu
sudo apt install ffmpeg
# Fedora
sudo dnf install ffmpeg
# Arch
sudo pacman -S ffmpeg
# macOS
brew install ffmpeg
# Windows
winget install --id Gyan.FFmpeg
choco install ffmpeg
scoop install ffmpeg
```

If the binaries are installed somewhere unusual, point the program at them
directly:

```bash
# Linux / macOS
export SONGLAB_FFMPEG=/opt/ffmpeg/bin/ffmpeg
export SONGLAB_FFPROBE=/opt/ffmpeg/bin/ffprobe
```

```powershell
# Windows PowerShell
$env:SONGLAB_FFMPEG = "C:\ffmpeg\bin\ffmpeg.exe"
$env:SONGLAB_FFPROBE = "C:\ffmpeg\bin\ffprobe.exe"
```

On Windows the search does not stop at `PATH`: it also looks in
`%LOCALAPPDATA%\Microsoft\WinGet\Links`, `%LOCALAPPDATA%\Programs`,
`%PROGRAMFILES%\ffmpeg\bin`, `%PROGRAMDATA%\chocolatey\bin` and `~\scoop\shims`,
so a winget, Chocolatey or Scoop install is found even in a terminal whose
`PATH` is stale. On 2026-10-31 `songlab doctor` on Windows 10 reported the
winget build (FFmpeg 9.0.2) for both tools. The full Windows install walkthrough
is the README section "On Windows 10 / 11".

## "… is not installed" / an engine reports `unavailable here`

Exit code 3 is not only FFmpeg. The chord, key and tempo engines need the `dsp`
extra, playback needs `playback`, the window needs `gui`, and lyrics need
`lyrics`. `songlab doctor` says which extra is absent in this environment, which
import was not found, and the exact command that fixes it; the same table in the
"Analysis engines" section marks an engine `ok` or `unavailable here`.

```bash
songlab doctor                        # or --json for the same table as data
pip install "song-chord-lyrics-analyzer[dsp]"
```

Check the environment you are actually running in: a venv that installed the
extras is not the interpreter `songlab` resolves to. `songlab doctor` prints
`Interpreter:` first, and `pip install` must go to that one —
`<that interpreter> -m pip install …` is the unambiguous form.

## "Unsupported or unreadable audio file"

The container was found but could not be decoded as audio. Common causes:

* the file is a video container without an audio stream;
* the download is truncated (check `songlab info --hash` against the expected
  digest);
* the extension is misleading — probing decides the truth, not the extension.

A mistyped time option can look like this too, because `argparse` accepts `nan`
and `inf` as numbers: since 2026-10-31 `--start`, `--end`, `--min-duration`,
`--at`, `--interval`, `--chunk-seconds` and `--overlap-seconds` are refused on
their own, before any file is opened, so this message now really means the file.
If a songlab version older than that says it about a file `songlab info` can
read, check the time options first.

## "Audio file is empty"

The path exists but the file has zero bytes; re-copy or re-download it.

## Wrong or missing tags

Tags are informational and are deliberately kept separate from technical
metadata. `songlab info` reports codec, sample rate, channels, bit depth,
bitrate, duration and size from the decoder, and shows container tags afterwards
under "Tags (informational, never trusted)". A wrong ID3 title is never used for
analysis.

## Mojibake, or a redirected file that is not valid UTF-8

songlab writes its own text as UTF-8 on every platform since 2026-10-31, so
`songlab analyze song.mp3 --json > doc.json` in `cmd` or Git Bash gives a UTF-8
file. What can still look wrong is the *terminal*, not the bytes: a legacy
Windows console in code page 850 or 1252 renders UTF-8 accents as garbage until
you run `chcp 65001` (or use Windows Terminal / PowerShell 7). PowerShell 5.1 is
the exception that is not songlab's fault — its `>` operator re-encodes what it
redirects as UTF-16LE, so prefer `songlab export --format json -o out.json`, which
writes the file itself as UTF-8. If you are on an older build and a command
answers *"Unexpected error: UnicodeEncodeError"*, the audio or its name contains
a character the console code page has no byte for: update, redirect with `-o`, or
set the console to UTF-8.

## Analysis takes too long or runs out of memory

Feature-specific guidance arrives with the engines (phases 3-8). Current
mitigations: use `songlab info` for metadata-only work, and remember that models
are cached under `SONGLAB_CACHE_DIR` (`songlab doctor` prints the path) so a
second run does not re-download anything.

## Where are caches and downloads stored?

```bash
songlab doctor    # prints cache, data, models, exports and temp directories
```

Override them with `SONGLAB_CACHE_DIR`, `SONGLAB_DATA_DIR` and
`SONGLAB_TEMP_DIR`. No path is ever hard-coded per operating system.

## I cannot find `.cache/chords/guitarset/`

That directory is not a runtime cache and `songlab doctor` will not print it. It
is the local dataset copy used by the measurement work, and it lives **inside the
repository, relative to its root** — not under your home directory. It also starts
with a dot, so file managers hide it: press `Ctrl+H` (Thunar, Dolphin, Nautilus)
or `Cmd+Shift+.` (Finder), or use `Ctrl+L` and paste the absolute path. The full
layout, file counts and take-name scheme are documented in the README section
"The GuitarSet copy on disk" ([`README.md`](../README.md)).

## Reporting a problem

Include the output of `songlab doctor`, the exact command, the exit code and the
`--debug` output. Attach audio only if its licence allows redistribution.
