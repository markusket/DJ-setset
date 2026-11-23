import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pytest

from setinrakentaja.core.builder import build_playlist, build_tracks
from setinrakentaja.core.exporter import ExportError, ExportPlaylist, build_xml, export_xml
from setinrakentaja.core.filters import apply_filters
from setinrakentaja.core.keys import (
    camelot_to_classical,
    compatible_keys,
    key_distance,
    to_camelot,
)
from setinrakentaja.core.library import LibraryError, load_library, parse_mytags
from setinrakentaja.core.recipe import Recipe
from setinrakentaja.core.sequencing import arrange, energy_curve

SAMPLE = Path(__file__).parent / "data" / "esimerkki_rekordbox.xml"


@pytest.fixture
def lib():
    return load_library(SAMPLE)


# ------------------------------------------------------------------ sävellajit

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("8A", "8A"), ("08a", "8A"), ("Am", "8A"), ("A min", "8A"), ("C", "8B"),
        ("F#m", "11A"), ("Gbm", "11A"), ("Dbm", "12A"), ("C#m", "12A"), ("Abm", "1A"),
        ("G#m", "1A"), ("B", "1B"), ("Db", "3B"), ("Eb", "5B"), ("D♭m", "12A"),
        ("1m", "8A"), ("1d", "8B"), ("", None), ("xyz", None), ("12B", "12B"),
    ],
)
def test_to_camelot(raw, expected):
    assert to_camelot(raw) == expected


def test_all_camelot_roundtrip():
    for n in range(1, 13):
        for l in "AB":
            code = f"{n}{l}"
            assert to_camelot(camelot_to_classical(code)) == code


def test_compatible():
    assert compatible_keys("8A") == {"8A", "7A", "9A", "8B"}
    assert compatible_keys("12B") == {"12B", "11B", "1B", "12A"}
    assert compatible_keys("1A") == {"1A", "12A", "2A", "1B"}
    assert "10A" in compatible_keys("8A", extended=True)
    assert key_distance("8A", "8A") == 0
    assert key_distance("8A", "9A") == 1
    assert key_distance("8A", "2A") > 3


# ------------------------------------------------------------------ kirjasto

def test_load_library(lib):
    assert len(lib.tracks) == 60
    assert lib.product_version == "7.0.4"
    t = lib.tracks[1]
    assert t.artist == "Kalle & Kide"
    assert "%26" in t.location
    assert t.camelot == "3A"  # Bbm
    assert t.mytags == ["Groovy", "Peak Time"]
    assert all(0 <= x.rating <= 5 for x in lib.tracks)
    assert "Techno" in lib.genres()


def test_parse_mytags():
    assert parse_mytags("Kiva /* Peak Time / Vocal */ #closing") == ["Peak Time", "Vocal", "closing"]
    assert parse_mytags("") == []


def test_not_rekordbox(tmp_path):
    p = tmp_path / "x.xml"
    p.write_text("<foo/>")
    with pytest.raises(LibraryError):
        load_library(p)


def test_camelot_tonality(tmp_path):
    p = tmp_path / "c.xml"
    p.write_text(
        '<?xml version="1.0" encoding="UTF-8"?><DJ_PLAYLISTS Version="1.0.0">'
        '<PRODUCT Name="rekordbox" Version="7.1.0" Company="AlphaTheta"/>'
        '<COLLECTION Entries="1"><TRACK TrackID="1" Name="a" Tonality="8A" AverageBpm="124.00" '
        'Location="file://localhost/Users/x/a.mp3" Rating="255" Colour="0xff0000"/></COLLECTION>'
        "</DJ_PLAYLISTS>"
    )
    t = load_library(p).tracks[0]
    assert t.camelot == "8A" and t.rating == 5 and t.colour == "Punainen"


# ------------------------------------------------------------------ suodatus

def test_bpm_and_genre(lib):
    r = Recipe(bpm_min=122, bpm_max=128, genres_include=["Tech House", "deep house"])
    res = apply_filters(lib.tracks, r)
    assert res
    assert all(122 <= t.bpm <= 128 for t in res)
    assert all(t.genre in ("Tech House", "Deep House") for t in res)


def test_exclusions(lib):
    r = Recipe(genres_exclude=["Techno"], text_exclude="lumo")
    res = apply_filters(lib.tracks, r)
    assert all(t.genre != "Techno" and "lumo" not in t.artist.lower() for t in res)
    assert len(res) < len(lib.tracks)


def test_half_double(lib):
    t = lib.tracks[0]
    r = Recipe(bpm_min=t.bpm * 2 - 0.1, bpm_max=t.bpm * 2 + 0.1, bpm_half_double=True)
    assert t in apply_filters(lib.tracks, r)


def test_key_filter(lib):
    r = Recipe(keys=["Am"], keys_compatible=True)
    res = apply_filters(lib.tracks, r)
    assert res and all(t.camelot in {"8A", "7A", "9A", "8B"} for t in res)


def test_other_filters(lib):
    r = Recipe(
        rating_min=3, play_count_max=5, year_min=2020, duration_min=300,
        added_from="2024-01-01", mytags_exclude=["Dark"],
    )
    for t in apply_filters(lib.tracks, r):
        assert t.rating >= 3 and t.play_count <= 5 and t.year >= 2020 and t.duration >= 300
        assert t.date_added >= date(2024, 1, 1) and "Dark" not in t.mytags


def test_added_last_days(lib):
    r = Recipe(added_last_days=365)
    res = apply_filters(lib.tracks, r, today=date(2026, 6, 30))
    assert all(t.date_added >= date(2025, 6, 30) for t in res)


def test_text_and_tags(lib):
    r = Recipe(text_search="kalle kide", mytags_include=["Peak Time"])
    res = apply_filters(lib.tracks, r)
    assert all("Peak Time" in t.mytags and "Kalle" in t.artist for t in res)


def test_manual_exclude(lib):
    loc = lib.tracks[0].location
    assert lib.tracks[0] not in apply_filters(lib.tracks, Recipe(manual_exclude=[loc]))


# ------------------------------------------------------------------ järjestys

def test_sort_bpm_and_limits(lib):
    res = arrange(lib.tracks, Recipe(sort_mode="bpm", target_count=10))
    assert len(res) == 10
    assert [t.bpm for t in res] == sorted(t.bpm for t in res)
    res = arrange(lib.tracks, Recipe(sort_mode="bpm", sort_descending=True, target_minutes=60))
    total = sum(t.duration for t in res)
    assert total >= 3600 and total - res[-1].duration < 3600


def test_harmonic(lib):
    res = arrange(lib.tracks, Recipe(sort_mode="harmonic", target_count=15))
    assert len(res) == 15 and len({t.track_id for t in res}) == 15
    good = sum(key_distance(a.camelot, b.camelot) <= 1 for a, b in zip(res, res[1:]))
    assert good >= 10  # suurin osa siirtymistä yhteensopivia
    # BPM nousee pääosin
    rises = sum(b.bpm >= a.bpm - 0.5 for a, b in zip(res, res[1:]))
    assert rises >= 11


def test_energy_arc(lib):
    r = Recipe(sort_mode="energy_arc", target_minutes=90)
    res = arrange(lib.tracks, r)
    total = sum(t.duration for t in res) / 60
    assert 80 <= total <= 100
    curve = energy_curve(11, 3, 9, 5, 0.7)
    assert curve[0] == 3 and curve[7] == 9 and curve[-1] == 5


# ------------------------------------------------------------------ vienti

def test_export_structure_and_locations(lib, tmp_path):
    p1 = build_playlist(lib, Recipe(name="Tech 122–128", folder="Keikat/Joulu",
                                    bpm_min=122, bpm_max=128, sort_mode="bpm"))
    p2 = build_playlist(lib, Recipe(name="Techno", folder="Keikat", genres_include=["Techno"]))
    p3 = build_playlist(lib, Recipe(name="Kaikki & muut", target_count=5))
    out = export_xml(lib, [p1, p2, p3], tmp_path / "uusi.xml")

    raw = out.read_bytes()
    assert raw.startswith(b'<?xml version="1.0" encoding="UTF-8"?>')

    root = ET.parse(out).getroot()
    assert root.tag == "DJ_PLAYLISTS" and root.get("Version") == "1.0.0"
    assert [c.tag for c in root] == ["PRODUCT", "COLLECTION", "PLAYLISTS"]
    coll = root.find("COLLECTION")
    ids = {t.get("TrackID") for t in coll.findall("TRACK")}
    assert int(coll.get("Entries")) == len(ids) == len(coll.findall("TRACK"))

    # Jokainen TRACK identtinen alkuperäisen kanssa (attribuutit ja lapsielementit)
    orig = {t.track_id: t.element for t in lib.tracks}
    for el in coll.findall("TRACK"):
        o = orig[el.get("TrackID")]
        assert el.attrib == o.attrib
        assert [(c.tag, c.attrib) for c in el] == [(c.tag, c.attrib) for c in o]

    # Location-merkkijonot säilyvät tiedostossa tavu tavulta samassa muodossa
    src = SAMPLE.read_text(encoding="utf-8")
    for el in coll.findall("TRACK"):
        assert f'Location="{el.get("Location")}"' in src

    rootnode = root.find("PLAYLISTS/NODE")
    assert rootnode.get("Name") == "ROOT" and rootnode.get("Type") == "0"
    keikat = rootnode.find("NODE[@Name='Keikat']")
    assert keikat.get("Type") == "0" and keikat.get("Count") == "2"
    joulu = keikat.find("NODE[@Name='Joulu']")
    pl = joulu.find("NODE")
    assert pl.get("Type") == "1" and pl.get("KeyType") == "0"
    assert int(pl.get("Entries")) == len(p1.tracks) == len(pl.findall("TRACK"))
    assert [t.get("Key") for t in pl.findall("TRACK")] == [t.track_id for t in p1.tracks]
    assert all(t.get("Key") in ids for t in root.iter("TRACK") if t.get("Key"))
    assert rootnode.get("Count") == "2"

    # Uudelleenluku omalla lukijalla toimii
    again = load_library(out)
    assert {t.location for t in again.tracks} == {orig[i].get("Location") for i in ids}


def test_never_overwrite_source(lib, tmp_path):
    pl = ExportPlaylist("x", lib.tracks[:3])
    with pytest.raises(ExportError):
        export_xml(lib, [pl], SAMPLE)
    target = tmp_path / "a.xml"
    export_xml(lib, [pl], target)
    with pytest.raises(ExportError):
        export_xml(lib, [pl], target)
    export_xml(lib, [pl], target, overwrite=True)


def test_empty_playlist_refused(lib, tmp_path):
    with pytest.raises(ExportError):
        export_xml(lib, [ExportPlaylist("tyhjä", [])], tmp_path / "x.xml")


def test_recipe_roundtrip(tmp_path):
    r = Recipe(name="Testi", bpm_min=120, genres_include=["Disco"], sort_mode="harmonic")
    p = tmp_path / "r.json"
    r.save(p)
    assert Recipe.load(p) == r
    assert Recipe.from_dict({"name": "x", "tuntematon": 1}).name == "x"


def test_build_xml_duplicates(lib):
    a = ExportPlaylist("a", lib.tracks[:5])
    b = ExportPlaylist("b", lib.tracks[3:8])
    root = build_xml(lib, [a, b]).getroot()
    assert root.find("COLLECTION").get("Entries") == "8"
    assert build_tracks(lib, Recipe(target_count=3))


def test_fast_sequencer_matches_exact():
    """Nopea polku (ämpärit) valitsee harmonisessa tilassa joka askeleella halvimman kappaleen."""
    import random

    from setinrakentaja.core import sequencing as sq
    from setinrakentaja.core.keys import ALL_CAMELOT
    from setinrakentaja.core.library import Track

    rnd = random.Random(3)
    pool = [
        Track(str(i), f"t{i}", "a", "", "g", round(rnd.uniform(118, 132), 2),
              "", rnd.choice(ALL_CAMELOT + [None]), rnd.randint(0, 5), "", "", [], None, None,
              rnd.randint(200, 500), 0, f"file://localhost/x{i}.mp3", "", "", None, None)
        for i in range(300)
    ]
    for direction in ("up", "down", "flat"):
        spec = sq._harmonic_cost_factory(pool, 40, direction)
        cost = spec[0]
        fast = sq._sequence_fast(pool, 40, *spec)
        remaining = list(pool)
        prev = None
        for i, pick in enumerate(fast):
            best = min(cost(t, i, prev) for t in remaining)
            assert abs(cost(pick, i, prev) - best) < 1e-9, (direction, i)
            remaining.remove(pick)
            prev = pick
