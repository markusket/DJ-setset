"""Kappaleiden suodatus reseptin ehtojen mukaan."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, Iterable

from .keys import compatible_keys, to_camelot
from .library import Track
from .recipe import Recipe


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _words(s: str) -> list[str]:
    return [w for w in _norm(s).split() if w]


def _bpm_ok(bpm: float, lo: float | None, hi: float | None, half_double: bool) -> bool:
    candidates = [bpm]
    if half_double and bpm > 0:
        candidates += [bpm * 2, bpm / 2]
    for b in candidates:
        if (lo is None or b >= lo - 1e-6) and (hi is None or b <= hi + 1e-6):
            return True
    return False


def expand_keys(recipe: Recipe) -> set[str]:
    keys = {k for k in (to_camelot(x) for x in recipe.keys) if k}
    if recipe.keys_compatible or recipe.keys_compatible_extended:
        extended = recipe.keys_compatible_extended
        out: set[str] = set()
        for k in keys:
            out |= compatible_keys(k, extended=extended)
        keys = out
    return keys


def build_predicates(recipe: Recipe, today: date | None = None) -> list[Callable[[Track], bool]]:
    r = recipe
    preds: list[Callable[[Track], bool]] = []

    if r.bpm_min is not None or r.bpm_max is not None:
        preds.append(lambda t: _bpm_ok(t.bpm, r.bpm_min, r.bpm_max, r.bpm_half_double))

    if r.keys:
        keys = expand_keys(r)
        preds.append(lambda t: t.camelot in keys)

    if r.genres_include:
        gi = {_norm(g) for g in r.genres_include}
        preds.append(lambda t: _norm(t.genre) in gi)
    if r.genres_exclude:
        ge = {_norm(g) for g in r.genres_exclude}
        preds.append(lambda t: _norm(t.genre) not in ge)

    if r.rating_min is not None:
        preds.append(lambda t: t.rating >= r.rating_min)
    if r.rating_max is not None:
        preds.append(lambda t: t.rating <= r.rating_max)

    if r.colours_include:
        ci = {_norm(c) for c in r.colours_include}
        preds.append(lambda t: _norm(t.colour) in ci)
    if r.colours_exclude:
        ce = {_norm(c) for c in r.colours_exclude}
        preds.append(lambda t: _norm(t.colour) not in ce)

    if r.comment_contains.strip():
        cw = _words(r.comment_contains)
        preds.append(lambda t: all(w in _norm(t.comment) for w in cw))
    if r.comment_excludes.strip():
        cx = _words(r.comment_excludes)
        preds.append(lambda t: not any(w in _norm(t.comment) for w in cx))

    if r.mytags_include:
        ti = {_norm(x) for x in r.mytags_include}
        if r.mytags_include_mode == "all":
            preds.append(lambda t: ti <= {_norm(x) for x in t.mytags})
        else:
            preds.append(lambda t: bool(ti & {_norm(x) for x in t.mytags}))
    if r.mytags_exclude:
        tx = {_norm(x) for x in r.mytags_exclude}
        preds.append(lambda t: not (tx & {_norm(x) for x in t.mytags}))

    if r.year_min is not None:
        preds.append(lambda t: t.year is not None and t.year >= r.year_min)
    if r.year_max is not None:
        preds.append(lambda t: t.year is not None and t.year <= r.year_max)

    d_from = date.fromisoformat(r.added_from) if r.added_from else None
    d_to = date.fromisoformat(r.added_to) if r.added_to else None
    if r.added_last_days:
        since = (today or date.today()) - timedelta(days=r.added_last_days)
        d_from = max(d_from, since) if d_from else since
    if d_from:
        preds.append(lambda t: t.date_added is not None and t.date_added >= d_from)
    if d_to:
        preds.append(lambda t: t.date_added is not None and t.date_added <= d_to)

    if r.duration_min is not None:
        preds.append(lambda t: t.duration >= r.duration_min)
    if r.duration_max is not None:
        preds.append(lambda t: t.duration <= r.duration_max)

    if r.play_count_min is not None:
        preds.append(lambda t: t.play_count >= r.play_count_min)
    if r.play_count_max is not None:
        preds.append(lambda t: t.play_count <= r.play_count_max)

    def haystack(t: Track) -> str:
        return " ".join((t.artist, t.name, t.album, t.remixer, t.label)).lower()

    if r.text_search.strip():
        sw = _words(r.text_search)
        preds.append(lambda t: all(w in haystack(t) for w in sw))
    if r.text_exclude.strip():
        sx = _words(r.text_exclude)
        preds.append(lambda t: not any(w in haystack(t) for w in sx))

    if r.manual_exclude:
        mx = set(r.manual_exclude)
        preds.append(lambda t: t.location not in mx)

    return preds


def apply_filters(tracks: Iterable[Track], recipe: Recipe, today: date | None = None) -> list[Track]:
    preds = build_predicates(recipe, today)
    return [t for t in tracks if all(p(t) for p in preds)]
