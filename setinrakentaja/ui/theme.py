"""Tumma teema: värit, Qt-paletti, tyylitiedosto ja generoidut gradienttikannet."""

from __future__ import annotations

import hashlib

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPalette,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication

BG = "#0b0b0c"
PANEL = "#151517"
PANEL_2 = "#1d1d20"
CHIP = "#27272b"
CHIP_HOVER = "#323237"
BORDER = "#2a2a2e"
TEXT = "#f4f4f5"
MUTED = "#9b9ba1"
FAINT = "#6b6b72"
ACCENT = "#ff6a3d"
GOOD = "#4cc38a"
WARN = "#e5b445"
BAD = "#ef5a5a"


# ---------------------------------------------------------------- värit

def camelot_color(code: str | None) -> QColor:
    """Camelot-pyörän väri: numero määrää sävyn, A tummempi ja B vaaleampi."""
    if not code:
        return QColor(CHIP)
    n, letter = int(code[:-1]), code[-1]
    hue = int(((n - 1) * 30 + 160) % 360)
    c = QColor()
    if letter == "A":
        c.setHsl(hue, 150, 150)
    else:
        c.setHsl(hue, 170, 185)
    return c


def _seed_hues(seed: str) -> tuple[int, int, int]:
    h = hashlib.md5(seed.encode("utf-8")).digest()
    base = h[0] * 360 // 256
    spread = 25 + h[1] % 50
    return base, (base + spread) % 360, (base - spread // 2) % 360


def cover_pixmap(seed: str, size: int, radius: float = 10, dpr: float = 2.0, base: QColor | None = None) -> QPixmap:
    """Pehmeä gradienttikansi, joka on aina sama samalle nimelle."""
    px = QPixmap(int(size * dpr), int(size * dpr))
    px.setDevicePixelRatio(dpr)
    px.fill(Qt.transparent)
    h1, h2, h3 = _seed_hues(seed or "?")
    if base is not None and base.isValid():
        h1 = max(0, base.hslHue())
        h2, h3 = (h1 + 35) % 360, (h1 - 20) % 360
    c1 = QColor.fromHsl(h1, 220, 120)
    c2 = QColor.fromHsl(h2, 230, 165)
    c3 = QColor.fromHsl(h3, 140, 205)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    p.setClipPath(path)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0.0, c1)
    g.setColorAt(0.55, c2)
    g.setColorAt(1.0, c3)
    p.fillRect(QRectF(0, 0, size, size), g)
    r = QRadialGradient(QPointF(size * 0.75, size * 0.25), size * 0.7)
    r.setColorAt(0.0, QColor(255, 255, 255, 120))
    r.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.fillRect(QRectF(0, 0, size, size), r)
    p.end()
    return px


def cover_color(seed: str) -> QColor:
    h1, _, _ = _seed_hues(seed or "?")
    return QColor.fromHsl(h1, 200, 110)


# ---------------------------------------------------------------- sovellus

QSS = f"""
* {{ outline: none; }}
QMainWindow, QWidget#root {{ background: {BG}; }}
QWidget {{ color: {TEXT}; font-size: 13px; }}
QToolTip {{ background: {PANEL_2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px; border-radius: 6px; }}

QFrame#panel {{ background: {PANEL}; border-radius: 16px; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#faint {{ color: {FAINT}; font-size: 12px; }}
QLabel#h1 {{ font-size: 18px; font-weight: 700; }}
QLabel#eyebrow {{ color: {MUTED}; font-size: 12px; }}
QLabel#logo {{ font-size: 15px; font-weight: 700; }}

QLineEdit#title {{
    background: transparent; border: none; font-size: 30px; font-weight: 800; padding: 0; color: {TEXT};
}}
QLineEdit#title:focus {{ background: rgba(255,255,255,0.06); border-radius: 8px; }}
QLineEdit#folder {{
    background: transparent; border: none; color: {MUTED}; font-size: 13px; padding: 0;
}}
QLineEdit#folder:focus {{ background: rgba(255,255,255,0.06); border-radius: 6px; color: {TEXT}; }}
QLineEdit#search {{
    background: {PANEL_2}; border: 1px solid {BORDER}; border-radius: 20px; padding: 8px 16px 8px 36px;
    font-size: 14px;
}}
QLineEdit#search:focus {{ border-color: #4a4a50; }}

QPushButton {{
    background: {CHIP}; border: none; border-radius: 15px; padding: 6px 16px; font-weight: 600; min-height: 18px;
}}
QPushButton::menu-indicator {{ image: none; width: 0; }}
QPushButton:hover {{ background: {CHIP_HOVER}; }}
QPushButton:pressed {{ background: #3b3b41; }}
QPushButton:disabled {{ color: {FAINT}; background: #1c1c1f; }}
QPushButton#primary {{ background: #ffffff; color: #0b0b0c; padding: 7px 22px; border-radius: 17px; font-size: 14px; min-height: 20px; }}
QPushButton#primary:hover {{ background: #e9e9ec; }}
QPushButton#primary:disabled {{ background: #3a3a3e; color: #7a7a80; }}
QPushButton#ghost {{ background: transparent; color: {MUTED}; padding: 6px 10px; }}
QPushButton#ghost:hover {{ color: {TEXT}; background: {CHIP}; }}
QPushButton#icon {{ background: rgba(255,255,255,0.10); border-radius: 17px; padding: 0; min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px; font-size: 15px; }}
QPushButton#icon:hover {{ background: rgba(255,255,255,0.16); }}
QPushButton#chip {{ background: {CHIP}; border-radius: 15px; padding: 6px 14px; font-weight: 600; min-height: 18px; }}
QPushButton#chip:hover {{ background: {CHIP_HOVER}; }}
QPushButton#chip[active="true"] {{ background: #f4f4f5; color: #0b0b0c; }}
QPushButton#tab {{ background: {CHIP}; border-radius: 15px; padding: 6px 12px; }}
QPushButton#tab:checked {{ background: #f4f4f5; color: #0b0b0c; }}

QFrame#popup QGroupBox {{ border: none; margin: 0; padding: 0; font-weight: 700; }}
QFrame#popup QGroupBox::title {{ color: transparent; height: 0; }}

QGroupBox {{ border: 1px solid {BORDER}; border-radius: 12px; margin-top: 14px; padding: 10px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; color: {MUTED}; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {{
    background: {CHIP}; border: 1px solid transparent; border-radius: 8px; padding: 5px 8px; min-height: 18px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus {{ border-color: #55555c; }}
QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::down-button,
QDateEdit::up-button, QDateEdit::down-button {{ width: 0; border: none; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {PANEL_2}; border: 1px solid {BORDER}; selection-background-color: {CHIP_HOVER}; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; background: {CHIP}; border: 1px solid #44444a; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QToolButton {{ background: {CHIP}; border: none; border-radius: 8px; padding: 4px; font-size: 11px; }}
QToolButton:hover {{ background: {CHIP_HOVER}; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 6px 12px; border-radius: 12px; margin-right: 4px; }}
QTabBar::tab:selected {{ background: {CHIP}; color: {TEXT}; }}

QListWidget {{ background: {CHIP}; border: none; border-radius: 8px; padding: 4px; }}
QListWidget::item {{ padding: 3px 4px; border-radius: 6px; }}
QListWidget::item:hover {{ background: {CHIP_HOVER}; }}
QListWidget#queue {{ background: transparent; padding: 0; }}
QListWidget#queue::item {{ padding: 6px; border-radius: 12px; }}
QListWidget#queue::item:selected {{ background: {PANEL_2}; }}
QListWidget#queue::item:hover {{ background: #1a1a1d; }}

QTableView {{
    background: transparent; border: none; gridline-color: transparent;
    selection-background-color: #2a2a2f; selection-color: {TEXT}; alternate-background-color: transparent;
}}
QTableView::item {{ border: none; padding-left: 6px; }}
QTableView::item:hover {{ background: #1b1b1e; }}
QTableView::item:selected {{ background: #2a2a2f; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: transparent; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
    padding: 6px 6px; font-size: 12px;
}}
QHeaderView::section:hover {{ color: {TEXT}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #3a3a40; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #3a3a40; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

QMenu {{ background: {PANEL_2}; border: 1px solid {BORDER}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {CHIP_HOVER}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}
QMenuBar {{ background: {BG}; }}
QMenuBar::item:selected {{ background: {CHIP}; border-radius: 6px; }}

QStatusBar {{ background: {BG}; color: {MUTED}; }}
QStatusBar::item {{ border: none; }}
QSplitter::handle {{ background: transparent; }}
QMessageBox, QDialog {{ background: {PANEL}; }}
QCalendarWidget QWidget {{ alternate-background-color: {PANEL_2}; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    roles = {
        QPalette.Window: BG,
        QPalette.WindowText: TEXT,
        QPalette.Base: PANEL_2,
        QPalette.AlternateBase: PANEL,
        QPalette.ToolTipBase: PANEL_2,
        QPalette.ToolTipText: TEXT,
        QPalette.Text: TEXT,
        QPalette.Button: CHIP,
        QPalette.ButtonText: TEXT,
        QPalette.BrightText: "#ffffff",
        QPalette.Highlight: "#3a3a40",
        QPalette.HighlightedText: TEXT,
        QPalette.PlaceholderText: FAINT,
        QPalette.Mid: MUTED,
    }
    for role, col in roles.items():
        pal.setColor(role, QColor(col))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor(FAINT))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(FAINT))
    app.setPalette(pal)
    app.setStyleSheet(QSS)


def sized_font(font, delta_px: float = 0, bold: bool | None = None):
    """Kopio fontista kokoa muutettuna (toimii sekä pikseli- että pistekoolla)."""
    from PySide6.QtGui import QFont

    f = QFont(font)
    if f.pixelSize() > 0:
        f.setPixelSize(max(9, round(f.pixelSize() + delta_px)))
    elif f.pointSizeF() > 0:
        f.setPointSizeF(max(7.0, f.pointSizeF() + delta_px * 0.75))
    if bold is not None:
        f.setBold(bold)
    return f
