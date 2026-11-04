"""Preferences the window remembers between runs (roadmap L8).

The store is a plain JSON file in songlab's own data directory, and it is the
only place a preference lives: a widget must not hold one, because a widget
cannot be read back after the process ends. What this module promises is the
part that matters for a *preference* - as opposed to a document:

* a file that cannot be read costs the preference and nothing else. A corrupt,
  empty, foreign or half-written settings file falls back to the defaults;
  losing the last folder must never stop the window from opening;
* a value the code does not know is refused at the boundary, so nothing down
  the line has to revalidate a string that came off disk - an unknown language
  is English, a folder that is not a folder is no folder;
* the toolkit's window state is **an opaque token** here (roadmap L7): this module
  does not know what a geometry blob contains, only whether it decodes as the
  base64 the window wrote, and a token that does not - or pane sizes that are not
  a list of positive whole numbers - is no state at all;
* the write is atomic, because the file a person edited by hand is theirs.

Qt-free, engine-free: plain files in a ``tmp_path``.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

import pytest

from song_chord_lyrics_analyzer.app.settings import (
    SETTINGS_FILENAME,
    Preferences,
    PreferenceStore,
    default_preferences_path,
    load_preferences,
    save_preferences,
)
from song_chord_lyrics_analyzer.i18n import LANGUAGES, SOURCE_LANGUAGE

#: What the window writes for a geometry blob: base64 of bytes it does not explain.
STATE = base64.b64encode(b"\x01\x00songlab-geometry").decode("ascii")


class TestTheDefaults:
    def test_a_preference_file_that_does_not_exist_is_just_the_defaults(
        self, tmp_path: Path
    ) -> None:
        preferences = load_preferences(tmp_path / SETTINGS_FILENAME)

        assert preferences.language == SOURCE_LANGUAGE
        assert preferences.last_folder is None
        assert preferences.window_geometry is None
        assert preferences.splitter_sizes == ()

    def test_the_defaults_are_the_source_language_and_no_folder(self) -> None:
        preferences = Preferences()

        assert preferences.language == "en"
        assert preferences.last_folder is None
        assert preferences.window_geometry is None
        assert preferences.splitter_sizes == ()

    def test_the_file_lives_in_the_data_directory_songlab_reports(self) -> None:
        from song_chord_lyrics_analyzer.utils.paths import default_data_dir

        assert default_preferences_path() == default_data_dir() / SETTINGS_FILENAME


class TestReadingAFile:
    def test_a_good_file_is_read_back_field_for_field(self, tmp_path: Path) -> None:
        path = tmp_path / SETTINGS_FILENAME
        path.write_text(json.dumps({"language": "es", "last_folder": str(tmp_path)}))

        preferences = load_preferences(path)

        assert preferences.language == "es"
        assert preferences.last_folder == tmp_path

    def test_a_key_that_is_not_there_leaves_that_preference_at_its_default(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / SETTINGS_FILENAME
        path.write_text(json.dumps({"language": "fr"}))

        preferences = load_preferences(path)

        assert preferences.language == "fr"
        assert preferences.last_folder is None

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "   ",
            "not json at all",
            "[1, 2, 3]",
            '{"language": 42}',
            '{"last_folder": 3.5}',
            '{"language": null, "last_folder": null}',
            '{"window_geometry": "not base64 at all !!"}',
            '{"window_geometry": 42}',
            '{"splitter_sizes": [420, -1]}',
            '{"splitter_sizes": "wide"}',
        ],
    )
    def test_a_file_the_code_cannot_trust_costs_the_preference_and_nothing_else(
        self, tmp_path: Path, text: str
    ) -> None:
        path = tmp_path / SETTINGS_FILENAME
        path.write_text(text)

        preferences = load_preferences(path)

        assert preferences == Preferences()

    def test_a_language_the_application_does_not_know_is_english(self, tmp_path: Path) -> None:
        """``xx`` is not in :data:`i18n.LANGUAGES`, so nothing offers it back."""
        path = tmp_path / SETTINGS_FILENAME
        path.write_text(json.dumps({"language": "xx"}))

        assert load_preferences(path).language == SOURCE_LANGUAGE

    def test_every_planned_language_survives_the_round_trip(self, tmp_path: Path) -> None:
        """A remembered language is kept even before its catalogue ships."""
        for code in LANGUAGES:
            path = tmp_path / SETTINGS_FILENAME
            path.write_text(json.dumps({"language": code}))

            assert load_preferences(path).language == code

    def test_a_folder_that_is_not_a_directory_is_no_folder_at_all(self, tmp_path: Path) -> None:
        a_file = tmp_path / "song.wav"
        a_file.write_text("x")
        path = tmp_path / SETTINGS_FILENAME
        path.write_text(json.dumps({"last_folder": str(tmp_path / "gone")}))

        assert load_preferences(path).last_folder is None

        path.write_text(json.dumps({"last_folder": str(a_file)}))

        assert load_preferences(path).last_folder is None

    def test_a_home_relative_folder_written_by_hand_is_understood(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        (tmp_path / "Music").mkdir()
        path = tmp_path / SETTINGS_FILENAME
        path.write_text(json.dumps({"last_folder": "~/Music"}))

        assert load_preferences(path).last_folder == tmp_path / "Music"


class TestWritingAFile:
    def test_saving_creates_the_directory_it_needs(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / SETTINGS_FILENAME

        save_preferences(Preferences(language="de"), path)

        assert json.loads(path.read_text())["language"] == "de"

    def test_a_saved_preference_reads_back_as_the_same_thing(self, tmp_path: Path) -> None:
        path = tmp_path / SETTINGS_FILENAME
        preferences = Preferences(language="pt", last_folder=tmp_path)

        save_preferences(preferences, path)

        assert load_preferences(path) == preferences

    def test_the_file_holds_only_the_keys_the_code_knows(self, tmp_path: Path) -> None:
        path = tmp_path / SETTINGS_FILENAME
        path.write_text(json.dumps({"language": "es", "theme": "dark"}))

        save_preferences(load_preferences(path), path)

        assert set(json.loads(path.read_text())) == {
            "language",
            "last_folder",
            "window_geometry",
            "splitter_sizes",
        }

    def test_a_file_left_half_written_by_an_older_build_is_not_a_preference(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / SETTINGS_FILENAME
        path.write_text('{"language": "es", "last_folder": "/musi')

        assert load_preferences(path) == Preferences()


class TestRememberingTheWindow:
    """The third committed setting: the state of the window itself (roadmap L7).

    The geometry is whatever the toolkit wrote, held as base64 because a JSON file
    has no bytes; this module's only question about it is whether it decodes. The
    pane sizes are the one part a person could reasonably edit by hand, so they are
    checked as numbers.
    """

    def test_a_window_state_writes_and_reads_back_as_the_same_token(self, tmp_path: Path) -> None:
        path = tmp_path / SETTINGS_FILENAME
        preferences = Preferences(window_geometry=STATE, splitter_sizes=(420, 420, 200))

        save_preferences(preferences, path)

        assert load_preferences(path) == preferences

    def test_a_pre_l7_file_costs_the_window_state_and_nothing_else(self, tmp_path: Path) -> None:
        """The file an older build wrote is a valid file with two keys missing."""
        path = tmp_path / SETTINGS_FILENAME
        path.write_text(json.dumps({"language": "es", "last_folder": str(tmp_path)}))

        preferences = load_preferences(path)

        assert preferences.language == "es"
        assert preferences.window_geometry is None
        assert preferences.splitter_sizes == ()

    def test_a_geometry_that_is_not_the_base64_the_window_writes_is_no_geometry(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / SETTINGS_FILENAME
        path.write_text(json.dumps({"window_geometry": "### not base64 ###"}))

        assert load_preferences(path).window_geometry is None

    @pytest.mark.parametrize(
        "value",
        [
            [],
            [0],
            [420, -1],
            [420.5],
            ["420"],
            [True],
            "wide",
            {"left": 420},
            None,
        ],
    )
    def test_sizes_that_are_not_positive_whole_numbers_are_no_sizes(
        self, tmp_path: Path, value: object
    ) -> None:
        """A list a person edited by hand is checked here, not downstream."""
        path = tmp_path / SETTINGS_FILENAME
        path.write_text(json.dumps({"splitter_sizes": value}))

        assert load_preferences(path).splitter_sizes == ()

    def test_a_file_written_by_this_build_keeps_the_sizes_it_was_given(
        self, tmp_path: Path
    ) -> None:
        store = PreferenceStore(tmp_path / SETTINGS_FILENAME)

        preferences = store.remember_window(STATE, (640, 240, 180))

        assert preferences.splitter_sizes == (640, 240, 180)
        assert json.loads(store.path.read_text())["splitter_sizes"] == [640, 240, 180]

    def test_the_store_holds_no_window_state_before_the_window_has_closed(
        self, tmp_path: Path
    ) -> None:
        store = PreferenceStore(tmp_path / SETTINGS_FILENAME)

        assert store.preferences.window_geometry is None
        assert not store.path.exists()

    def test_a_junk_geometry_is_not_stored_when_the_window_closes(self, tmp_path: Path) -> None:
        """Refusing at the boundary holds on the way in as well as on the way out."""
        store = PreferenceStore(tmp_path / SETTINGS_FILENAME)

        preferences = store.remember_window("### not base64 ###", (300, 300))

        assert preferences.window_geometry is None
        assert preferences.splitter_sizes == (300, 300)


class TestTheStore:
    def test_a_store_reads_the_file_once_and_exposes_the_preferences(self, tmp_path: Path) -> None:
        path = tmp_path / SETTINGS_FILENAME
        path.write_text(json.dumps({"language": "it"}))

        store = PreferenceStore(path)

        assert store.preferences.language == "it"
        assert store.path == path

    def test_changing_a_preference_writes_it_and_returns_the_new_value(
        self, tmp_path: Path
    ) -> None:
        store = PreferenceStore(tmp_path / SETTINGS_FILENAME)

        preferences = store.set_language("es")

        assert preferences.language == "es"
        assert store.preferences.language == "es"
        assert json.loads(store.path.read_text())["language"] == "es"

    def test_remembering_a_folder_uses_the_directory_of_the_file_it_was_given(
        self, tmp_path: Path
    ) -> None:
        folder = tmp_path / "Music"
        folder.mkdir()
        song = folder / "song.wav"
        store = PreferenceStore(tmp_path / SETTINGS_FILENAME)

        store.remember_folder(song)

        assert store.preferences.last_folder == folder

    def test_the_dialog_starts_where_the_last_song_came_from(self, tmp_path: Path) -> None:
        folder = tmp_path / "Music"
        folder.mkdir()
        store = PreferenceStore(tmp_path / SETTINGS_FILENAME)

        assert store.start_folder() == ""

        store.remember_folder(folder / "song.wav")

        assert store.start_folder() == str(folder)

    def test_a_file_that_cannot_be_written_loses_the_preference_not_the_window(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """``path`` is inside a file, so no directory can be created for it."""
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory")
        store = PreferenceStore(blocker / SETTINGS_FILENAME)

        with caplog.at_level(logging.WARNING):
            preferences = store.set_language("es")

        assert preferences.language == "es"
        assert store.preferences.language == "es"
        assert not (blocker / SETTINGS_FILENAME).exists()
        assert any("preferences" in record.getMessage().lower() for record in caplog.records)

    def test_a_store_without_a_file_on_disk_is_still_the_defaults(self, tmp_path: Path) -> None:
        store = PreferenceStore(tmp_path / "nothing" / SETTINGS_FILENAME)

        assert store.preferences == Preferences()

    def test_reading_preferences_never_creates_the_file(self, tmp_path: Path) -> None:
        path = tmp_path / SETTINGS_FILENAME

        store = PreferenceStore(path)

        assert store.preferences == Preferences()
        assert not path.exists()
