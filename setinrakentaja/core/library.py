"""Rekordboxin XML-viennin (rekordbox.xml) lukeminen.

Tiedostoa luetaan ainoastaan. Jokaisen kappaleen alkuperäinen <TRACK>-elementti
säilytetään sellaisenaan, jotta vienti voi kopioida sen muuttumattomana
(Location, TEMPO, POSITION_MARK jne.).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlparse

from .keys import to_camelot

# Rekordboxin värit (Colour-attribuutti) -> nimi
COLOURS = {
    "0xFF007F": "Pinkki",
    "0xFF0000": "Punainen",
    "0xFFA500": "Oranssi",
    "0xFFFF00": "Keltainen",
    "0x00FF00": "Vihreä",
    "0x25FDE9": "Turkoosi",
    "0x0000FF": "Sininen",
    "0x660099": "Violetti",
}
COLOUR_NAMES = list(COLOURS.values())

# "Add My Tag to Comments" -asetus kirjoittaa tagit muodossa: /* Tagi 1 / Tagi 2 */
_MYTAG_BLOCK_RE = re.compile(r"/\*(.*?)\*/", re.S)
_HASHTAG_RE = re.compile(r"(?<![\w&])#([\w\-]+)", re.UNICODE)
_ENERGY_RE = [
    re.compile(r"\b(?:energy|energia)\s*[:=]?\s*(10|[1-9])\b", re.I),
    re.compile(r"\bE(10|[1-9])\b"),
]


class LibraryError(Exception):
    pass


@dataclass(eq=False)
class Track:
    track_id: str
    name: str
    artist: str
    album: str
    genre: str
    bpm: float
    key_raw: str
    camelot: str | None
    rating: int  # tähdet 0–5
    colour: str  # värin nimi tai ""
    comment: str
    mytags: list[str]
    year: int | None
    date_added: date | None
    duration: int  # sekunteina
    play_count: int
    location: str
    label: str
    remixer: str
    energy_tag: int | None
    element: ET.Element = field(repr=False)

    @property
    def file_path(self) -> str:
        """Location-URL tiedostopoluksi (vain näyttöä varten)."""
        try:
            p = urlparse(self.location)
            return unquote(p.path)
        except ValueError:
            return self.location


@dataclass
class Library:
    path: Path
    product_name: str
    product_version: str
    product_company: str
    tracks: list[Track]

    @property
    def by_id(self) -> dict[str, Track]:
        return {t.track_id: t for t in self.tracks}

    def genres(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for t in self.tracks:
            g = t.genre.strip()
            if g:
                out[g] = out.get(g, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: kv[0].lower()))

    def mytags(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for t in self.tracks:
            for tag in t.mytags:
                out[tag] = out.get(tag, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: kv[0].lower()))


def _int(v: str | None, default: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else default
    except ValueError:
        return default


def _float(v: str | None) -> float:
    try:
        return float(v) if v else 0.0
    except ValueError:
        return 0.0


def _date(v: str | None) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(v.strip()[:10])
    except ValueError:
        return None


def parse_mytags(comment: str) -> list[str]:
    """Poimii My Tag -tagit kommentista.

    Tukee Rekordboxin "Add My Tag to Comments" -muotoa /* Tagi / Tagi */ sekä #hashtageja.
    """
    tags: list[str] = []
    for block in _MYTAG_BLOCK_RE.findall(comment or ""):
        for part in block.split("/"):
            part = part.strip()
            if part:
                tags.append(part)
    for h in _HASHTAG_RE.findall(_MYTAG_BLOCK_RE.sub(" ", comment or "")):
        tags.append(h)
    # duplikaatit pois järjestys säilyttäen
    seen: set[str] = set()
    out = []
    for t in tags:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)
    return out


def parse_energy(comment: str, mytags: list[str]) -> int | None:
    for text in [comment or "", *mytags]:
        for rx in _ENERGY_RE:
            m = rx.search(text)
            if m:
                return int(m.group(1))
    return None


def track_from_element(el: ET.Element) -> Track:
    a = el.attrib
    comment = a.get("Comments", "")
    tags = parse_mytags(comment)
    colour_attr = a.get("Colour", "").strip()
    colour = COLOURS.get(colour_attr.upper().replace("0X", "0x"), "")
    year = _int(a.get("Year"), 0)
    rating_raw = _int(a.get("Rating"), 0)
    return Track(
        track_id=a.get("TrackID", ""),
        name=a.get("Name", ""),
        artist=a.get("Artist", ""),
        album=a.get("Album", ""),
        genre=a.get("Genre", ""),
        bpm=_float(a.get("AverageBpm")),
        key_raw=a.get("Tonality", ""),
        camelot=to_camelot(a.get("Tonality", "")),
        rating=max(0, min(5, round(rating_raw / 51))),
        colour=colour,
        comment=comment,
        mytags=tags,
        year=year or None,
        date_added=_date(a.get("DateAdded")),
        duration=_int(a.get("TotalTime"), 0),
        play_count=_int(a.get("PlayCount"), 0),
        location=a.get("Location", ""),
        label=a.get("Label", ""),
        remixer=a.get("Remixer", ""),
        energy_tag=parse_energy(comment, tags),
        element=el,
    )


def load_library(path: str | Path) -> Library:
    """Lukee rekordbox.xml-tiedoston. Tiedostoa ei muokata."""
    path = Path(path)
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        raise LibraryError(f"XML-tiedoston lukeminen epäonnistui: {e}") from e
    except OSError as e:
        raise LibraryError(f"Tiedostoa ei voitu avata: {e}") from e

    root = tree.getroot()
    if root.tag != "DJ_PLAYLISTS":
        raise LibraryError(
            "Tiedosto ei näytä Rekordboxin XML-viennilta (juurielementti ei ole DJ_PLAYLISTS)."
        )
    product = root.find("PRODUCT")
    collection = root.find("COLLECTION")
    if collection is None:
        raise LibraryError("XML-tiedostosta puuttuu COLLECTION-osio.")

    tracks = [
        track_from_element(el)
        for el in collection.findall("TRACK")
        if el.get("TrackID") and el.get("Location")
    ]
    return Library(
        path=path,
        product_name=product.get("Name", "rekordbox") if product is not None else "rekordbox",
        product_version=product.get("Version", "") if product is not None else "",
        product_company=product.get("Company", "") if product is not None else "",
        tracks=tracks,
    )
