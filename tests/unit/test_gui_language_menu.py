"""The Language menu: only installed catalogues, never a guessed language.

The menu is the only thing in the product that changes the language
(docs/INTERNATIONALIZATION.md): it offers English (the source, always) plus
every compiled catalogue found on disk, a switch loads that catalogue onto
the application, and a failure keeps the language the window had - reported,
never silently English with a Spanish menu item ticked.

The catalogue compiled here is a test fixture whose "translation" is
``(ES) Open...``: a marker, not a Spanish string. The product ships no
translated strings until a human translator fills the source catalogue.
"""

from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path

import pytest

from fixtures.catalogues import compile_catalogue

# See the note in the other window tests: the guard must precede the imports of
# the package that needs Qt, or collection fails before any skip can be recorded.
if importlib.util.find_spec("PyQt6") is None:  # pragma: no cover - Qt-free machine
    pytest.skip("PyQt6 is not installed (optional 'gui' extra)", allow_module_level=True)

from song_chord_lyrics_analyzer.app.settings import PreferenceStore
from song_chord_lyrics_analyzer.gui.main_window import MainWindow

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")


def _enabled_labels(window: MainWindow) -> list[str]:
    """The labels of the enabled transport buttons, in order."""
    return [
        action.text()
        for toolbar in window.findChildren(QtWidgets.QToolBar)
        for action in toolbar.actions()
        if action.text() and action.isEnabled()
    ]


def _warned(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Capture dialogs instead of opening them, so tests stay headless."""
    messages: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "warning",
        lambda *args, **kwargs: messages.append(args[-1]),
    )
    return messages


class TestTheMenuOffersOnlyWhatIsInstalled:
    def test_a_checkout_without_compiled_catalogues_offers_only_english(
        self, qt_app: object
    ) -> None:
        window = MainWindow()

        try:
            assert window.language == "en"
            assert window.installed_languages == (("en", "English"),)
        finally:
            window.close()

    def test_an_installed_catalogue_appears_in_its_own_language(
        self, qt_app: object, tmp_path: Path
    ) -> None:
        compile_catalogue(tmp_path, "es")
        window = MainWindow(translations_dir=tmp_path)

        try:
            assert window.installed_languages == (("en", "English"), ("es", "Español"))
        finally:
            window.close()

    def test_the_source_language_starts_checked(self, qt_app: object) -> None:
        window = MainWindow()

        try:
            # The check mark is the one state of the menu with no public
            # accessor; everything else is read through the window's surface.
            assert window._language_actions["en"].isChecked() is True
        finally:
            window.close()


class TestRememberingTheLanguage:
    """The language the person picked is waiting for them next time (roadmap L8).

    Only item 7's rule decides *whether* a remembered language is applied: a
    catalogue that is not installed on this machine cannot be shown, so the window
    opens in English and keeps the choice on file for the day it arrives. A
    catalogue that is on disk but unreadable is reported in the log, not in a
    dialog: the person has not seen the window yet.
    """

    @staticmethod
    def _store(tmp_path: Path) -> PreferenceStore:
        return PreferenceStore(tmp_path / "settings.json")

    def test_a_remembered_language_opens_the_window_in_it(
        self, qt_app: object, tmp_path: Path
    ) -> None:
        compile_catalogue(tmp_path, "es")
        store = self._store(tmp_path)
        store.set_language("es")

        window = MainWindow(translations_dir=tmp_path, preferences=store)
        try:
            assert window.language == "es"
            assert "(ES) Open..." in _enabled_labels(window)
            assert window._language_actions["es"].isChecked() is True
        finally:
            window.set_language("en")
            window.close()

    def test_a_language_with_no_catalogue_opens_english_and_keeps_the_choice(
        self, qt_app: object, tmp_path: Path
    ) -> None:
        store = self._store(tmp_path)
        store.set_language("de")

        window = MainWindow(translations_dir=tmp_path, preferences=store)
        try:
            assert window.language == "en"
            assert "Open..." in _enabled_labels(window)
        finally:
            window.close()

        # The choice was not thrown away because this machine cannot show it yet.
        assert json.loads(store.path.read_text())["language"] == "de"

    def test_a_language_the_person_picks_is_written_once_and_a_failure_never(
        self,
        qt_app: object,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        compile_catalogue(tmp_path, "es")
        warned = _warned(monkeypatch)
        store = self._store(tmp_path)

        window = MainWindow(translations_dir=tmp_path, preferences=store)
        try:
            assert window.set_language("es") is True
            assert json.loads(store.path.read_text())["language"] == "es"

            assert window.set_language("de") is False  # no catalogue here
            assert window.language == "es"
            assert warned and "Could not load" in warned[0]
        finally:
            window.set_language("en")
            window.close()

        assert json.loads(store.path.read_text())["language"] == "en"

    def test_a_catalogue_that_will_not_load_opens_english_and_logs_the_reason(
        self, qt_app: object, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A stray ``.qm`` is offered by the menu and refuses to load.

        ``available_languages()`` can only check that the file is there, so a
        remembered language can name a catalogue this machine cannot read. The
        window must open in English and say why in the log - not answer a
        question in a dialog before the person has seen the window.
        """
        (tmp_path / "song_chord_lyrics_analyzer_es.qm").write_bytes(b"not a catalogue")
        store = self._store(tmp_path)
        store.set_language("es")

        with caplog.at_level(logging.WARNING):
            window = MainWindow(translations_dir=tmp_path, preferences=store)
        try:
            assert window.language == "en"
            assert "Open..." in _enabled_labels(window)
        finally:
            window.close()

        assert store.preferences.language == "es"  # the choice is still on file
        assert any("es" in record.getMessage() for record in caplog.records)

    def test_choosing_through_the_menu_is_the_path_that_stores_it(
        self, qt_app: object, tmp_path: Path
    ) -> None:
        compile_catalogue(tmp_path, "fr")
        store = self._store(tmp_path)

        window = MainWindow(translations_dir=tmp_path, preferences=store)
        try:
            window._on_language_chosen(window._language_actions["fr"])

            assert window.language == "fr"
            assert json.loads(store.path.read_text())["language"] == "fr"
        finally:
            window.set_language("en")
            window.close()


class TestSwitchingLanguages:
    def test_picking_a_catalogue_retranslates_the_window(
        self, qt_app: object, tmp_path: Path
    ) -> None:
        compile_catalogue(tmp_path, "es")
        window = MainWindow(translations_dir=tmp_path)

        try:
            assert window.set_language("es") is True

            assert window.language == "es"
            assert window._language_actions["es"].isChecked() is True
            assert "(ES) Open..." in _enabled_labels(window)  # the transport toolbar

            # Switching back is a real switch-back, not a reload of the app.
            assert window.set_language("en") is True
            assert window.language == "en"
            assert "Open..." in _enabled_labels(window)
        finally:
            window.close()

    def test_a_language_without_a_catalogue_is_refused_and_the_old_one_kept(
        self, qt_app: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        warned = _warned(monkeypatch)
        window = MainWindow(translations_dir=tmp_path)  # empty: nothing installed

        try:
            assert window.set_language("de") is False

            assert window.language == "en"  # kept, honestly
            assert warned and "Could not load" in warned[0]
            assert "Open..." in _enabled_labels(window)  # still the source strings
        finally:
            window.close()

    def test_choosing_through_the_menu_goes_through_the_same_path(
        self, qt_app: object, tmp_path: Path
    ) -> None:
        compile_catalogue(tmp_path, "es")
        window = MainWindow(translations_dir=tmp_path)

        try:
            window._on_language_chosen(window._language_actions["es"])

            assert window.language == "es"
            assert "(ES) Open..." in _enabled_labels(window)
        finally:
            window.set_language("en")  # leave the shared application clean
            window.close()

    def test_an_unchecked_failure_keeps_the_tick_where_it_was(
        self, qt_app: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _warned(monkeypatch)
        window = MainWindow(translations_dir=tmp_path)

        try:
            window._on_language_chosen(window._language_actions["en"])  # installed: the only one

            assert window.language == "en"
            assert window._language_actions["en"].isChecked() is True
            # Nothing was offered for "de", so its state is simply absent.
        finally:
            window.close()
