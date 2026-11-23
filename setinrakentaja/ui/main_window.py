"""Pääikkuna: suodattimet vasemmalla, esikatselu ja vientijono oikealla."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..core.builder import build_tracks
from ..core.exporter import ExportError, ExportPlaylist, export_xml
from ..core.library import Library, LibraryError, Track, load_library
from ..core.recipe import Recipe
from .filter_panel import FilterPanel
from .track_model import TrackTableModel, TrackTableView, fmt_duration

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
        self.resize(1400, 860)
        self.settings = QSettings()  # organisaatio- ja sovellusnimi asetetaan app.py:ssä
        self.library: Library | None = None
        self.current = Recipe()
        self.queue: list[QueueEntry] = []
        self._unsaved = False

        self._build_ui()
        self._build_menus()
        self._set_enabled(False)

        notation = self.settings.value("key_notation", "both")
        self._set_notation(notation)

        last = self.settings.value("last_library", "")
        if last and Path(last).exists():
            self.open_library(last, quiet=True)

    # ================================================================ UI
    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Horizontal)

        # --- vasen: suodattimet
        self.filters = FilterPanel()
        self.filters.build_requested.connect(self.build_list)
        scroll = QScrollArea()
        scroll.setWidget(self.filters)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(380)
        splitter.addWidget(scroll)

        # --- oikea
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(6, 6, 6, 6)

        top = QHBoxLayout()
        self.name_edit = QLineEdit(self.current.name)
        self.name_edit.setPlaceholderText("Soittolistan nimi")
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Kansio, esim. Keikat/2026 Joulu (valinnainen)")
        top.addWidget(QLabel("Nimi:"))
        top.addWidget(self.name_edit, 2)
        top.addWidget(QLabel("Kansio:"))
        top.addWidget(self.folder_edit, 2)
        rv.addLayout(top)

        self.info = QLabel("Avaa ensin Rekordboxin XML-vienti (Tiedosto > Avaa kirjasto).")
        self.info.setStyleSheet("padding: 2px;")
        rv.addWidget(self.info)

        vsplit = QSplitter(Qt.Vertical)
        self.model = TrackTableModel()
        self.model.changed.connect(self._update_info)
        self.table = TrackTableView()
        self.table.setModel(self.model)
        self.table.remove_requested.connect(self.remove_selected)
        tablebox = QWidget()
        tv = QVBoxLayout(tablebox)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.addWidget(self.table)

        btns = QHBoxLayout()
        self.up_btn = QPushButton("▲ Ylös")
        self.up_btn.setToolTip("Siirrä valitut ylös (Ctrl+↑). Rivejä voi myös raahata hiirellä.")
        self.up_btn.clicked.connect(lambda: self.table.move_selected(-1))
        self.down_btn = QPushButton("▼ Alas")
        self.down_btn.setToolTip("Siirrä valitut alas (Ctrl+↓)")
        self.down_btn.clicked.connect(lambda: self.table.move_selected(1))
        self.remove_btn = QPushButton("Poista valitut")
        self.remove_btn.setToolTip("Poistaa kappaleet listalta ja pitää ne poissa myös reseptissä (Delete)")
        self.remove_btn.clicked.connect(self.remove_selected)
        self.restore_btn = QPushButton("Palauta poistetut")
        self.restore_btn.setToolTip("Tyhjentää käsin poistettujen listan ja luo listan uudelleen")
        self.restore_btn.clicked.connect(self.restore_removed)
        self.add_queue_btn = QPushButton("Lisää vientijonoon ▼")
        self.add_queue_btn.setStyleSheet("font-weight: bold;")
        self.add_queue_btn.clicked.connect(self.add_to_queue)
        for b in (self.up_btn, self.down_btn, self.remove_btn, self.restore_btn):
            btns.addWidget(b)
        btns.addStretch(1)
        btns.addWidget(self.add_queue_btn)
        tv.addLayout(btns)
        vsplit.addWidget(tablebox)

        # --- vientijono
        qbox = QGroupBox("Vientijono (nämä soittolistat tallennetaan samaan XML-tiedostoon)")
        qv = QVBoxLayout(qbox)
        self.queue_tree = QTreeWidget()
        self.queue_tree.setHeaderLabels(["Soittolista / kansio", "Kappaleita", "Kesto"])
        self.queue_tree.setColumnWidth(0, 360)
        self.queue_tree.itemDoubleClicked.connect(self._queue_item_activated)
        qv.addWidget(self.queue_tree)
        qb = QHBoxLayout()
        self.queue_edit_btn = QPushButton("Avaa muokattavaksi")
        self.queue_edit_btn.clicked.connect(lambda: self._queue_item_activated(self.queue_tree.currentItem()))
        self.queue_remove_btn = QPushButton("Poista jonosta")
        self.queue_remove_btn.clicked.connect(self.remove_from_queue)
        self.export_btn = QPushButton("Vie XML-tiedostoksi…")
        self.export_btn.setStyleSheet("font-weight: bold;")
        self.export_btn.clicked.connect(self.export)
        qb.addWidget(self.queue_edit_btn)
        qb.addWidget(self.queue_remove_btn)
        qb.addStretch(1)
        qb.addWidget(self.export_btn)
        qv.addLayout(qb)
        vsplit.addWidget(qbox)
        vsplit.setSizes([560, 220])
        rv.addWidget(vsplit, 1)

        splitter.addWidget(right)
        splitter.setSizes([420, 980])
        self.setCentralWidget(splitter)
        self.statusBar().showMessage("Valmis")

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

        v = mb.addMenu("&Näytä")
        km = v.addMenu("Sävellajimerkintä")
        self.notation_group = QActionGroup(self)
        self.notation_actions = {}
        for key, label in (("both", "Molemmat (8A (Am))"), ("camelot", "Camelot (8A)"), ("classical", "Perinteinen (Am)")):
            a = QAction(label, self, checkable=True)
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

    def _set_enabled(self, on: bool) -> None:
        for w in (
            self.filters, self.table, self.up_btn, self.down_btn, self.remove_btn,
            self.restore_btn, self.add_queue_btn, self.act_reload, self.act_batch,
            self.act_load_recipe,
        ):
            w.setEnabled(on)
        self._update_queue_buttons()

    def _update_queue_buttons(self) -> None:
        has = bool(self.queue) and self.library is not None
        for w in (self.export_btn, self.act_export, self.queue_remove_btn, self.queue_edit_btn, self.act_save_queue):
            w.setEnabled(has)

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
        self.statusBar().showMessage(f"Kirjasto: {lib.path}  ·  {len(lib.tracks)} kappaletta  ·  {ver}")
        if old is not None:
            # kirjasto vaihtui: päivitetään jono resepteistä, jotta kappaleviittaukset ovat ajantasaiset
            self.rebuild_queue()
        self.model.set_tracks([])
        self.info.setText(f"{len(lib.tracks)} kappaletta kirjastossa. Valitse suodattimet ja paina »Luo lista«.")

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
        self.model.set_tracks(tracks)
        if not tracks:
            self.statusBar().showMessage("Yksikään kappale ei täyttänyt ehtoja.", 5000)

    def _update_info(self) -> None:
        tr = self.model.tracks
        if not tr:
            if self.library:
                self.info.setText("Ei kappaleita. Muuta suodattimia ja paina »Luo lista«.")
            return
        total = sum(t.duration for t in tr)
        bpms = [t.bpm for t in tr if t.bpm]
        bpm_txt = f"BPM {min(bpms):.1f}–{max(bpms):.1f}" if bpms else ""
        removed = len(self.current.manual_exclude)
        extra = f"  ·  käsin poistettu {removed}" if removed else ""
        self.info.setText(f"<b>{len(tr)}</b> kappaletta  ·  {fmt_duration(total)}  ·  {bpm_txt}{extra}")

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
        self.queue_tree.clear()
        folders: dict[tuple, QTreeWidgetItem] = {}
        for i, e in enumerate(self.queue):
            parent = self.queue_tree.invisibleRootItem()
            parts = [p for p in e.recipe.folder.split("/") if p.strip()]
            path: tuple = ()
            for p in parts:
                path = path + (p.strip(),)
                if path not in folders:
                    it = QTreeWidgetItem(parent, [f"📁 {p.strip()}"])
                    it.setExpanded(True)
                    folders[path] = it
                parent = folders[path]
            item = QTreeWidgetItem(
                parent,
                [f"♫ {e.recipe.name}", str(len(e.tracks)), fmt_duration(sum(t.duration for t in e.tracks))],
            )
            item.setData(0, Qt.UserRole, i)
        self.queue_tree.expandAll()
        self._update_queue_buttons()

    def _queue_item_activated(self, item: QTreeWidgetItem | None) -> None:
        if item is None:
            return
        idx = item.data(0, Qt.UserRole)
        if idx is None:
            return
        e = self.queue[idx]
        self.current = copy.deepcopy(e.recipe)
        self.name_edit.setText(e.recipe.name)
        self.folder_edit.setText(e.recipe.folder)
        self.filters.set_recipe(e.recipe)
        self.model.set_tracks(e.tracks)
        self.statusBar().showMessage(
            f"Avattiin muokattavaksi: {e.recipe.name}. Lisää jonoon uudelleen tallentaaksesi muutokset.", 6000
        )

    def remove_from_queue(self) -> None:
        item = self.queue_tree.currentItem()
        if item is None:
            return
        idx = item.data(0, Qt.UserRole)
        if idx is None:
            # kansio: poistetaan kaikki sen alla olevat
            ids = []
            stack = [item]
            while stack:
                it = stack.pop()
                if it.data(0, Qt.UserRole) is not None:
                    ids.append(it.data(0, Qt.UserRole))
                stack.extend(it.child(i) for i in range(it.childCount()))
        else:
            ids = [idx]
        self.queue = [e for i, e in enumerate(self.queue) if i not in set(ids)]
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
