"""Esikatselutaulukon malli, piirtäjät (delegaatit) ja näkymä (raahaus, siirto, poisto)."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QItemSelectionModel, QModelIndex, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QKeySequence, QLinearGradient, QPainter, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QStyle, QStyledItemDelegate, QTableView

from ..core.keys import camelot_sort_key, format_key
from ..core.library import Track
from ..core.sequencing import bpm_bounds, energy_of, transition_quality
from . import theme

COLOUR_QT = {
    "Pinkki": "#FF007F", "Punainen": "#FF0000", "Oranssi": "#FFA500", "Keltainen": "#FFFF00",
    "Vihreä": "#00FF00", "Turkoosi": "#25FDE9", "Sininen": "#0000FF", "Violetti": "#660099",
}

ArtistRole = Qt.UserRole + 1
TagsRole = Qt.UserRole + 2
CoverRole = Qt.UserRole + 3
EnergyRole = Qt.UserRole + 4
CamelotRole = Qt.UserRole + 5


def fmt_duration(sec: int) -> str:
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def track_tags(t: Track) -> list[str]:
    tags = [t.genre] if t.genre else []
    tags += [x for x in t.mytags if x.lower() != t.genre.lower()]
    return tags


COLUMNS = [
    ("#", None),
    ("Kappale", lambda t: (t.name.lower(), t.artist.lower())),
    ("Tagit", lambda t: t.genre.lower()),
    ("Siirtymä", None),
    ("BPM", lambda t: t.bpm),
    ("Sävellaji", lambda t: camelot_sort_key(t.camelot)),
    ("Energia", None),  # lasketaan erikseen
    ("Arvio", lambda t: t.rating),
    ("Lisätty", lambda t: str(t.date_added or "")),
    ("Kesto", lambda t: t.duration),
]
COL_TITLE, COL_TAGS, COL_TRANS, COL_BPM, COL_KEY, COL_ENERGY, COL_RATING, COL_ADDED, COL_TIME = range(1, 10)


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
        if orientation != Qt.Horizontal:
            return None
        if role == Qt.DisplayRole:
            return COLUMNS[section][0]
        if role == Qt.TextAlignmentRole and section in (0, COL_BPM, COL_TIME):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role == Qt.ToolTipRole:
            if section == COL_TRANS:
                return "Siirtymä edellisestä kappaleesta: ✓ yhteensopiva, ~ kohtuullinen, ✗ riitasointu, BPM-muutos"
            if section == COL_ENERGY:
                return "Energia 1–10: kommentin merkintä (Energy 7 / E7, merkitty *) tai arvio BPM:stä ja tähdistä"
            if section == COL_TAGS:
                return "Genre ja My Tagit"
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
            if c == COL_TITLE:
                return t.name
            if c == COL_TAGS:
                return ", ".join(track_tags(t))
            if c == COL_TRANS:
                return transition_quality(self.tracks[r - 1] if r > 0 else None, t)
            if c == COL_BPM:
                return f"{t.bpm:.1f}" if t.bpm else ""
            if c == COL_KEY:
                return format_key(t.camelot, self.key_notation) if t.camelot else t.key_raw
            if c == COL_ENERGY:
                e = self._energy.get(id(t))
                return f"{e:.1f}" + ("*" if t.energy_tag is not None else "") if e is not None else ""
            if c == COL_RATING:
                return "★" * t.rating
            if c == COL_ADDED:
                d = t.date_added
                return f"{d.day}.{d.month}.{d.year}" if d else ""
            if c == COL_TIME:
                return fmt_duration(t.duration)
        elif role == ArtistRole:
            return t.artist
        elif role == TagsRole:
            return track_tags(t)
        elif role == CoverRole:
            return (f"{t.artist}|{t.album or t.name}", COLOUR_QT.get(t.colour))
        elif role == EnergyRole:
            return self._energy.get(id(t))
        elif role == CamelotRole:
            return t.camelot
        elif role == Qt.ForegroundRole:
            if c == COL_TRANS:
                txt = transition_quality(self.tracks[r - 1] if r > 0 else None, t)
                if txt.startswith("✗"):
                    return QColor(theme.BAD)
                if txt.startswith("✓"):
                    return QColor(theme.GOOD)
                if txt.startswith("~"):
                    return QColor(theme.WARN)
                return QColor(theme.MUTED)
            if c in (0, COL_ADDED, COL_TIME, COL_RATING):
                return QColor(theme.MUTED)
        elif role == Qt.TextAlignmentRole:
            if c in (0, COL_BPM, COL_TIME):
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        elif role == Qt.ToolTipRole:
            tip = f"{t.artist} – {t.name}\n{t.file_path}"
            if t.comment:
                tip += f"\nKommentti: {t.comment}"
            if t.mytags:
                tip += f"\nMy Tag: {', '.join(t.mytags)}"
            tip += f"\nToistokerrat: {t.play_count}"
            if t.colour:
                tip += f"\nVäri: {t.colour}"
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
        self._recalc()
        self.endResetModel()
        self.changed.emit()


# ==================================================================== delegaatit

class _BaseDelegate(QStyledItemDelegate):
    def paint_background(self, p: QPainter, option, index) -> None:
        opt = option.__class__(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        opt.icon = opt.icon.__class__()
        style = opt.widget.style() if opt.widget else None
        if style:
            style.drawControl(QStyle.CE_ItemViewItem, opt, p, opt.widget)


class TitleDelegate(_BaseDelegate):
    """Pieni gradienttikansi + kappaleen nimi lihavoituna + artisti harmaana."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache: dict[tuple, object] = {}

    def paint(self, p: QPainter, option, index) -> None:
        self.paint_background(p, option, index)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        rect = option.rect
        size = min(40, rect.height() - 10)
        seed, colour = index.data(CoverRole)
        key = (seed, colour, size)
        px = self._cache.get(key)
        if px is None:
            base = QColor(colour) if colour else None
            px = theme.cover_pixmap(seed, size, radius=6, base=base)
            if len(self._cache) > 3000:
                self._cache.clear()
            self._cache[key] = px
        y = rect.top() + (rect.height() - size) // 2
        p.drawPixmap(rect.left() + 8, y, px)
        x = rect.left() + 8 + size + 12
        w = rect.right() - x - 6
        f = theme.sized_font(option.font, 0.5, bold=True)
        p.setFont(f)
        fm = QFontMetrics(f)
        p.setPen(QColor(theme.TEXT))
        name = fm.elidedText(index.data(Qt.DisplayRole) or "", Qt.ElideRight, w)
        p.drawText(QRectF(x, rect.top() + 6, w, rect.height() / 2 - 4), Qt.AlignLeft | Qt.AlignBottom, name)
        f2 = theme.sized_font(option.font, -0.5)
        p.setFont(f2)
        p.setPen(QColor(theme.MUTED))
        artist = QFontMetrics(f2).elidedText(index.data(ArtistRole) or "", Qt.ElideRight, w)
        p.drawText(QRectF(x, rect.center().y() + 2, w, rect.height() / 2 - 6), Qt.AlignLeft | Qt.AlignTop, artist)
        p.restore()


def _draw_chip(p: QPainter, x: float, cy: float, text: str, font: QFont, bg: QColor, fg: QColor, max_w: float) -> float:
    fm = QFontMetrics(font)
    full = fm.horizontalAdvance(text) + 2
    if full + 20 > max_w:
        if max_w - 20 < 16:
            return 0
        text = fm.elidedText(text, Qt.ElideRight, int(max_w - 20))
        full = fm.horizontalAdvance(text) + 2
    w = full + 20
    h = fm.height() + 8
    r = QRectF(x, cy - h / 2, w, h)
    p.setPen(Qt.NoPen)
    p.setBrush(bg)
    p.drawRoundedRect(r, h / 2, h / 2)
    p.setPen(fg)
    p.drawText(r, Qt.AlignCenter | Qt.TextDontClip, text)
    return w


class TagsDelegate(_BaseDelegate):
    """Genre ja My Tagit pyöristettyinä "pilleinä", ylimääräiset "+N"."""

    def paint(self, p: QPainter, option, index) -> None:
        self.paint_background(p, option, index)
        tags: list[str] = index.data(TagsRole) or []
        if not tags:
            return
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        f = theme.sized_font(option.font, -1.5)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        rect = option.rect
        x = rect.left() + 6
        cy = rect.center().y()
        bg = QColor(theme.CHIP)
        fg = QColor("#d9d9de")
        fm = QFontMetrics(f)
        chip_w = lambda text: fm.horizontalAdvance(text) + 22  # noqa: E731
        right = rect.right() - 4
        shown = 0
        for i, tag in enumerate(tags):
            rest_after = len(tags) - i - 1
            reserve = chip_w(f"+{rest_after}") + 6 if rest_after else 0
            if x + chip_w(tag) + reserve > right and shown > 0:
                break
            x += _draw_chip(p, x, cy, tag, f, bg, fg, right - x - reserve) + 6
            shown += 1
        hidden = len(tags) - shown
        if hidden > 0:
            _draw_chip(p, x, cy, f"+{hidden}", f, bg, fg, right - x)
        p.restore()


class KeyDelegate(_BaseDelegate):
    """Sävellaji Camelot-pyörän värisenä pillinä."""

    def paint(self, p: QPainter, option, index) -> None:
        self.paint_background(p, option, index)
        text = index.data(Qt.DisplayRole) or ""
        if not text:
            return
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        f = theme.sized_font(option.font, -1, bold=True)
        p.setFont(f)
        code = index.data(CamelotRole)
        bg = theme.camelot_color(code) if code else QColor(theme.CHIP)
        fg = QColor("#0b0b0c") if code else QColor(theme.MUTED)
        _draw_chip(p, option.rect.left() + 6, option.rect.center().y(), text, f, bg, fg, option.rect.width() - 10)
        p.restore()


class EnergyDelegate(_BaseDelegate):
    """Energia lyhyenä liukuväripalkkina ja numerona."""

    def paint(self, p: QPainter, option, index) -> None:
        self.paint_background(p, option, index)
        e = index.data(EnergyRole)
        if e is None:
            return
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        rect = option.rect
        bar_w = max(20, rect.width() - 48)
        x = rect.left() + 8
        cy = rect.center().y()
        track = QRectF(x, cy - 3, bar_w, 6)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.CHIP))
        p.drawRoundedRect(track, 3, 3)
        g = QLinearGradient(track.topLeft(), track.topRight())
        g.setColorAt(0, QColor("#ffb347"))
        g.setColorAt(1, QColor("#ff3d7f"))
        fill = QRectF(track)
        fill.setWidth(bar_w * max(0.05, min(1.0, e / 10)))
        p.setBrush(g)
        p.drawRoundedRect(fill, 3, 3)
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(x + bar_w + 6, rect.top(), 34, rect.height()), Qt.AlignLeft | Qt.AlignVCenter,
                   index.data(Qt.DisplayRole) or "")
        p.restore()


# ==================================================================== näkymä

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
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setMouseTracking(True)
        self.setFrameShape(QTableView.NoFrame)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(54)
        h = self.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setHighlightSections(False)
        h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        h.setSectionsClickable(True)
        h.sectionClicked.connect(self._header_clicked)
        self._delegates = {
            COL_TITLE: TitleDelegate(self),
            COL_TAGS: TagsDelegate(self),
            COL_KEY: KeyDelegate(self),
            COL_ENERGY: EnergyDelegate(self),
        }
        for col, d in self._delegates.items():
            self.setItemDelegateForColumn(col, d)
        QShortcut(QKeySequence.Delete, self, activated=self.remove_requested.emit)
        QShortcut(QKeySequence(Qt.Key_Backspace), self, activated=self.remove_requested.emit)
        QShortcut(QKeySequence("Ctrl+Up"), self, activated=lambda: self.move_selected(-1))
        QShortcut(QKeySequence("Ctrl+Down"), self, activated=lambda: self.move_selected(1))

    def setModel(self, model):
        super().setModel(model)
        widths = [40, 300, 240, 78, 58, 112, 92, 84, 90, 58]
        for i, w in enumerate(widths):
            self.setColumnWidth(i, w)
        h = self.horizontalHeader()
        h.setSectionResizeMode(COL_TITLE, QHeaderView.Stretch)

    def sizeHint(self) -> QSize:
        return QSize(900, 500)

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
