"""Reseptistä valmiiksi soittolistaksi."""

from __future__ import annotations

from datetime import date

from .exporter import ExportPlaylist
from .filters import apply_filters
from .library import Library, Track
from .recipe import Recipe
from .sequencing import arrange


def build_tracks(library: Library, recipe: Recipe, today: date | None = None) -> list[Track]:
    return arrange(apply_filters(library.tracks, recipe, today), recipe)


def build_playlist(library: Library, recipe: Recipe, today: date | None = None) -> ExportPlaylist:
    return ExportPlaylist(
        name=recipe.name, folder=recipe.folder, tracks=build_tracks(library, recipe, today)
    )
