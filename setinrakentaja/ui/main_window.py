"""Pääikkuna: vientijono vasemmalla, soittolista (kansi, suodatinpainikkeet, kappaleet) oikealla."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..core.builder import build_tracks
from ..core.exporter import ExportError, ExportPlaylist, export_xml
from ..core.library import Library, LibraryError, Track, load_library
from ..core.recipe import Recipe
from . import theme
from .filter_panel import FilterPanel, section_summary
from .track_model import TrackTableModel, TrackTableView
from .widgets import CoverLabel, FilterChip, HeroPanel, QueueList, label, pill_button, search_with_icon

APP_NAME = "Setinrakentaja"


@dataclass
class QueueEntry:
    recipe: Recipe
    tracks: list[Track]

    @property
    def key(self) -> tuple[str, str]:
        return (self.recipe.folder.strip("/ ").lower(), self.recipe.name.strip().lower())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1440, 900)
        self.setMinimumSize(1100, 680)
        self.settings = QSettings()  # organisaatio- ja sovellusnimi asetetaan app.py:ssä
        self.library: Library | None = None
        self.current = Recipe()
        self.queue: list[QueueEntry] = []
        self._unsaved = False

        self._build_ui()
        self._build_menus()
        self._refresh_queue_view()
        self._set_enabled(False)
        self._update_info()

        notation = self.settings.value("key_notation", "both")
        self._set_notation(notation)

        last = self.settings.value("last_library", "")
        if last and Path(last).exists():
            self.open_library(last, quiet=True)

    # ================================================================ UI
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 10, 14, 4)
        outer.setSpacing(12)

        self.filters = FilterPanel(root)
        self.filters.hide()
        self.filters.build_requested.connect(self.build_list)

        # --- yläpalkki
        top = QHBoxLayout()
        top.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(theme.cover_pixmap("Setinrakentaja", 28, radius=14))
        top.addWidget(logo)
        top.addWidget(label(APP_NAME, "logo"))
        top.addSpacing(14)
        self.library_btn = pill_button("Avaa kirjasto…", "ghost", "Avaa Rekordboxin XML-vienti (⌘O)")
        self.library_btn.clicked.connect(lambda: self.open_library())
        top.addWidget(self.library_btn)
        top.addStretch(1)
        self.search = search_with_icon(self.filters.text_search)
        self.search.setMinimumWidth(420)
        self.search.setMaximumWidth(620)
        self.search.textChanged.connect(lambda _: self._search_timer.start())
        self.search.returnPressed.connect(self.build_list)
        top.addWidget(self.search, 3)
        top.addStretch(1)
        self.recipe_btn = pill_button("Reseptit  ▾", "", "Tallenna ja avaa suodatinyhdistelmiä")
        top.addWidget(self.recipe_btn)
        self.more_btn = pill_button("⋯", "icon", "Näkymä ja ohjeet")
        top.addWidget(self.more_btn)
        self.export_btn = pill_button("⇪  Vie XML", "", "Vie vientijonon soittolistat uuteen rekordbox.xml-tiedostoon (⌘E)")
        self.export_btn.clicked.connect(self.export)
        top.addWidget(self.export_btn)
        outer.addLayout(top)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(350)
        self._search_timer.timeout.connect(self._auto_build)

        body = QSplitter(Qt.Horizontal)
        body.setHandleWidth(10)

        # --- vasen: vientijono kortteina
        left = QFrame()
        left.setObjectName("panel")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(18, 16, 12, 14)
        lv.setSpacing(10)
        lh = QHBoxLayout()
        lh.addWidget(label("Vientijono", "h1"))
        lh.addStretch(1)
        self.new_btn = pill_button("+  Uusi", "", "Aloita uusi soittolista tyhjillä suodattimilla")
        self.new_btn.clicked.connect(self.new_playlist)
        lh.addWidget(self.new_btn)
        lv.addLayout(lh)
        sub = label("Nämä soittolistat tallennetaan samaan XML-tiedostoon.", "faint")
        sub.setWordWrap(True)
        lv.addWidget(sub)
        self.queue_list = QueueList()
        self.queue_list.itemDoubleClicked.connect(self._queue_item_activated)
        self.queue_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.queue_list.customContextMenuRequested.connect(self._queue_menu)
        QShortcut(QKeySequence.Delete, self.queue_list, activated=self.remove_from_queue)
        QShortcut(QKeySequence(Qt.Key_Backspace), self.queue_list, activated=self.remove_from_queue)
        lv.addWidget(self.queue_list, 1)
        self.queue_empty = label(
            "Jono on tyhjä.\n\nKoosta lista oikealla ja paina »+ Lisää jonoon«.", "faint"
        )
        self.queue_empty.setWordWrap(True)
        self.queue_empty.setAlignment(Qt.AlignCenter)
        lv.addWidget(self.queue_empty, 1)
        qb = QHBoxLayout()
        self.queue_edit_btn = pill_button("Avaa", "ghost", "Avaa valittu lista muokattavaksi")
        self.queue_edit_btn.clicked.connect(lambda: self._queue_item_activated(self.queue_list.currentItem()))
        self.queue_remove_btn = pill_button("Poista", "ghost", "Poista valittu lista jonosta")
        self.queue_remove_btn.clicked.connect(self.remove_from_queue)
        qb.addWidget(self.queue_edit_btn)
        qb.addWidget(self.queue_remove_btn)
        qb.addStretch(1)
        lv.addLayout(qb)
        left.setMinimumWidth(240)
        body.addWidget(left)

        # --- oikea: hero + suodatinpainikkeet + taulukko
        right = HeroPanel()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(26, 26, 22, 8)
        rv.setSpacing(14)

        hero = QHBoxLayout()
        hero.setSpacing(26)
        self.cover = CoverLabel(176)
        hero.addWidget(self.cover, 0, Qt.AlignTop)
        hv = QVBoxLayout()
        hv.setSpacing(4)
        hv.addSpacing(6)
        hv.addWidget(label("Soittolista", "eyebrow"))
        self.name_edit = QLineEdit(self.current.name)
        self.name_edit.setObjectName("title")
        self.name_edit.setPlaceholderText("Nimetön soittolista")
        self.name_edit.setToolTip("Soittolistan nimi – napsauta muokataksesi")
        self.name_edit.textChanged.connect(self._update_cover)
        hv.addWidget(self.name_edit)
        self.folder_edit = QLineEdit()
        self.folder_edit.setObjectName("folder")
        self.folder_edit.setPlaceholderText("📁  Lisää kansio, esim. Keikat/2026 Joulu")
        self.folder_edit.setToolTip("Kansio Rekordboxissa. Alikansiot erotetaan kauttaviivalla.")
        hv.addWidget(self.folder_edit)
        hv.addSpacing(4)
        self.info = label("", "muted")
        hv.addWidget(self.info)
        hv.addStretch(1)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.build_btn = pill_button("▶  Luo lista", "primary", "Hae ja järjestä kappaleet suodattimien mukaan (Enter)")
        self.build_btn.clicked.connect(self.build_list)
        actions.addWidget(self.build_btn)
        self.add_queue_btn = pill_button("+  Lisää jonoon", "", "Lisää tämä lista vientijonoon (samanniminen korvataan)")
        self.add_queue_btn.clicked.connect(self.add_to_queue)
        actions.addWidget(self.add_queue_btn)
        actions.addStretch(1)
        self.up_btn = pill_button("↑", "icon", "Siirrä valitut ylös (⌘↑). Rivejä voi myös raahata.")
        self.up_btn.clicked.connect(lambda: self.table.move_selected(-1))
        self.down_btn = pill_button("↓", "icon", "Siirrä valitut alas (⌘↓)")
        self.down_btn.clicked.connect(lambda: self.table.move_selected(1))
        self.remove_btn = pill_button("✕", "icon", "Poista valitut listalta (Delete). Poisto tallentuu reseptiin.")
        self.remove_btn.clicked.connect(self.remove_selected)
        self.restore_btn = pill_button("↺", "icon", "Palauta käsin poistetut kappaleet")
        self.restore_btn.clicked.connect(self.restore_removed)
        for b in (self.up_btn, self.down_btn, self.remove_btn, self.restore_btn):
            actions.addWidget(b)
        hv.addLayout(actions)
        hero.addLayout(hv, 1)
        rv.addLayout(hero)
        rv.addSpacing(4)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        self.chips: dict[str, FilterChip] = {}
        order = [
            ("genre", "Genre"), ("key", "Sävellaji"), ("bpm", "BPM"), ("rating", "Arvio"),
            ("tags", "Tagit"), ("more", "Lisää"),
        ]
        for key, text in order:
            title, widget = self.filters.sections[key]
            chip = FilterChip(key, text, title, widget)
            chip.closed.connect(self._chip_closed)
            self.chips[key] = chip
            chips.addWidget(chip)
        self.clear_btn = pill_button("Tyhjennä", "ghost", "Tyhjennä suodattimet (järjestys ja pituus säilyvät)")
        self.clear_btn.clicked.connect(self.clear_filters)
        chips.addWidget(self.clear_btn)
        chips.addStretch(1)
        for key, text in (("limit", "Pituus"), ("sort", "Järjestys")):
            title, widget = self.filters.sections[key]
            chip = FilterChip(key, text, title, widget)
            chip.closed.connect(self._chip_closed)
            self.chips[key] = chip
            chips.addWidget(chip)
        rv.addLayout(chips)

        self.model = TrackTableModel()
        self.model.changed.connect(self._update_info)
        self.table = TrackTableView()
        self.table.setModel(self.model)
        self.table.remove_requested.connect(self.remove_selected)

        self.stack = QStackedWidget()
        welcome = QWidget()
        wv = QVBoxLayout(welcome)
        wv.addStretch(1)
        wt = label("Aloita avaamalla Rekordbox-kirjastosi", "h1")
        wt.setAlignment(Qt.AlignCenter)
        wv.addWidget(wt)
        ws = label(
            "Vie kirjasto Rekordboxissa: File > Export Collection in xml format.\n"
            "Sovellus vain lukee tiedostoa – Rekordboxin tietokantaan ei kosketa.",
            "muted",
        )
        ws.setAlignment(Qt.AlignCenter)
        wv.addWidget(ws)
        wb = pill_button("Avaa rekordbox.xml…", "primary")
        wb.clicked.connect(lambda: self.open_library())
        wbl = QHBoxLayout()
        wbl.addStretch(1)
        wbl.addWidget(wb)
        wbl.addStretch(1)
        wv.addSpacing(10)
        wv.addLayout(wbl)
        wv.addStretch(2)
        self.stack.addWidget(welcome)
        self.stack.addWidget(self.table)
        self.empty_label = label("", "muted")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.stack.addWidget(self.empty_label)
        rv.addWidget(self.stack, 1)

        body.addWidget(right)
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        body.setSizes([300, 1100])
        outer.addWidget(body, 1)

        self.setCentralWidget(root)
        self.statusBar().showMessage("Valmis")
        self._last_built: dict | None = None
        self._update_cover()
        self.queue_list.itemSelectionChanged.connect(self._update_queue_buttons)

    def _update_cover(self) -> None:
        seed = self.name_edit.text().strip() or "Nimetön"
        self.cover.set_seed(seed)
        self.centralWidget().findChild(HeroPanel).set_color(theme.cover_color(seed))

    def _filters_signature(self) -> dict:
        d = self.filters.get_recipe(self.current).to_dict()
        for k in ("name", "folder", "version"):
            d.pop(k, None)
        return d

    def _update_chips(self) -> None:
        r = self.filters.get_recipe()
        for key, chip in self.chips.items():
            chip.set_summary(section_summary(key, r))

    def _chip_closed(self, key: str) -> None:
        self._update_chips()
        self._auto_build()

    def _auto_build(self) -> None:
        """Luo listan uudelleen vain, jos suodattimet ovat muuttuneet edellisestä."""
        if self.library is None:
            return
        if self._filters_signature() != self._last_built:
            self.build_list()

    def clear_filters(self) -> None:
        self.filters.reset()
        self._update_chips()
        self._auto_build()

    def new_playlist(self) -> None:
        self.current = Recipe()
        self.filters.set_recipe(Recipe())
        self.name_edit.setText("Uusi soittolista")
        self.folder_edit.clear()
        self.queue_list.clearSelection()
        self._update_chips()
        self.model.set_tracks([])
        self._last_built = None
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _build_menus(self) -> None:
        mb = self.menuBar()
        m = mb.addMenu("&Tiedosto")
        self.act_open = QAction("Avaa kirjasto (rekordbox.xml)…", self, shortcut=QKeySequence.Open)
        self.act_open.triggered.connect(lambda: self.open_library())
        self.act_reload = QAction("Lataa kirjasto uudelleen", self, shortcut="Ctrl+R")
        self.act_reload.triggered.connect(self.reload_library)
        m.addAction(self.act_open)
        m.addAction(self.act_reload)
        m.addSeparator()
        self.act_export = QAction("Vie jono XML-tiedostoksi…", self, shortcut="Ctrl+E")
        self.act_export.triggered.connect(self.export)
        m.addAction(self.act_export)
        m.addSeparator()
        quit_act = QAction("Lopeta", self, shortcut=QKeySequence.Quit)
        quit_act.triggered.connect(self.close)
        m.addAction(quit_act)

        r = mb.addMenu("&Resepti")
        self.act_load_recipe = QAction("Avaa resepti…", self, shortcut="Ctrl+Shift+O")
        self.act_load_recipe.triggered.connect(self.load_recipe)
        self.act_save_recipe = QAction("Tallenna nykyinen resepti…", self, shortcut=QKeySequence.Save)
        self.act_save_recipe.triggered.connect(self.save_recipe)
        self.act_batch = QAction("Luo soittolistat resepteistä vientijonoon…", self)
        self.act_batch.triggered.connect(self.batch_from_recipes)
        self.act_save_queue = QAction("Tallenna vientijonon reseptit kansioon…", self)
        self.act_save_queue.triggered.connect(self.save_queue_recipes)
        for a in (self.act_load_recipe, self.act_save_recipe):
            r.addAction(a)
        r.addSeparator()
        r.addAction(self.act_batch)
        r.addAction(self.act_save_queue)
        self.recipe_btn.setMenu(r)

        v = mb.addMenu("&Näytä")
        km = v.addMenu("Sävellajimerkintä")
        self.notation_group = QActionGroup(self)
        self.notation_actions = {}
        for key, text in (("both", "Molemmat (8A (Am))"), ("camelot", "Camelot (8A)"), ("classical", "Perinteinen (Am)")):
            a = QAction(text, self, checkable=True)
            a.triggered.connect(lambda _=False, k=key: self._set_notation(k))
            self.notation_group.addAction(a)
            km.addAction(a)
            self.notation_actions[key] = a

        h = mb.addMenu("&Ohje")
        a = QAction("Näin tuot listat Rekordboxiin", self)
        a.triggered.connect(self.show_import_help)
        h.addAction(a)
        a = QAction("Tietoja", self)
        a.triggered.connect(
            lambda: QMessageBox.about(
                self,
                APP_NAME,
                f"<b>{APP_NAME}</b> {__version__}<br>Rekordbox-soittolistojen kokoaja.<br><br>"
                "Lukee Rekordboxin XML-viennin ja kirjoittaa aina <i>uuden</i> XML-tiedoston. "
                "Rekordboxin tietokantaa (master.db) ei kosketa.",
            )
        )
        h.addAction(a)

        more = QMenu(self)
        more.addMenu(km)
        more.addSeparator()
        for act in h.actions():
            more.addAction(act)
        self.more_btn.setMenu(more)
        self.more_btn.setStyleSheet("QPushButton::menu-indicator { width: 0; }")

    def _set_enabled(self, on: bool) -> None:
        for w in (
            self.table, self.up_btn, self.down_btn, self.remove_btn, self.restore_btn,
            self.add_queue_btn, self.build_btn, self.search, self.clear_btn, self.act_reload,
            self.act_batch, self.act_load_recipe, self.act_save_recipe, *self.chips.values(),
        ):
            w.setEnabled(on)
        self.stack.setCurrentIndex(1 if on else 0)
        self._update_queue_buttons()

    def _update_queue_buttons(self) -> None:
        has = bool(self.queue) and self.library is not None
        for w in (self.export_btn, self.act_export, self.act_save_queue):
            w.setEnabled(has)
        sel = self.queue_list.currentItem() is not None
        for w in (self.queue_remove_btn, self.queue_edit_btn):
            w.setEnabled(has and sel)

    def _set_notation(self, key: str) -> None:
        if key not in self.notation_actions:
            key = "both"
        self.notation_actions[key].setChecked(True)
        self.model.set_key_notation(key)
        self.settings.setValue("key_notation", key)

    # ================================================================ kirjasto
    def _start_dir(self, key: str) -> str:
        return self.settings.value(key, str(Path.home()))

    def open_library(self, path: str | None = None, quiet: bool = False) -> None:
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Avaa Rekordboxin XML-vienti", self._start_dir("dir_library"), "Rekordbox XML (*.xml)"
            )
            if not path:
                return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            lib = load_library(path)
        except LibraryError as e:
            QApplication.restoreOverrideCursor()
            if not quiet:
                QMessageBox.critical(self, "Kirjaston avaus epäonnistui", str(e))
            return
        QApplication.restoreOverrideCursor()
        self._apply_library(lib)
        self.settings.setValue("last_library", str(lib.path))
        self.settings.setValue("dir_library", str(lib.path.parent))

    def _apply_library(self, lib: Library) -> None:
        old = self.library
        self.library = lib
        self.filters.set_library(lib)
        self._set_enabled(True)
        ver = f"{lib.product_name} {lib.product_version}".strip()
        self.statusBar().showMessage(f"Kirjasto: {lib.path}  ·  {ver}")
        self.library_btn.setText(f"📚  {lib.path.name}  ·  {len(lib.tracks)} kpl")
        if old is not None:
            # kirjasto vaihtui: päivitetään jono resepteistä, jotta kappaleviittaukset ovat ajantasaiset
            self.rebuild_queue()
        self._update_chips()
        self.model.set_tracks([])
        self._last_built = None

    def reload_library(self) -> None:
        if self.library:
            self.open_library(str(self.library.path))

    # ================================================================ lista
    def _recipe_from_ui(self) -> Recipe:
        self.current.name = self.name_edit.text().strip() or "Nimetön soittolista"
        self.current.folder = self.folder_edit.text().strip().strip("/")
        self.current = self.filters.get_recipe(self.current)
        return self.current

    def build_list(self) -> None:
        if not self.library:
            return
        recipe = self._recipe_from_ui()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            tracks = build_tracks(self.library, recipe)
        finally:
            QApplication.restoreOverrideCursor()
        self._last_built = self._filters_signature()
        self._update_chips()
        self.model.set_tracks(tracks)

    def _update_info(self) -> None:
        tr = self.model.tracks
        if self.library is None:
            self.info.setText("Ei kirjastoa avattuna")
            return
        if not tr:
            if self._last_built is None:
                self.info.setText(f"{len(self.library.tracks)} kappaletta kirjastossa")
                self.empty_label.setText(
                    "Valitse suodattimet yllä olevista painikkeista tai hae artistia,\n"
                    "ja paina »▶ Luo lista«."
                )
            else:
                self.info.setText("Ei kappaleita")
                self.empty_label.setText("Yksikään kappale ei täyttänyt ehtoja.\nKokeile väljentää suodattimia.")
            self.stack.setCurrentIndex(2)
            return
        self.stack.setCurrentIndex(1)
        total = sum(t.duration for t in tr)
        bpms = [t.bpm for t in tr if t.bpm]
        parts = [f"<b style='color:{theme.TEXT}'>{len(tr)} kappaletta</b>, {_fmt_long(total)}"]
        if bpms:
            parts.append(f"BPM {min(bpms):g}–{max(bpms):g}")
        removed = len(self.current.manual_exclude)
        if removed:
            parts.append(f"{removed} poistettu käsin")
        self.info.setText("  ·  ".join(parts))

    def remove_selected(self) -> None:
        rows = self.table.selected_rows()
        if not rows:
            return
        removed = self.model.remove_rows(rows)
        for t in removed:
            if t.location not in self.current.manual_exclude:
                self.current.manual_exclude.append(t.location)
        self._update_info()

    def restore_removed(self) -> None:
        self.current.manual_exclude.clear()
        self.build_list()

    # ================================================================ jono
    def add_to_queue(self) -> None:
        if not self.model.tracks:
            QMessageBox.information(self, APP_NAME, "Lista on tyhjä.")
            return
        recipe = copy.deepcopy(self._recipe_from_ui())
        entry = QueueEntry(recipe, list(self.model.tracks))
        for i, e in enumerate(self.queue):
            if e.key == entry.key:
                self.queue[i] = entry
                self.statusBar().showMessage(f"Korvattiin jonossa: {recipe.name}", 4000)
                break
        else:
            self.queue.append(entry)
            self.statusBar().showMessage(f"Lisättiin jonoon: {recipe.name}", 4000)
        self._refresh_queue()

    def _refresh_queue(self) -> None:
        self._unsaved = bool(self.queue)
        self._refresh_queue_view()

    def _refresh_queue_view(self) -> None:
        self.queue_list.clear()
        for i, e in enumerate(self.queue):
            folder = e.recipe.folder.strip("/ ") or "Juuritaso"
            dur = _fmt_long(sum(t.duration for t in e.tracks))
            self.queue_list.add_card(e.recipe.name, f"📁 {folder}\n{len(e.tracks)} kpl · {dur}", e.recipe.name, i)
        has = bool(self.queue)
        self.queue_list.setVisible(has)
        self.queue_empty.setVisible(not has)
        n = len(self.queue)
        self.export_btn.setText(f"⇪  Vie XML ({n})" if n else "⇪  Vie XML")
        self.export_btn.setObjectName("primary" if n else "")
        self.export_btn.style().unpolish(self.export_btn)
        self.export_btn.style().polish(self.export_btn)
        self._update_queue_buttons()

    def _queue_item_activated(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        idx = item.data(Qt.UserRole)
        if idx is None:
            return
        e = self.queue[idx]
        self.current = copy.deepcopy(e.recipe)
        self.name_edit.setText(e.recipe.name)
        self.folder_edit.setText(e.recipe.folder)
        self.filters.set_recipe(e.recipe)
        self._update_chips()
        self.model.set_tracks(e.tracks)
        self._last_built = self._filters_signature()
        self.statusBar().showMessage(
            f"Avattiin muokattavaksi: {e.recipe.name}. Paina »+ Lisää jonoon« tallentaaksesi muutokset.", 6000
        )

    def _queue_menu(self, pos) -> None:
        item = self.queue_list.itemAt(pos)
        if item is None:
            return
        self.queue_list.setCurrentItem(item)
        menu = QMenu(self)
        menu.addAction("Avaa muokattavaksi", lambda: self._queue_item_activated(item))
        menu.addAction("Poista jonosta", self.remove_from_queue)
        menu.exec(self.queue_list.mapToGlobal(pos))

    def remove_from_queue(self) -> None:
        item = self.queue_list.currentItem()
        if item is None:
            return
        idx = item.data(Qt.UserRole)
        self.queue = [e for i, e in enumerate(self.queue) if i != idx]
        self._refresh_queue()

    def rebuild_queue(self) -> None:
        """Luo jonon listat uudelleen resepteistä nykyisestä kirjastosta.

        Huom: käsin tehdyt järjestysmuutokset menetetään, poistot säilyvät.
        """
        if not self.library or not self.queue:
            return
        for e in self.queue:
            e.tracks = build_tracks(self.library, e.recipe)
        self._refresh_queue()

    # ================================================================ reseptit
    def save_recipe(self) -> None:
        if not self.library:
            return
        r = self._recipe_from_ui()
        default = Path(self._start_dir("dir_recipes")) / f"{_safe_name(r.name)}.json"
        path, _ = QFileDialog.getSaveFileName(self, "Tallenna resepti", str(default), "Resepti (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        r.save(path)
        self.settings.setValue("dir_recipes", str(Path(path).parent))
        self.statusBar().showMessage(f"Resepti tallennettu: {path}", 5000)

    def load_recipe(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Avaa resepti", self._start_dir("dir_recipes"), "Resepti (*.json)"
        )
        if not path:
            return
        try:
            r = Recipe.load(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Reseptin avaus epäonnistui", str(e))
            return
        self.settings.setValue("dir_recipes", str(Path(path).parent))
        self.current = r
        self.name_edit.setText(r.name)
        self.folder_edit.setText(r.folder)
        self.filters.set_recipe(r)
        self._update_chips()
        self.build_list()

    def batch_from_recipes(self) -> None:
        if not self.library:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Valitse reseptit", self._start_dir("dir_recipes"), "Resepti (*.json)"
        )
        if not paths:
            return
        errors, added = [], 0
        for p in sorted(paths):
            try:
                r = Recipe.load(p)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{Path(p).name}: {e}")
                continue
            entry = QueueEntry(r, build_tracks(self.library, r))
            self.queue = [e for e in self.queue if e.key != entry.key] + [entry]
            added += 1
        self._refresh_queue()
        msg = f"Jonoon lisättiin {added} soittolistaa."
        empty = [e.recipe.name for e in self.queue if not e.tracks]
        if empty:
            msg += "\n\nHuom: seuraavat listat ovat tyhjiä eikä niitä voi viedä:\n" + "\n".join(empty)
        if errors:
            msg += "\n\nVirheet:\n" + "\n".join(errors)
        QMessageBox.information(self, APP_NAME, msg)

    def save_queue_recipes(self) -> None:
        if not self.queue:
            return
        d = QFileDialog.getExistingDirectory(self, "Valitse kansio resepteille", self._start_dir("dir_recipes"))
        if not d:
            return
        for e in self.queue:
            parts = [_safe_name(p) for p in e.recipe.folder.split("/") if p.strip()]
            name = "_".join(parts + [_safe_name(e.recipe.name)])
            e.recipe.save(Path(d) / f"{name}.json")
        self.settings.setValue("dir_recipes", d)
        self.statusBar().showMessage(f"{len(self.queue)} reseptiä tallennettu kansioon {d}", 5000)

    # ================================================================ vienti
    def export(self) -> None:
        if not self.library or not self.queue:
            return
        empty = [e.recipe.name for e in self.queue if not e.tracks]
        if empty:
            QMessageBox.warning(self, APP_NAME, "Tyhjiä listoja ei voi viedä:\n" + "\n".join(empty))
            return
        default_dir = Path(self.settings.value("dir_export", str(self.library.path.parent)))
        default = default_dir / f"setinrakentaja_{date.today().isoformat()}.xml"
        path, _ = QFileDialog.getSaveFileName(
            self, "Tallenna uusi rekordbox.xml", str(default), "Rekordbox XML (*.xml)"
        )
        if not path:
            return
        if not path.lower().endswith(".xml"):
            path += ".xml"
        playlists = [ExportPlaylist(e.recipe.name, e.tracks, e.recipe.folder) for e in self.queue]
        try:
            # Tallennusikkuna on jo kysynyt luvan korvata olemassa oleva (muu kuin lähde)tiedosto.
            out = export_xml(self.library, playlists, path, overwrite=True)
        except (ExportError, OSError) as e:
            QMessageBox.critical(self, "Vienti epäonnistui", str(e))
            return
        self._unsaved = False
        self.settings.setValue("dir_export", str(Path(out).parent))
        n = sum(len(p.tracks) for p in playlists)
        QMessageBox.information(
            self,
            "Vienti valmis",
            f"Tallennettu: {out}\n\n{len(playlists)} soittolistaa, {n} kappaleviittausta.\n\n"
            "Tuo Rekordboxiin: Asetukset (Preferences) > Lisäasetukset (Advanced) > "
            "Tietokanta (Database) > rekordbox xml > Imported Library: valitse tämä tiedosto. "
            "Listat näkyvät selaimen kohdassa »rekordbox xml«.",
        )

    def show_import_help(self) -> None:
        QMessageBox.information(
            self,
            "Tuonti Rekordboxiin",
            "<b>1. Vie kirjasto Rekordboxista</b><br>"
            "Tiedosto (File) > Vie kokoelma XML-muodossa (Export Collection in xml format).<br><br>"
            "<b>2. Kokoa listat tässä sovelluksessa</b> ja vie ne: Tiedosto > Vie jono XML-tiedostoksi.<br><br>"
            "<b>3. Tuo Rekordboxiin</b><br>"
            "Preferences > Advanced > Database > rekordbox xml > Imported Library > Browse: valitse "
            "viety tiedosto. Ota tarvittaessa käyttöön näkymä: Preferences > View > Layout > "
            "»rekordbox xml«.<br><br>"
            "<b>4.</b> Selaimen »rekordbox xml« -kohdassa näkyvät uudet listat. Napsauta listaa "
            "hiiren oikealla ja valitse »Import Playlist« (Tuo soittolista).<br><br>"
            "Kappaleet tunnistetaan tiedostopolun (Location) perusteella, joten cue-pisteet ja "
            "muut tiedot säilyvät.",
        )

    def closeEvent(self, event):
        if self._unsaved:
            res = QMessageBox.question(
                self,
                APP_NAME,
                "Vientijonon muutoksia ei ole viety XML-tiedostoon. Lopetetaanko silti?",
            )
            if res != QMessageBox.Yes:
                event.ignore()
                return
        event.accept()


def _safe_name(s: str) -> str:
    keep = "".join(c if c.isalnum() or c in " -_." else "_" for c in s).strip()
    return keep or "resepti"


def _fmt_long(sec: int) -> str:
    h, rem = divmod(int(sec), 3600)
    m = rem // 60
    return f"{h} h {m} min" if h else f"{m} min"
