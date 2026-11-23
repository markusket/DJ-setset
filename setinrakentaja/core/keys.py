"""Sävellajit: Camelot- ja perinteisen merkintätavan muunnokset sekä harmoninen yhteensopivuus.

Sisäisesti kaikki sävellajit käsitellään Camelot-koodeina, esim. "8A" (= Am) tai "8B" (= C).
"""

from __future__ import annotations

import re

# Camelot-numero -> (molli, duuri) Rekordboxin käyttämillä nimillä
_CAMELOT_TABLE = {
    1: ("Abm", "B"),
    2: ("Ebm", "F#"),
    3: ("Bbm", "Db"),
    4: ("Fm", "Ab"),
    5: ("Cm", "Eb"),
    6: ("Gm", "Bb"),
    7: ("Dm", "F"),
    8: ("Am", "C"),
    9: ("Em", "G"),
    10: ("Bm", "D"),
    11: ("F#m", "A"),
    12: ("Dbm", "E"),
}

ALL_CAMELOT = [f"{n}{l}" for n in range(1, 13) for l in ("A", "B")]

_NOTE_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

_CAMELOT_RE = re.compile(r"^(1[0-2]|0?[1-9])\s*([ABab])$")
_OPENKEY_RE = re.compile(r"^(1[0-2]|0?[1-9])\s*([dmDM])$")
_CLASSICAL_RE = re.compile(
    r"^([A-Ga-g])\s*([#b]?)\s*(m|min|minor|moll|maj|major|duuri|molli)?$", re.IGNORECASE
)


def _major_number(pc: int) -> int:
    """Duurisävellajin Camelot-numero sävelluokasta (C=0 -> 8)."""
    return ((pc * 7) % 12 + 7) % 12 + 1


def to_camelot(value: str | None) -> str | None:
    """Muuntaa sävellajimerkinnän Camelot-koodiksi.

    Hyväksyy esim. "8A", "08a", "Am", "A min", "F#m", "Gb", "D♭m", "1m" (Open Key).
    Palauttaa None, jos merkintää ei tunnisteta.
    """
    if not value:
        return None
    s = value.strip().replace("♯", "#").replace("♭", "b")
    if not s:
        return None

    m = _CAMELOT_RE.match(s)
    if m:
        return f"{int(m.group(1))}{m.group(2).upper()}"

    m = _OPENKEY_RE.match(s)
    if m:
        n = int(m.group(1))
        num = (n + 6) % 12 + 1
        return f"{num}{'A' if m.group(2).lower() == 'm' else 'B'}"

    m = _CLASSICAL_RE.match(s)
    if m:
        letter, acc, quality = m.groups()
        # Pelkkä pieni "b" ilman laatua voi olla nuotti B; käsitellään isona
        pc = _NOTE_PC[letter.upper()]
        if acc == "#":
            pc += 1
        elif acc == "b":
            pc -= 1
        pc %= 12
        q = (quality or "").lower()
        minor = q in ("m", "min", "minor", "moll", "molli")
        if minor:
            return f"{_major_number((pc + 3) % 12)}A"
        return f"{_major_number(pc)}B"
    return None


def parse_camelot(code: str) -> tuple[int, str]:
    return int(code[:-1]), code[-1]


def camelot_to_classical(code: str | None) -> str:
    if not code:
        return ""
    n, l = parse_camelot(code)
    minor, major = _CAMELOT_TABLE[n]
    return minor if l == "A" else major


def format_key(code: str | None, notation: str = "both") -> str:
    """notation: 'camelot', 'classical' tai 'both'."""
    if not code:
        return ""
    if notation == "camelot":
        return code
    if notation == "classical":
        return camelot_to_classical(code)
    return f"{code} ({camelot_to_classical(code)})"


def _wrap(n: int) -> int:
    return (n - 1) % 12 + 1


def compatible_keys(code: str, extended: bool = False) -> set[str]:
    """Harmonisesti yhteensopivat sävellajit Camelot-pyörällä.

    Perussäännöt: sama sävellaji, ±1 samalla kirjaimella ja rinnakkaissävellaji (A<->B).
    Laajennettu: lisäksi +2 ("energy boost") ja diagonaalit (±1 ja kirjaimen vaihto).
    """
    n, l = parse_camelot(code)
    other = "B" if l == "A" else "A"
    keys = {f"{n}{l}", f"{_wrap(n + 1)}{l}", f"{_wrap(n - 1)}{l}", f"{n}{other}"}
    if extended:
        keys |= {f"{_wrap(n + 2)}{l}", f"{_wrap(n + 1)}{other}", f"{_wrap(n - 1)}{other}"}
    return keys


def key_distance(a: str | None, b: str | None) -> float:
    """Siirtymän "hinta" kahden sävellajin välillä (0 = sama, 1 = yhteensopiva, ...).

    Tuntematon sävellaji palauttaa 2.0 (neutraali, mutta ei suosittu).
    """
    if not a or not b:
        return 2.0
    if a == b:
        return 0.0
    if b in compatible_keys(a):
        return 1.0
    if b in compatible_keys(a, extended=True):
        return 2.0
    na, la = parse_camelot(a)
    nb, lb = parse_camelot(b)
    diff = min((na - nb) % 12, (nb - na) % 12)
    return 3.0 + diff * 0.5 + (0.5 if la != lb else 0.0)


def camelot_sort_key(code: str | None) -> tuple[int, int]:
    if not code:
        return (99, 9)
    n, l = parse_camelot(code)
    return (n, 0 if l == "A" else 1)
