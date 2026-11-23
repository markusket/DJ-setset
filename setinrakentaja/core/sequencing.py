"""Kappaleiden järjestäminen: tavalliset lajittelut, harmoninen setti ja energiakaari."""

from __future__ import annotations

from bisect import bisect_left
from datetime import date
from statistics import median
from typing import Callable

from .keys import camelot_sort_key, key_distance
from .library import Track
from .recipe import Recipe


# ---------------------------------------------------------------- energia

def energy_of(track: Track, bpm_lo: float, bpm_hi: float) -> float:
    """Kappaleen energia asteikolla 1–10.

    Jos kommentissa / My Tageissa on merkintä (esim. "Energy 7" tai "E7"), käytetään sitä.
    Muuten arvio lasketaan BPM:stä (75 %) suhteessa valikoiman BPM-alueeseen sekä
    tähtiarviosta (25 %; arvioimaton = neutraali).
    """
    if track.energy_tag is not None:
        return float(track.energy_tag)
    span = bpm_hi - bpm_lo
    bpm_norm = 0.5 if span <= 0.01 or track.bpm <= 0 else (track.bpm - bpm_lo) / span
    bpm_norm = max(0.0, min(1.0, bpm_norm))
    rating_norm = 0.5 if track.rating == 0 else (track.rating - 1) / 4
    return 1.0 + 9.0 * (0.75 * bpm_norm + 0.25 * rating_norm)


def bpm_bounds(tracks: list[Track]) -> tuple[float, float]:
    bpms = sorted(t.bpm for t in tracks if t.bpm > 0)
    if not bpms:
        return 0.0, 0.0
    return bpms[0], bpms[-1]


def energy_curve(n: int, start: float, peak: float, end: float, peak_pos: float) -> list[float]:
    if n <= 0:
        return []
    if n == 1:
        return [peak]
    peak_pos = max(0.0, min(1.0, peak_pos))
    out = []
    for i in range(n):
        x = i / (n - 1)
        if peak_pos > 0 and x <= peak_pos:
            v = start + (peak - start) * (x / peak_pos)
        elif peak_pos < 1:
            v = peak + (end - peak) * ((x - peak_pos) / (1 - peak_pos))
        else:
            v = peak
        out.append(v)
    return out


# ---------------------------------------------------------------- tavalliset lajittelut

_SIMPLE_KEYS: dict[str, Callable[[Track], object]] = {
    "bpm": lambda t: t.bpm,
    "key": lambda t: (camelot_sort_key(t.camelot), t.bpm),
    "rating": lambda t: (t.rating, t.bpm),
    "date_added": lambda t: t.date_added or date.min,
    "year": lambda t: t.year or 0,
    "artist": lambda t: (t.artist.lower(), t.name.lower()),
    "name": lambda t: (t.name.lower(), t.artist.lower()),
    "play_count": lambda t: t.play_count,
}


def _limit_simple(tracks: list[Track], recipe: Recipe) -> list[Track]:
    out = tracks
    if recipe.target_count:
        out = out[: recipe.target_count]
    if recipe.target_minutes:
        limit = recipe.target_minutes * 60
        acc, res = 0, []
        for t in out:
            if acc >= limit:
                break
            res.append(t)
            acc += t.duration
        out = res
    return out


# ---------------------------------------------------------------- ahne sekvensoija

def _sequence(
    pool: list[Track],
    n: int,
    cost: Callable[[Track, int, Track | None], float],
) -> list[Track]:
    """Tarkka ahne valinta: jokaisella askeleella halvin jäljellä oleva kappale. O(n²)."""
    remaining = list(pool)
    out: list[Track] = []
    prev: Track | None = None
    for i in range(min(n, len(pool))):
        best_idx = min(range(len(remaining)), key=lambda j: cost(remaining[j], i, prev))
        prev = remaining.pop(best_idx)
        out.append(prev)
    return out


FAST_THRESHOLD = 400


def _sequence_fast(
    pool: list[Track],
    n: int,
    cost: Callable[[Track, int, Track | None], float],
    value: Callable[[Track], float],
    probes: Callable[[int, Track | None], list[float]],
    width: int,
) -> list[Track]:
    """Nopea ahne valinta suurille joukoille.

    Kappaleet jaetaan sävellajin mukaan ämpäreihin ja lajitellaan value()-arvon mukaan.
    Sävellajin hinta on ämpärin sisällä vakio, joten riittää tutkia kandidaatit
    kustannusfunktion taitekohtien (probes) läheltä.
    """
    buckets: dict[str | None, tuple[list[float], list[Track]]] = {}
    for t in sorted(pool, key=value):
        vals, items = buckets.setdefault(t.camelot, ([], []))
        vals.append(value(t))
        items.append(t)
    out: list[Track] = []
    prev: Track | None = None
    for i in range(min(n, len(pool))):
        best: tuple[float, str | None, int] | None = None
        pts = probes(i, prev)
        for code, (vals, items) in buckets.items():
            if not vals:
                continue
            idxs: set[int] = set()
            for p in pts:
                j = bisect_left(vals, p)
                idxs.update(range(max(0, j - width), min(len(vals), j + width)))
            for k in idxs:
                c = cost(items[k], i, prev)
                if best is None or c < best[0]:
                    best = (c, code, k)
        assert best is not None
        _, code, k = best
        vals, items = buckets[code]
        vals.pop(k)
        prev = items.pop(k)
        out.append(prev)
    return out


def _run(pool: list[Track], n: int, spec) -> list[Track]:
    cost, value, probes, width = spec
    if len(pool) <= FAST_THRESHOLD:
        return _sequence(pool, n, cost)
    return _sequence_fast(pool, n, cost, value, probes, width)


def _harmonic_cost_factory(pool: list[Track], n: int, direction: str):
    lo, hi = bpm_bounds(pool)
    if direction == "flat" or n <= 1:
        mid = median([t.bpm for t in pool if t.bpm > 0] or [0])
        targets = [mid] * max(n, 1)
    else:
        a, b = (lo, hi) if direction == "up" else (hi, lo)
        targets = [a + (b - a) * i / (n - 1) for i in range(n)]

    def cost(t: Track, i: int, prev: Track | None) -> float:
        c = abs(t.bpm - targets[i]) * 0.4
        if t.camelot is None:
            c += 1.0
        if prev is not None:
            c += key_distance(prev.camelot, t.camelot) * 1.5
            delta = t.bpm - prev.bpm
            if direction == "up" and delta < -0.5:
                c += -delta * 1.0
            elif direction == "down" and delta > 0.5:
                c += delta * 1.0
            if abs(delta) > 8:
                c += (abs(delta) - 8) * 0.5
        return c

    def probes(i: int, prev: Track | None) -> list[float]:
        pts = [targets[i]]
        if prev is not None:
            pts += [prev.bpm, prev.bpm - 0.5, prev.bpm + 0.5, prev.bpm - 8, prev.bpm + 8]
        return pts

    # BPM-kustannus on konveksi, joten minimi on taitekohtien vieressä: leveys 2 riittää
    return cost, (lambda t: t.bpm), probes, 2


def _energy_cost_factory(pool: list[Track], n: int, recipe: Recipe):
    lo, hi = bpm_bounds(pool)
    energies = {id(t): energy_of(t, lo, hi) for t in pool}
    targets = energy_curve(
        n, recipe.arc_start, recipe.arc_peak, recipe.arc_end, recipe.arc_peak_position
    )

    def cost(t: Track, i: int, prev: Track | None) -> float:
        c = abs(energies[id(t)] - targets[i])
        if prev is not None:
            if recipe.arc_prefer_harmonic:
                c += key_distance(prev.camelot, t.camelot) * 0.8
            c += max(0.0, abs(t.bpm - prev.bpm) - 4) * 0.25
        return c

    return cost, (lambda t: energies[id(t)]), (lambda i, prev: [targets[i]]), 8


def _sequence_with_limits(pool: list[Track], recipe: Recipe, factory) -> list[Track]:
    if not pool:
        return []
    n = len(pool)
    if recipe.target_count:
        n = min(n, recipe.target_count)
    if not recipe.target_minutes:
        return _run(pool, n, factory(pool, n))

    target = recipe.target_minutes * 60
    avg = sum(t.duration for t in pool) / len(pool) or 360
    n = max(1, min(n, round(target / avg)))
    best: list[Track] = []
    tried: set[int] = set()
    for _ in range(8):
        tried.add(n)
        seq = _run(pool, n, factory(pool, n))
        best = seq
        total = sum(t.duration for t in seq)
        avg_seq = total / len(seq) if seq else avg
        if total < target - avg_seq / 2 and n < len(pool) and (n + 1) not in tried:
            n += 1
        elif total > target + avg_seq / 2 and n > 1 and (n - 1) not in tried:
            n -= 1
        else:
            break
        if recipe.target_count and n > recipe.target_count:
            break
    return best


# ---------------------------------------------------------------- julkinen rajapinta

def arrange(tracks: list[Track], recipe: Recipe) -> list[Track]:
    """Järjestää ja rajaa suodatetut kappaleet reseptin mukaan."""
    mode = recipe.sort_mode
    if mode == "harmonic":
        return _sequence_with_limits(
            tracks,
            recipe,
            lambda pool, n: _harmonic_cost_factory(pool, n, recipe.harmonic_bpm_direction),
        )
    if mode == "energy_arc":
        return _sequence_with_limits(
            tracks, recipe, lambda pool, n: _energy_cost_factory(pool, n, recipe)
        )
    out = list(tracks)
    if mode in _SIMPLE_KEYS:
        out.sort(key=_SIMPLE_KEYS[mode], reverse=recipe.sort_descending)
    elif recipe.sort_descending:
        out.reverse()
    return _limit_simple(out, recipe)


def transition_quality(prev: Track | None, cur: Track) -> str:
    """Siirtymän merkki esikatseluun: ✓ hyvä, ~ kohtuullinen, ✗ riitasointuinen."""
    if prev is None:
        return ""
    d = key_distance(prev.camelot, cur.camelot)
    if prev.camelot is None or cur.camelot is None:
        mark = "?"
    elif d <= 1:
        mark = "✓"
    elif d <= 2:
        mark = "~"
    else:
        mark = "✗"
    delta = cur.bpm - prev.bpm
    return f"{mark} {delta:+.1f}"
