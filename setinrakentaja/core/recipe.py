"""Resepti = tallennettu suodatin-, järjestys- ja rajausyhdistelmä (JSON)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

RECIPE_VERSION = 1

SORT_MODES = {
    "none": "Ei järjestystä (kirjaston järjestys)",
    "bpm": "BPM",
    "key": "Sävellaji (Camelot)",
    "rating": "Arvio",
    "date_added": "Lisäyspäivä",
    "year": "Julkaisuvuosi",
    "artist": "Artisti",
    "name": "Nimi",
    "play_count": "Toistokerrat",
    "harmonic": "Harmoninen setti",
    "energy_arc": "Energiakaari",
}


@dataclass
class Recipe:
    # --- soittolista ---
    name: str = "Uusi soittolista"
    folder: str = ""  # esim. "Keikat/2026 Joulu" ("/" erottaa kansiot)

    # --- suodattimet (None / tyhjä = ei rajausta) ---
    bpm_min: float | None = None
    bpm_max: float | None = None
    bpm_half_double: bool = False  # hyväksy myös puolikas/tupla-tempo

    keys: list[str] = field(default_factory=list)  # Camelot-koodit
    keys_compatible: bool = False  # laajenna yhteensopiviin sävellajeihin
    keys_compatible_extended: bool = False  # myös +2 ja diagonaalit

    genres_include: list[str] = field(default_factory=list)
    genres_exclude: list[str] = field(default_factory=list)

    rating_min: int | None = None
    rating_max: int | None = None

    colours_include: list[str] = field(default_factory=list)
    colours_exclude: list[str] = field(default_factory=list)

    comment_contains: str = ""
    comment_excludes: str = ""

    mytags_include: list[str] = field(default_factory=list)
    mytags_include_mode: str = "any"  # "any" = jokin, "all" = kaikki
    mytags_exclude: list[str] = field(default_factory=list)

    year_min: int | None = None
    year_max: int | None = None

    added_from: str | None = None  # ISO-päivämäärä "2024-01-31"
    added_to: str | None = None
    added_last_days: int | None = None  # esim. 30 = viimeiset 30 päivää

    duration_min: int | None = None  # sekunteina
    duration_max: int | None = None

    play_count_min: int | None = None
    play_count_max: int | None = None

    text_search: str = ""  # artisti/nimi/albumi/remixer, kaikki sanat oltava mukana
    text_exclude: str = ""  # mikä tahansa sana -> pois

    # --- järjestys ---
    sort_mode: str = "none"
    sort_descending: bool = False

    # harmoninen setti
    harmonic_bpm_direction: str = "up"  # "up", "down", "flat"
    # energiakaari (energia-asteikko 1–10)
    arc_start: float = 4.0
    arc_peak: float = 9.0
    arc_end: float = 5.0
    arc_peak_position: float = 0.7  # 0–1, kohta jossa huippu
    arc_prefer_harmonic: bool = True

    # --- rajaus ---
    target_count: int | None = None
    target_minutes: int | None = None

    # käsin poistetut kappaleet (Location-arvot), jotka pidetään poissa
    manual_exclude: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["version"] = RECIPE_VERSION
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Recipe":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, path: str | Path) -> "Recipe":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
