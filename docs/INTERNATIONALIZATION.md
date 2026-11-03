# Internationalization

## Current policy: English first

The application is English-only until it is stable. This is a deliberate
ordering decision (roadmap sections 3, 77 and 79), not an oversight:

* Python identifiers, class names, function names — English
* CLI commands, options, help text and error messages — English
* Logging, configuration keys, reports and documentation — English
* GUI text — English, from the start
* Test names and descriptions — English

Spanish and any other language are added **after** the English application stops
changing.

## What exists today

* All user-facing strings are plain English literals in the CLI layer, in
  complete sentences — never concatenated fragments. They are cheap to extract
  later precisely because no string assembling happens anywhere.
* The window's text goes through Qt's own translation calls (dozens of sites in
  `gui/main_window.py`, including its dynamic status and tooltip strings), so
  rule 2 below has been satisfied in advance: the strings are *marked*
  translatable even though no catalogue exists to translate them.
* `src/song_chord_lyrics_analyzer/i18n/` is **no longer an empty placeholder** —
  it was when this section was first written. Since 2026-10-14 it owns
  `SOURCE_LANGUAGE` / `LANGUAGES`, `available_languages()` (which lists only the
  compiled `.qm` catalogues actually installed, and never invents a display
  name), and `install_translator()` (which raises when a catalogue is missing or
  unreadable instead of quietly staying English). The window builds its Language
  menu from these and holds the `QTranslator` it loads, because Qt drops a
  translation whose translator is collected.
* Nothing guesses a language from the environment. English is the default and —
  because `translations/` still ships only its own `README.md` and no `.qm` — the
  only language a user can actually get. No Spanish strings exist anywhere in the
  codebase.
* Since 2026-11-02 the chosen language is *remembered* between runs
  (`app/settings.py`, roadmap task L8): the window applies the stored code only
  when `available_languages()` actually lists it, so this bullet stays true — a
  remembered `de` on a machine with no German catalogue opens English and leaves
  the `de` on file. Nothing here reads a locale or an `LC_*` variable.

The open work is therefore **content, not wiring**: a real `.ts` → `.qm`
catalogue, and the `lrelease` step that builds it (ROADMAP §12 task L3).

## Phase 17 plan

```text
English source strings (stabilized)
        ↓
lupdate  →  translations/song_chord_lyrics_analyzer_es.ts
        ↓
Qt Linguist (translator)
        ↓
lrelease →  *_es.qm
        ↓
QTranslator loaded at runtime
```

Rules for that phase:

1. Do not start translating while the UI changes daily.
2. Never write `label.setText("Analyze")` without making it translatable.
3. Prefer whole translatable strings; never build sentences from translated
   fragments (word order and plurals differ per language).
4. Ship the English source catalogue as the reference for translators.
5. Keep CLI text translatable through the same mechanism where practical, so the
   CLI and GUI share terminology.

Planned catalogue names:

```text
translations/
├── song_chord_lyrics_analyzer_es.ts
├── song_chord_lyrics_analyzer_fr.ts
├── song_chord_lyrics_analyzer_de.ts
└── ...
```

Spanish is the first target; French, German, Portuguese and Italian follow only
if there is demand.

## Terminology freeze

Before translations begin, the English terminology is frozen: menus, dialogs,
settings, error messages, CLI help and documentation vocabulary. Any change
after the freeze invalidates existing catalogues, so the freeze happens as part
of the architecture freeze (roadmap phase 14).
