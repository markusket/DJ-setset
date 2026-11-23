"""Esikatselutaulukon malli ja näkymä (raahaus, siirto, poisto)."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QItemSelectionModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView

from ..core.keys import camelot_sort_key, format_key
from ..core.library import Track
from ..core.sequencing import bpm_bounds, energy_of, transition_quality

COLOUR_QT = {
    "Pinkki": "#FF007F", "Punainen": "#FF0000", "Oranssi": "#FFA500", "Keltainen": "#FFFF00",
    "Vihreä": "#00FF00", "Turkoosi": "#25FDE9", "Sininen": "#0000FF", "Violetti": "#660099",
}


def fmt_duration(sec: int) -> str:
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


COLUMNS = [
    ("#", None),
    ("Siirtymä", None),
    ("Nimi", lambda t: t.name.lower()),
    ("Artisti", lambda t: t.artist.lower()),
    ("BPM", lambda t: t.bpm),
    ("Sävellaji", lambda t: camelot_sort_key(t.camelot)),
    ("Genre", lambda t: t.genre.lower()),
    ("Kesto", lambda t: t.duration),
    ("Arvio", lambda t: t.rating),
    ("Energia", None),  # lasketaan erikseen
    ("Lisätty", lambda t: str(t.date_added or "")),
    ("Toistot", lambda t: t.play_count),
    ("Väri", lambda t: t.colour),
]
COL_ENERGY = 9


class TrackTableModel(QAbstractTableModel):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tracks: list[Track] = []
        self.key_notation = "both"
        self._energy: dict[int, float] = {}
        self._sort_state: tuple[int, bool] | None = None

    # ---------------------------------------------------------------- data
    def set_tracks(self, tracks: list[Track]) -> None:
        self.beginResetModel()
        self.tracks = list(tracks)
        self._recalc()
        self.endResetModel()
        self.changed.emit()

    def _recalc(self) -> None:
        lo, hi = bpm_bounds(self.tracks)
        self._energy = {id(t): energy_of(t, lo, hi) for t in self.tracks}

    def _touch(self) -> None:
        self._recalc()
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, len(COLUMNS) - 1))
        self.changed.emit()

    def set_key_notation(self, notation: str) -> None:
        self.key_notation = notation
        self._touch()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.tracks)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section][0]
        if role == Qt.ToolTipRole and orientation == Qt.Horizontal:
            if section == 1:
                return "Siirtymä edellisestä kappaleesta: ✓ yhteensopiva, ~ kohtuullinen, ✗ riitasointu, BPM-muutos"
            if section == COL_ENERGY:
                return "Energia 1–10: kommentin merkintä (Energy 7 / E7) tai arvio BPM:stä ja tähdistä"
            return "Klikkaa järjestääksesi listan tämän sarakkeen mukaan"
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r, c = index.row(), index.column()
        t = self.tracks[r]
        if role == Qt.DisplayRole:
            if c == 0:
                return r + 1
            if c == 1:
                return transition_quality(self.tracks[r - 1] if r > 0 else None, t)
            if c == 2:
                return t.name
            if c == 3:
                return t.artist
            if c == 4:
                return f"{t.bpm:.1f}" if t.bpm else ""
            if c == 5:
                return format_key(t.camelot, self.key_notation) if t.camelot else t.key_raw
            if c == 6:
                return t.genre
            if c == 7:
                return fmt_duration(t.duration)
            if c == 8:
                return "★" * t.rating
            if c == COL_ENERGY:
                e = self._energy.get(id(t))
                return f"{e:.1f}" + ("*" if t.energy_tag is not None else "") if e is not None else ""
            if c == 10:
                return t.date_added.isoformat() if t.date_added else ""
            if c == 11:
                return t.play_count
            if c == 12:
                return t.colour
        elif role == Qt.DecorationRole and c == 12 and t.colour:
            return QColor(COLOUR_QT.get(t.colour, "#888"))
        elif role == Qt.ForegroundRole and c == 1:
            txt = transition_quality(self.tracks[r - 1] if r > 0 else None, t)
            if txt.startswith("✗"):
                return QColor("#d9534f")
            if txt.startswith("✓"):
                return QColor("#3c9a5f")
        elif role == Qt.TextAlignmentRole and c in (0, 4, 7, 9, 11):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        elif role == Qt.ToolTipRole:
            tip = f"{t.artist} – {t.name}\n{t.file_path}"
            if t.comment:
                tip += f"\nKommentti: {t.comment}"
            if t.mytags:
                tip += f"\nMy Tag: {', '.join(t.mytags)}"
            return tip
        return None

    # ---------------------------------------------------------------- muokkaus
    def flags(self, index):
        base = Qt.ItemIsDropEnabled
        if not index.isValid():
            return base
        return base | Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled

    def supportedDropActions(self):
        return Qt.MoveAction | Qt.CopyAction

    def supportedDragActions(self):
        return Qt.MoveAction | Qt.CopyAction

    def move_rows(self, rows: list[int], target: int) -> list[int]:
        """Siirtää rivit kohtaan target (ennen riviä target). Palauttaa uudet rivinumerot."""
        rows = sorted(set(r for r in rows if 0 <= r < len(self.tracks)))
        if not rows:
            return []
        moving = [self.tracks[r] for r in rows]
        before = sum(1 for r in rows if r < target)
        rest = [t for i, t in enumerate(self.tracks) if i not in set(rows)]
        target = max(0, min(len(rest), target - before))
        self.beginResetModel()
        self.tracks = rest[:target] + moving + rest[target:]
        self._recalc()
        self.endResetModel()
        self.changed.emit()
        return list(range(target, target + len(moving)))

    def remove_rows(self, rows: list[int]) -> list[Track]:
        rows = sorted(set(rows), reverse=True)
        removed = []
        for r in rows:
            self.beginRemoveRows(QModelIndex(), r, r)
            removed.append(self.tracks.pop(r))
            self.endRemoveRows()
        self._touch()
        return removed

    def sort_by_column(self, col: int) -> None:
        key = COLUMNS[col][1]
        if col == COL_ENERGY:
            key = lambda t: self._energy.get(id(t), 0)  # noqa: E731
        if key is None:
            return
        desc = bool(self._sort_state and self._sort_state[0] == col and not self._sort_state[1])
        self._sort_state = (col, desc)
        self.beginResetModel()
        self.tracks.sort(key=key, reverse=desc)
        self.endResetModel()
        self.changed.emit()


class TrackTableView(QTableView):
    """Taulukko, jossa rivejä voi raahata uuteen järjestykseen ja poistaa Delete-näppäimellä."""

    remove_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropOverwriteMode(False)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(22)
        h = self.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(False)
        h.setSectionsClickable(True)
        h.sectionClicked.connect(self._header_clicked)
        QShortcut(QKeySequence.Delete, self, activated=self.remove_requested.emit)
        QShortcut(QKeySequence(Qt.Key_Backspace), self, activated=self.remove_requested.emit)
        QShortcut(QKeySequence("Ctrl+Up"), self, activated=lambda: self.move_selected(-1))
        QShortcut(QKeySequence("Ctrl+Down"), self, activated=lambda: self.move_selected(1))

    def setModel(self, model):
        super().setModel(model)
        widths = [36, 80, 240, 170, 56, 90, 110, 56, 70, 60, 86, 56, 80]
        for i, w in enumerate(widths):
            self.setColumnWidth(i, w)

    def _header_clicked(self, col: int) -> None:
        self.model().sort_by_column(col)

    def selected_rows(self) -> list[int]:
        return sorted({i.row() for i in self.selectionModel().selectedRows()})

    def _select_rows(self, rows: list[int]) -> None:
        sm = self.selectionModel()
        sm.clearSelection()
        m = self.model()
        for r in rows:
            sm.select(
                m.index(r, 0),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
            )
        if rows:
            self.scrollTo(m.index(rows[0], 0))

    def move_selected(self, step: int) -> None:
        rows = self.selected_rows()
        if not rows:
            return
        m: TrackTableModel = self.model()
        if step < 0:
            target = max(0, rows[0] + step)
        else:
            target = min(m.rowCount(), rows[-1] + 1 + step)
        new = m.move_rows(rows, target)
        self._select_rows(new)

    def dropEvent(self, event):
        if event.source() is not self:
            return super().dropEvent(event)
        rows = self.selected_rows()
        pos = event.position().toPoint()
        idx = self.indexAt(pos)
        m: TrackTableModel = self.model()
        if idx.isValid():
            target = idx.row()
            rect = self.visualRect(idx)
            if pos.y() > rect.center().y():
                target += 1
        else:
            target = m.rowCount()
        new = m.move_rows(rows, target)
        # CopyAction estää Qt:ta poistamasta "siirrettyjä" rivejä uudelleen
        event.setDropAction(Qt.CopyAction)
        event.accept()
        self._select_rows(new)
