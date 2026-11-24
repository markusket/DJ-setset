"""Vasemman reunan suodatinpaneeli. Muuntaa kentät Recipe-olioksi ja takaisin."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core.keys import camelot_to_classical, to_camelot
from ..core.library import COLOUR_NAMES, Library
from ..core.recipe import SORT_MODES, Recipe
from .theme import camelot_color


# ---------------------------------------------------------------- apuwidgetit

def opt_spin(minimum: int, maximum: int, suffix: str = "", none_text: str = "—") -> QSpinBox:
    """Kokonaislukukenttä, jonka pienin arvo tarkoittaa "ei rajausta"."""
    s = QSpinBox()
    s.setRange(minimum, maximum)
    s.setSpecialValueText(none_text)
    s.setSuffix(suffix)
    s.setValue(minimum)
    s.setAccelerated(True)
    return s


def opt_dspin(minimum: float, maximum: float, decimals: int = 1, suffix: str = "") -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(minimum, maximum)
    s.setDecimals(decimals)
    s.setSpecialValueText("—")
    s.setSuffix(suffix)
    s.setValue(minimum)
    s.setAccelerated(True)
    return s


def spin_value(s):
    v = s.value()
    return None if v == s.minimum() else v


def set_spin(s, v):
    s.setValue(s.minimum() if v is None else v)


class CheckList(QWidget):
    """Hakukentällinen valintalista (rastit)."""

    changed = Signal()

    def __init__(self, placeholder: str = "Suodata listaa…", height: int = 120):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.search = QLineEdit()
        self.search.setPlaceholderText(placeholder)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        self.list = QListWidget()
        self.list.setFixedHeight(height)
        self.list.itemChanged.connect(lambda *_: self.changed.emit())
        lay.addWidget(self.search)
        lay.addWidget(self.list)

    def set_items(self, items: dict[str, int] | list[str]) -> None:
        checked = set(self.checked())
        self.list.blockSignals(True)
        self.list.clear()
        entries = items.items() if isinstance(items, dict) else ((i, None) for i in items)
        for name, count in entries:
            it = QListWidgetItem(f"{name}  ({count})" if count is not None else name)
            it.setData(Qt.UserRole, name)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if name in checked else Qt.Unchecked)
            self.list.addItem(it)
        self.list.blockSignals(False)
        self._filter(self.search.text())

    def _filter(self, text: str) -> None:
        t = text.lower().strip()
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(t) and t not in it.text().lower())

    def checked(self) -> list[str]:
        return [
            self.list.item(i).data(Qt.UserRole)
            for i in range(self.list.count())
            if self.list.item(i).checkState() == Qt.Checked
        ]

    def set_checked(self, names: list[str]) -> None:
        wanted = {n.lower() for n in names}
        present = set()
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            it = self.list.item(i)
            name = it.data(Qt.UserRole)
            on = name.lower() in wanted
            if on:
                present.add(name.lower())
            it.setCheckState(Qt.Checked if on else Qt.Unchecked)
        # reseptissä voi olla arvoja, joita nykyisessä kirjastossa ei ole: lisätään ne
        for n in names:
            if n.lower() not in present:
                it = QListWidgetItem(f"{n}  (0)")
                it.setData(Qt.UserRole, n)
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Checked)
                self.list.addItem(it)
        self.list.blockSignals(False)


class IncludeExclude(QTabWidget):
    """Kaksi välilehteä: Sisällytä / Poissulje."""

    def __init__(self, placeholder: str, height: int = 120):
        super().__init__()
        self.include = CheckList(placeholder, height)
        self.exclude = CheckList(placeholder, height)
        self.addTab(self.include, "Sisällytä")
        self.addTab(self.exclude, "Poissulje")

    def set_items(self, items) -> None:
        self.include.set_items(items)
        self.exclude.set_items(items)


class DateField(QWidget):
    def __init__(self, label: str):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.check = QCheckBox(label)
        self.edit = QDateEdit()
        self.edit.setCalendarPopup(True)
        self.edit.setDisplayFormat("d.M.yyyy")
        self.edit.setDate(QDate.currentDate())
        self.edit.setEnabled(False)
        self.check.toggled.connect(self.edit.setEnabled)
        lay.addWidget(self.check)
        lay.addWidget(self.edit, 1)

    def value(self) -> str | None:
        if not self.check.isChecked():
            return None
        return self.edit.date().toPython().isoformat()

    def set_value(self, v: str | None) -> None:
        self.check.setChecked(bool(v))
        if v:
            self.edit.setDate(QDate(date.fromisoformat(v)))


# ---------------------------------------------------------------- paneeli

class FilterPanel(QWidget):
    build_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Osiot näytetään pääikkunassa suodatinpainikkeiden ponnahdusikkunoissa.
        self.sections: dict[str, tuple[str, QWidget]] = {}

        def section(key: str, title: str, widget: QWidget) -> None:
            widget.setTitle("")
            widget.setParent(self)
            widget.hide()
            self.sections[key] = (title, widget)

        # --- BPM
        g = QGroupBox("BPM")
        f = QFormLayout(g)
        row = QHBoxLayout()
        self.bpm_min = opt_dspin(0, 300, 1)
        self.bpm_max = opt_dspin(0, 300, 1)
        row.addWidget(self.bpm_min)
        row.addWidget(QLabel("–"))
        row.addWidget(self.bpm_max)
        f.addRow("Väli", row)
        self.bpm_half_double = QCheckBox("Hyväksy myös puolikas / tupla-tempo")
        f.addRow(self.bpm_half_double)
        section("bpm", "BPM", g)

        # --- Sävellaji
        g = QGroupBox("Sävellaji")
        v = QVBoxLayout(g)
        grid = QGridLayout()
        grid.setSpacing(2)
        self.key_buttons: dict[str, QToolButton] = {}
        for li, letter in enumerate("AB"):
            for n in range(1, 13):
                code = f"{n}{letter}"
                b = QToolButton()
                b.setText(f"{code}\n{camelot_to_classical(code)}")
                b.setCheckable(True)
                b.setToolTip(f"{code} = {camelot_to_classical(code)} ({'molli' if letter == 'A' else 'duuri'})")
                b.setMinimumSize(46, 40)
                col = camelot_color(code)
                b.setStyleSheet(
                    f"QToolButton {{ color: {col.name()}; }}"
                    f"QToolButton:checked {{ background: {col.name()}; color: #0b0b0c; font-weight: 700; }}"
                )
                self.key_buttons[code] = b
                r = li * 2 + (0 if n <= 6 else 1)
                grid.addWidget(b, r, (n - 1) % 6)
        v.addLayout(grid)
        self.keys_compatible = QCheckBox("Myös harmonisesti yhteensopivat (±1, A↔B)")
        self.keys_extended = QCheckBox("Laajennettu (+2 ja diagonaalit)")
        clear_keys = QPushButton("Tyhjennä sävellajit")
        clear_keys.clicked.connect(lambda: [b.setChecked(False) for b in self.key_buttons.values()])
        v.addWidget(self.keys_compatible)
        v.addWidget(self.keys_extended)
        v.addWidget(clear_keys)
        section("key", "Sävellaji", g)

        # --- Genre
        g = QGroupBox("Genre")
        v = QVBoxLayout(g)
        self.genres = IncludeExclude("Suodata genrejä…", 130)
        v.addWidget(self.genres)
        section("genre", "Genre", g)

        # --- Arvio, väri
        g = QGroupBox("Arvio ja väri")
        f = QFormLayout(g)
        row = QHBoxLayout()
        self.rating_min = QComboBox()
        self.rating_max = QComboBox()
        for i in range(6):
            self.rating_min.addItem("—" if i == 0 else "★" * i, i)
            self.rating_max.addItem("★" * i if i else "0 (ei arviota)", i)
        self.rating_max.setCurrentIndex(5)
        row.addWidget(QLabel("väh."))
        row.addWidget(self.rating_min)
        row.addWidget(QLabel("enint."))
        row.addWidget(self.rating_max)
        f.addRow("Tähdet", row)
        self.colours = IncludeExclude("Suodata värejä…", 100)
        self.colours.set_items(COLOUR_NAMES)
        f.addRow(self.colours)
        section("rating", "Arvio ja väri", g)

        # --- My Tag & kommentti
        g = QGroupBox("My Tag ja kommentti")
        f = QFormLayout(g)
        self.mytags = IncludeExclude("Suodata tageja…", 110)
        f.addRow(self.mytags)
        self.mytags_mode = QComboBox()
        self.mytags_mode.addItem("jokin valituista", "any")
        self.mytags_mode.addItem("kaikki valitut", "all")
        f.addRow("Sisällytä, kun", self.mytags_mode)
        self.comment_contains = QLineEdit()
        self.comment_contains.setPlaceholderText("esim. vocal")
        self.comment_excludes = QLineEdit()
        self.comment_excludes.setPlaceholderText("esim. edit")
        f.addRow("Kommentissa", self.comment_contains)
        f.addRow("Ei kommentissa", self.comment_excludes)
        section("tags", "My Tag ja kommentti", g)

        # --- Aika
        g = QGroupBox("Vuosi, lisäyspäivä, pituus, toistot")
        f = QFormLayout(g)
        row = QHBoxLayout()
        self.year_min = opt_spin(1899, 2100)
        self.year_max = opt_spin(1899, 2100)
        row.addWidget(self.year_min)
        row.addWidget(QLabel("–"))
        row.addWidget(self.year_max)
        f.addRow("Julkaisuvuosi", row)
        self.added_from = DateField("alkaen")
        self.added_to = DateField("asti")
        f.addRow("Lisätty", self.added_from)
        f.addRow("", self.added_to)
        self.added_last_days = opt_spin(0, 3650, " pv")
        f.addRow("Lisätty viim.", self.added_last_days)
        row = QHBoxLayout()
        self.duration_min = opt_dspin(0, 60, 1, " min")
        self.duration_max = opt_dspin(0, 60, 1, " min")
        row.addWidget(self.duration_min)
        row.addWidget(QLabel("–"))
        row.addWidget(self.duration_max)
        f.addRow("Pituus", row)
        row = QHBoxLayout()
        self.play_min = opt_spin(-1, 99999)
        self.play_max = opt_spin(-1, 99999)
        row.addWidget(self.play_min)
        row.addWidget(QLabel("–"))
        row.addWidget(self.play_max)
        f.addRow("Toistokerrat", row)
        time_group, time_form = g, f

        # --- Teksti: hakukenttä on pääikkunan yläpalkissa, poissulkeva haku "Lisää"-osiossa
        self.text_search = QLineEdit()
        self.text_search.setObjectName("search")
        self.text_search.setPlaceholderText("Hae artistia, nimeä, albumia tai levy-yhtiötä…")
        self.text_search.setClearButtonEnabled(True)
        self.text_exclude = QLineEdit()
        self.text_exclude.setPlaceholderText("mikä tahansa sana sulkee pois")
        time_form.addRow("Ei sisällä sanoja", self.text_exclude)
        section("more", "Lisää ehtoja", time_group)

        # --- Järjestys
        g = QGroupBox("Järjestys")
        f = QFormLayout(g)
        self.sort_mode = QComboBox()
        for k, label in SORT_MODES.items():
            self.sort_mode.addItem(label, k)
        f.addRow("Järjestä", self.sort_mode)
        self.sort_desc = QCheckBox("Laskeva järjestys")
        f.addRow(self.sort_desc)
        self.harm_dir = QComboBox()
        self.harm_dir.addItem("BPM nousee", "up")
        self.harm_dir.addItem("BPM laskee", "down")
        self.harm_dir.addItem("BPM pysyy tasaisena", "flat")
        self.harm_dir_label = QLabel("Tempo")
        f.addRow(self.harm_dir_label, self.harm_dir)

        self.arc_box = QWidget()
        af = QFormLayout(self.arc_box)
        af.setContentsMargins(0, 0, 0, 0)
        self.arc_start = QDoubleSpinBox()
        self.arc_peak = QDoubleSpinBox()
        self.arc_end = QDoubleSpinBox()
        for s, val in ((self.arc_start, 4), (self.arc_peak, 9), (self.arc_end, 5)):
            s.setRange(1, 10)
            s.setDecimals(1)
            s.setSingleStep(0.5)
            s.setValue(val)
        row = QHBoxLayout()
        for lbl, s in (("alku", self.arc_start), ("huippu", self.arc_peak), ("loppu", self.arc_end)):
            row.addWidget(QLabel(lbl))
            row.addWidget(s)
        af.addRow("Energia 1–10", row)
        self.arc_peak_pos = QSpinBox()
        self.arc_peak_pos.setRange(0, 100)
        self.arc_peak_pos.setSuffix(" % setistä")
        self.arc_peak_pos.setValue(70)
        af.addRow("Huipun kohta", self.arc_peak_pos)
        self.arc_harmonic = QCheckBox("Suosi harmonisia siirtymiä")
        self.arc_harmonic.setChecked(True)
        af.addRow(self.arc_harmonic)
        f.addRow(self.arc_box)
        self.sort_mode.currentIndexChanged.connect(self._update_sort_visibility)
        section("sort", "Järjestys", g)

        # --- Rajaus
        g = QGroupBox("Pituus / määrä")
        f = QFormLayout(g)
        self.target_count = opt_spin(0, 1000, " kpl")
        self.target_minutes = opt_spin(0, 1440, " min")
        f.addRow("Kappalemäärä enint.", self.target_count)
        f.addRow("Kokonaiskesto", self.target_minutes)
        section("limit", "Setin pituus", g)

        for le in (self.text_search, self.text_exclude, self.comment_contains, self.comment_excludes):
            le.returnPressed.connect(self.build_requested.emit)

        self._update_sort_visibility()

    # ---------------------------------------------------------------- kirjasto
    def set_library(self, lib: Library) -> None:
        self.genres.set_items(lib.genres())
        self.mytags.set_items(lib.mytags())

    def reset(self) -> None:
        """Tyhjentää suodattimet mutta säilyttää järjestyksen ja setin pituuden."""
        keep = self.get_recipe()
        fresh = Recipe(
            sort_mode=keep.sort_mode, sort_descending=keep.sort_descending,
            harmonic_bpm_direction=keep.harmonic_bpm_direction, arc_start=keep.arc_start,
            arc_peak=keep.arc_peak, arc_end=keep.arc_end, arc_peak_position=keep.arc_peak_position,
            arc_prefer_harmonic=keep.arc_prefer_harmonic, target_count=keep.target_count,
            target_minutes=keep.target_minutes,
        )
        self.set_recipe(fresh)

    def _update_sort_visibility(self) -> None:
        mode = self.sort_mode.currentData()
        self.harm_dir.setVisible(mode == "harmonic")
        self.harm_dir_label.setVisible(mode == "harmonic")
        self.arc_box.setVisible(mode == "energy_arc")
        self.sort_desc.setVisible(mode not in ("harmonic", "energy_arc"))

    # ---------------------------------------------------------------- recipe <-> UI
    def get_recipe(self, base: Recipe | None = None) -> Recipe:
        r = Recipe()
        if base:
            r.name, r.folder = base.name, base.folder
            r.manual_exclude = list(base.manual_exclude)
        r.bpm_min = spin_value(self.bpm_min)
        r.bpm_max = spin_value(self.bpm_max)
        r.bpm_half_double = self.bpm_half_double.isChecked()
        r.keys = [k for k, b in self.key_buttons.items() if b.isChecked()]
        r.keys_compatible = self.keys_compatible.isChecked()
        r.keys_compatible_extended = self.keys_extended.isChecked()
        r.genres_include = self.genres.include.checked()
        r.genres_exclude = self.genres.exclude.checked()
        rmin = self.rating_min.currentData()
        rmax = self.rating_max.currentData()
        r.rating_min = rmin or None
        r.rating_max = None if rmax == 5 else rmax
        r.colours_include = self.colours.include.checked()
        r.colours_exclude = self.colours.exclude.checked()
        r.mytags_include = self.mytags.include.checked()
        r.mytags_exclude = self.mytags.exclude.checked()
        r.mytags_include_mode = self.mytags_mode.currentData()
        r.comment_contains = self.comment_contains.text().strip()
        r.comment_excludes = self.comment_excludes.text().strip()
        r.year_min = spin_value(self.year_min)
        r.year_max = spin_value(self.year_max)
        r.added_from = self.added_from.value()
        r.added_to = self.added_to.value()
        r.added_last_days = spin_value(self.added_last_days)
        dmin = spin_value(self.duration_min)
        dmax = spin_value(self.duration_max)
        r.duration_min = round(dmin * 60) if dmin is not None else None
        r.duration_max = round(dmax * 60) if dmax is not None else None
        r.play_count_min = spin_value(self.play_min)
        r.play_count_max = spin_value(self.play_max)
        r.text_search = self.text_search.text().strip()
        r.text_exclude = self.text_exclude.text().strip()
        r.sort_mode = self.sort_mode.currentData()
        r.sort_descending = self.sort_desc.isChecked()
        r.harmonic_bpm_direction = self.harm_dir.currentData()
        r.arc_start = self.arc_start.value()
        r.arc_peak = self.arc_peak.value()
        r.arc_end = self.arc_end.value()
        r.arc_peak_position = self.arc_peak_pos.value() / 100
        r.arc_prefer_harmonic = self.arc_harmonic.isChecked()
        r.target_count = spin_value(self.target_count)
        r.target_minutes = spin_value(self.target_minutes)
        return r

    def set_recipe(self, r: Recipe) -> None:
        set_spin(self.bpm_min, r.bpm_min)
        set_spin(self.bpm_max, r.bpm_max)
        self.bpm_half_double.setChecked(r.bpm_half_double)
        wanted = {to_camelot(k) for k in r.keys}
        for k, b in self.key_buttons.items():
            b.setChecked(k in wanted)
        self.keys_compatible.setChecked(r.keys_compatible)
        self.keys_extended.setChecked(r.keys_compatible_extended)
        self.genres.include.set_checked(r.genres_include)
        self.genres.exclude.set_checked(r.genres_exclude)
        self.rating_min.setCurrentIndex(r.rating_min or 0)
        self.rating_max.setCurrentIndex(5 if r.rating_max is None else r.rating_max)
        self.colours.include.set_checked(r.colours_include)
        self.colours.exclude.set_checked(r.colours_exclude)
        self.mytags.include.set_checked(r.mytags_include)
        self.mytags.exclude.set_checked(r.mytags_exclude)
        self.mytags_mode.setCurrentIndex(1 if r.mytags_include_mode == "all" else 0)
        self.comment_contains.setText(r.comment_contains)
        self.comment_excludes.setText(r.comment_excludes)
        set_spin(self.year_min, r.year_min)
        set_spin(self.year_max, r.year_max)
        self.added_from.set_value(r.added_from)
        self.added_to.set_value(r.added_to)
        set_spin(self.added_last_days, r.added_last_days)
        set_spin(self.duration_min, None if r.duration_min is None else r.duration_min / 60)
        set_spin(self.duration_max, None if r.duration_max is None else r.duration_max / 60)
        set_spin(self.play_min, r.play_count_min)
        set_spin(self.play_max, r.play_count_max)
        self.text_search.setText(r.text_search)
        self.text_exclude.setText(r.text_exclude)
        idx = self.sort_mode.findData(r.sort_mode)
        self.sort_mode.setCurrentIndex(max(0, idx))
        self.sort_desc.setChecked(r.sort_descending)
        self.harm_dir.setCurrentIndex(max(0, self.harm_dir.findData(r.harmonic_bpm_direction)))
        self.arc_start.setValue(r.arc_start)
        self.arc_peak.setValue(r.arc_peak)
        self.arc_end.setValue(r.arc_end)
        self.arc_peak_pos.setValue(round(r.arc_peak_position * 100))
        self.arc_harmonic.setChecked(r.arc_prefer_harmonic)
        set_spin(self.target_count, r.target_count)
        set_spin(self.target_minutes, r.target_minutes)
        self._update_sort_visibility()


# ---------------------------------------------------------------- painikkeiden tekstit

def _fmt_num(v: float) -> str:
    return f"{v:g}"


def _first_plus(items: list[str]) -> str:
    return items[0] + (f" +{len(items) - 1}" if len(items) > 1 else "")


def section_summary(key: str, r: Recipe) -> str | None:
    """Lyhyt kuvaus aktiivisesta suodattimesta painikkeeseen (None = ei aktiivinen)."""
    if key == "bpm":
        if r.bpm_min is None and r.bpm_max is None:
            return None
        lo = _fmt_num(r.bpm_min) if r.bpm_min is not None else "…"
        hi = _fmt_num(r.bpm_max) if r.bpm_max is not None else "…"
        return f"BPM {lo}–{hi}" + (" ½×2" if r.bpm_half_double else "")
    if key == "key":
        if not r.keys:
            return None
        keys = sorted({to_camelot(k) or k for k in r.keys}, key=lambda c: (int(c[:-1]), c[-1]))
        txt = ", ".join(keys[:3]) + (f" +{len(keys) - 3}" if len(keys) > 3 else "")
        return txt + (" ≈" if r.keys_compatible or r.keys_compatible_extended else "")
    if key == "genre":
        parts = []
        if r.genres_include:
            parts.append(_first_plus(r.genres_include))
        if r.genres_exclude:
            parts.append("ei " + _first_plus(r.genres_exclude))
        return " · ".join(parts) or None
    if key == "rating":
        parts = []
        if r.rating_min:
            parts.append(f"★{r.rating_min}+")
        if r.rating_max is not None:
            parts.append(f"≤★{r.rating_max}")
        if r.colours_include or r.colours_exclude:
            parts.append(f"väri {len(r.colours_include) + len(r.colours_exclude)}")
        return " ".join(parts) or None
    if key == "tags":
        parts = []
        if r.mytags_include:
            parts.append(_first_plus(r.mytags_include))
        if r.mytags_exclude:
            parts.append("ei " + _first_plus(r.mytags_exclude))
        if r.comment_contains or r.comment_excludes:
            parts.append("kommentti")
        return " · ".join(parts) or None
    if key == "more":
        n = sum(
            1 for v in (
                r.year_min, r.year_max, r.added_from, r.added_to, r.added_last_days,
                r.duration_min, r.duration_max, r.play_count_min, r.play_count_max,
                r.text_exclude or None,
            ) if v is not None
        )
        return f"Lisää · {n}" if n else None
    if key == "sort":
        return None if r.sort_mode == "none" else SORT_MODES.get(r.sort_mode, r.sort_mode)
    if key == "limit":
        parts = []
        if r.target_minutes:
            parts.append(f"{r.target_minutes} min")
        if r.target_count:
            parts.append(f"{r.target_count} kpl")
        return " / ".join(parts) or None
    return None
