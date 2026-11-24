import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from setinrakentaja.core.keys import camelot_to_classical  # noqa: E402
from setinrakentaja.core.recipe import Recipe  # noqa: E402
from setinrakentaja.ui.main_window import MainWindow  # noqa: E402

SAMPLE = Path(__file__).parent / "data" / "esimerkki_rekordbox.xml"


@pytest.fixture(scope="module")
def app():
    QSettings.setDefaultFormat(QSettings.IniFormat)
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("SetinrakentajaTesti")
    app.setApplicationName("SetinrakentajaTesti")
    from setinrakentaja.ui.theme import apply_theme

    apply_theme(app)
    return app


@pytest.fixture
def win(app, tmp_path, monkeypatch):
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path / "settings"))
    w = MainWindow()
    w.settings.clear()
    w.open_library(str(SAMPLE))
    yield w
    w._unsaved = False
    w.close()


def test_full_flow(win, tmp_path):
    f = win.filters
    f.bpm_min.setValue(120)
    f.bpm_max.setValue(128)
    f.genres.exclude.set_checked(["Techno"])
    f.sort_mode.setCurrentIndex(f.sort_mode.findData("harmonic"))
    win.name_edit.setText("Lämmittely")
    win.folder_edit.setText("Keikat/Joulu")
    win.build_list()
    tracks = win.model.tracks
    assert tracks and all(120 <= t.bpm <= 128 and t.genre != "Techno" for t in tracks)

    # poisto ja siirto
    n = len(tracks)
    removed = tracks[0]
    win.table.selectRow(0)
    win.remove_selected()
    assert len(win.model.tracks) == n - 1
    assert removed.location in win.current.manual_exclude
    first, second = win.model.tracks[0], win.model.tracks[1]
    win.table.selectRow(0)
    win.table.move_selected(1)
    assert win.model.tracks[1] is first and win.model.tracks[0] is second

    win.add_to_queue()
    f.genres.include.set_checked(["Disco"])
    f.genres.exclude.set_checked([])
    f.bpm_min.setValue(0)
    f.bpm_max.setValue(0)
    f.sort_mode.setCurrentIndex(f.sort_mode.findData("bpm"))
    win.name_edit.setText("Disco")
    win.folder_edit.setText("")
    win.build_list()
    win.add_to_queue()
    assert len(win.queue) == 2

    out = tmp_path / "vienti.xml"
    from setinrakentaja.core.exporter import ExportPlaylist, export_xml

    pls = [ExportPlaylist(e.recipe.name, e.tracks, e.recipe.folder) for e in win.queue]
    export_xml(win.library, pls, out)
    root = ET.parse(out).getroot()
    names = [n.get("Name") for n in root.iter("NODE")]
    assert names == ["ROOT", "Keikat", "Joulu", "Lämmittely", "Disco"]
    lam = [n for n in root.iter("NODE") if n.get("Name") == "Lämmittely"][0]
    assert [t.get("Key") for t in lam] == [t.track_id for t in win.queue[0].tracks]


def test_recipe_ui_roundtrip(win):
    r = Recipe(
        bpm_min=122, bpm_max=128.5, keys=["8A", "Em"], keys_compatible=True,
        genres_include=["Deep House"], genres_exclude=["Techno"], rating_min=3, rating_max=4,
        colours_include=["Punainen"], mytags_include=["Vocal"], mytags_include_mode="all",
        comment_contains="vocal", year_min=2020, added_from="2024-02-03", added_last_days=90,
        duration_min=300, duration_max=480, play_count_max=3, text_search="aurora",
        text_exclude="edit", sort_mode="energy_arc", arc_peak_position=0.6, target_minutes=90,
        target_count=20,
    )
    win.filters.set_recipe(r)
    back = win.filters.get_recipe()
    for field in ("bpm_min", "bpm_max", "keys_compatible", "genres_include", "genres_exclude",
                  "rating_min", "rating_max", "colours_include", "mytags_include",
                  "mytags_include_mode", "comment_contains", "year_min", "added_from",
                  "added_last_days", "duration_min", "duration_max", "play_count_max",
                  "text_search", "text_exclude", "sort_mode", "arc_peak_position",
                  "target_minutes", "target_count"):
        assert getattr(back, field) == getattr(r, field), field
    assert set(back.keys) == {"8A", "9A"}
    win.filters.set_recipe(Recipe())
    empty = win.filters.get_recipe()
    assert empty.bpm_min is None and empty.play_count_min is None and not empty.keys


def test_header_sort_and_notation(win):
    win.build_list()
    win.model.sort_by_column(4)
    bpms = [t.bpm for t in win.model.tracks]
    assert bpms == sorted(bpms)
    t = win.model.tracks[0]
    idx = win.model.index(0, 5)
    win._set_notation("classical")
    assert win.model.data(idx) == camelot_to_classical(t.camelot)
    win._set_notation("camelot")
    assert win.model.data(idx) == t.camelot
    win._set_notation("both")
    assert win.model.data(idx) == f"{t.camelot} ({camelot_to_classical(t.camelot)})"


def test_move_rows_edges(win):
    win.build_list()
    m = win.model
    ids = [t.track_id for t in m.tracks]
    assert m.move_rows([0, 1], m.rowCount()) == [len(ids) - 2, len(ids) - 1]
    assert [t.track_id for t in m.tracks] == ids[2:] + ids[:2]
    m.move_rows([len(ids) - 1], 0)
    assert m.tracks[0].track_id == ids[1]
    m.set_tracks([t for i in ids for t in win.library.tracks if t.track_id == i])
    m.move_rows([3], 3)  # paikallaan
    assert [t.track_id for t in m.tracks] == ids


def test_chips_and_popover(win):
    from setinrakentaja.ui.filter_panel import section_summary

    chip = win.chips["bpm"]
    assert chip.property("active") == "false"
    chip.open()
    QApplication.processEvents()
    assert win.filters.bpm_min.isVisible()
    win.filters.bpm_min.setValue(122)
    win.filters.bpm_max.setValue(128)
    chip.close_popover()
    QApplication.processEvents()
    # sulkeminen päivittää painikkeen ja luo listan automaattisesti
    assert chip.property("active") == "true" and "122" in chip.text()
    assert win.model.tracks and all(122 <= t.bpm <= 128 for t in win.model.tracks)
    # osion voi avata uudelleen
    chip.open()
    QApplication.processEvents()
    assert win.filters.bpm_min.isVisible()
    chip.close_popover()

    r = Recipe(keys=["8A", "9A"], keys_compatible=True, genres_include=["Disco", "Techno"],
               genres_exclude=["Afro House"], target_minutes=60, sort_mode="harmonic")
    assert section_summary("key", r) == "8A, 9A ≈"
    assert section_summary("genre", r) == "Disco +1 · ei Afro House"
    assert section_summary("limit", r) == "60 min"
    assert section_summary("sort", r) == "Harmoninen setti"
    assert section_summary("more", Recipe()) is None


def test_queue_cards(win):
    win.build_list()
    win.name_edit.setText("A")
    win.add_to_queue()
    win.name_edit.setText("B")
    win.folder_edit.setText("Keikat")
    win.add_to_queue()
    assert win.queue_list.count() == 2
    assert "Vie XML (2)" in win.export_btn.text()
    win.queue_list.setCurrentRow(0)
    win.remove_from_queue()
    assert [e.recipe.name for e in win.queue] == ["B"]
    win._queue_item_activated(win.queue_list.item(0))
    assert win.name_edit.text() == "B" and win.folder_edit.text() == "Keikat"
