"""Käyttöliittymän rakennuspalikat: suodatinpainikkeet, ponnahdusikkunat, kansi ja jonokortit."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from . import theme


# ---------------------------------------------------------------- ponnahdus

class Popover(QFrame):
    """Kelluva paneeli painikkeen alla; sulkeutuu, kun napsautetaan muualle."""

    closed = Signal()

    def __init__(self, title: str, content: QWidget, parent: QWidget | None = None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setObjectName("popup")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)
        head = QLabel(title)
        head.setObjectName("h1")
        head.setStyleSheet("font-size: 15px;")
        lay.addWidget(head)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)
        lay.addWidget(self.scroll)
        self.content = content

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.setBrush(QColor(theme.PANEL_2))
        p.drawRoundedRect(r, 14, 14)
        p.end()

    def open_below(self, anchor: QWidget) -> None:
        self.content.show()
        self.scroll.setWidget(self.content)
        hint = self.content.sizeHint()
        screen = anchor.screen().availableGeometry()
        w = max(hint.width() + 40, 300)
        h = min(hint.height() + 70, int(screen.height() * 0.75))
        self.resize(w, h)
        pos = anchor.mapToGlobal(QPoint(0, anchor.height() + 6))
        pos.setX(max(screen.left() + 8, min(pos.x(), screen.right() - w - 8)))
        if pos.y() + h > screen.bottom():
            pos.setY(max(screen.top() + 8, anchor.mapToGlobal(QPoint(0, 0)).y() - h - 6))
        self.move(pos)
        self.show()

    def hideEvent(self, event):
        super().hideEvent(event)
        # irrotetaan sisältö, jotta sama osio voidaan avata uudelleen
        w = self.scroll.takeWidget()
        if w is not None:
            w.hide()
            w.setParent(self.parentWidget())
            w.hide()
        self.closed.emit()


class FilterChip(QPushButton):
    """Pyöristetty suodatinpainike, joka avaa osion ponnahdusikkunassa."""

    closed = Signal(str)

    def __init__(self, key: str, label: str, title: str, content: QWidget, parent=None):
        super().__init__(parent)
        self.key = key
        self.label = label
        self.title = title
        self.content = content
        self.setObjectName("chip")
        self.setCursor(Qt.PointingHandCursor)
        self.set_summary(None)
        self.clicked.connect(self.open)
        self._popover: Popover | None = None

    def set_summary(self, summary: str | None) -> None:
        self.setText(f"{summary or self.label}  ▾")
        self.setProperty("active", "true" if summary else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.setToolTip(f"{self.title}: {summary}" if summary else self.title)

    def open(self) -> None:
        pop = Popover(self.title, self.content, self.window())
        pop.closed.connect(lambda: self.closed.emit(self.key))
        pop.closed.connect(pop.deleteLater)
        self._popover = pop
        pop.open_below(self)

    def close_popover(self) -> None:
        if self._popover is not None and self._popover.isVisible():
            self._popover.hide()


# ---------------------------------------------------------------- kansi ja hero

class CoverLabel(QWidget):
    def __init__(self, size: int, parent=None):
        super().__init__(parent)
        self._size = size
        self._seed = ""
        self.setFixedSize(size, size)

    def set_seed(self, seed: str) -> None:
        if seed != self._seed:
            self._seed = seed
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.drawPixmap(0, 0, theme.cover_pixmap(self._seed, self._size, radius=14))
        # pieni levysymboli kannen nurkkaan
        r = QRectF(self._size - 46, self._size - 46, 30, 30)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawEllipse(r)
        p.setBrush(QColor(255, 255, 255, 170))
        p.drawEllipse(r.center(), 4, 4)
        p.end()


class HeroPanel(QFrame):
    """Yläosan paneeli, jonka tausta liukuu kannen väristä paneelin väriin."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor(theme.PANEL)
        self.setAttribute(Qt.WA_StyledBackground, False)

    def set_color(self, c: QColor) -> None:
        self._color = c
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, 16, 16)
        p.setClipPath(path)
        p.fillRect(rect, QColor(theme.PANEL))
        g = QLinearGradient(rect.topLeft(), rect.topLeft() + QPoint(0, 460))
        top = QColor(self._color)
        top.setAlpha(120)
        mid = QColor(self._color)
        mid.setAlpha(34)
        g.setColorAt(0.0, top)
        g.setColorAt(0.55, mid)
        g.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(rect, g)
        p.end()


class MagnifierOverlay(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedSize(30, parent.height())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(theme.MUTED), 1.8)
        p.setPen(pen)
        cy = self.height() / 2
        p.drawEllipse(QRectF(14, cy - 7, 11, 11))
        p.drawLine(int(23), int(cy + 2.5), int(27), int(cy + 6.5))
        p.end()


def search_with_icon(edit: QLineEdit) -> QLineEdit:
    edit.setMinimumHeight(40)
    icon = MagnifierOverlay(edit)
    icon.move(0, 0)
    orig_resize = edit.resizeEvent

    def on_resize(ev):
        icon.setFixedHeight(edit.height())
        orig_resize(ev)

    edit.resizeEvent = on_resize
    return edit


# ---------------------------------------------------------------- jonokortit

class QueueCardDelegate(QStyledItemDelegate):
    """Kortti: kansi, lihavoitu nimi ja harmaat lisätiedot."""

    def sizeHint(self, option, index):
        return index.data(Qt.SizeHintRole) or QSize(164, 210)

    def paint(self, p: QPainter, option, index) -> None:
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(option.rect).adjusted(2, 2, -2, -2)
        if option.state & QStyle.State_Selected:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.PANEL_2))
            p.drawRoundedRect(r, 12, 12)
        elif option.state & QStyle.State_MouseOver:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#1a1a1d"))
            p.drawRoundedRect(r, 12, 12)
        px = index.data(Qt.UserRole + 2)
        size = QueueList.CARD
        x = r.left() + (r.width() - size) / 2
        if px is not None:
            p.drawPixmap(int(x), int(r.top() + 6), px)
        y = r.top() + 6 + size + 8
        w = size
        f = theme.sized_font(option.font, 0, bold=True)
        p.setFont(f)
        p.setPen(QColor(theme.TEXT))
        fm = QFontMetrics(f)
        p.drawText(QRectF(x, y, w, fm.height()), Qt.AlignLeft, fm.elidedText(index.data(Qt.DisplayRole), Qt.ElideRight, w))
        y += fm.height() + 2
        f2 = theme.sized_font(option.font, -1)
        p.setFont(f2)
        p.setPen(QColor(theme.MUTED))
        fm2 = QFontMetrics(f2)
        for line in (index.data(Qt.UserRole + 1) or "").split("\n"):
            p.drawText(QRectF(x, y, w, fm2.height()), Qt.AlignLeft, fm2.elidedText(line, Qt.ElideRight, w))
            y += fm2.height()
        p.restore()


class QueueList(QListWidget):
    """Vientijonon soittolistat kortteina (kansi, nimi, kansio ja kappalemäärä)."""

    CARD = 150

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("queue")
        self.setViewMode(QListWidget.IconMode)
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static)
        self.setIconSize(QSize(self.CARD, self.CARD))
        self.setGridSize(QSize(self.CARD + 20, self.CARD + 66))
        self.setSpacing(4)
        self.setWordWrap(True)
        self.setUniformItemSizes(True)
        self.setItemDelegate(QueueCardDelegate(self))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSelectionMode(QListWidget.SingleSelection)
        f = QFont(self.font())
        self.setFont(f)

    def add_card(self, title: str, subtitle: str, seed: str, data) -> QListWidgetItem:
        it = QListWidgetItem(title)
        it.setData(Qt.UserRole, data)
        it.setData(Qt.UserRole + 1, subtitle)
        it.setData(Qt.UserRole + 2, theme.cover_pixmap(seed, self.CARD, radius=12))
        it.setSizeHint(QSize(self.CARD + 14, self.CARD + 60))
        it.setToolTip(f"{title}\n{subtitle}\nKaksoisnapsauta avataksesi muokattavaksi")
        self.addItem(it)
        return it


def pill_button(text: str, kind: str = "", tooltip: str = "") -> QPushButton:
    b = QPushButton(text)
    if kind:
        b.setObjectName(kind)
    b.setCursor(Qt.PointingHandCursor)
    if tooltip:
        b.setToolTip(tooltip)
    return b


def label(text: str, kind: str = "") -> QLabel:
    lab = QLabel(text)
    if kind:
        lab.setObjectName(kind)
    return lab
