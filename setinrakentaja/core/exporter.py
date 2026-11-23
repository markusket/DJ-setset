"""Soittolistojen vienti uutena rekordbox.xml-tiedostona.

Rakenne vastaa Rekordboxin omaa XML-vientiä:

<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="..." Company="..."/>
  <COLLECTION Entries="N">
    <TRACK ... (alkuperäinen elementti kopioituna muuttumattomana) />
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="0" Name="ROOT" Count="..">
      <NODE Type="0" Name="Kansio" Count="..">
        <NODE Name="Lista" Type="1" KeyType="0" Entries="..">
          <TRACK Key="TrackID"/>
"""

from __future__ import annotations

import copy
import os
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .library import Library, Track


class ExportError(Exception):
    pass


@dataclass
class ExportPlaylist:
    name: str
    tracks: list[Track]
    folder: str = ""  # "Kansio/Alikansio"

    @property
    def folder_parts(self) -> list[str]:
        return [p.strip() for p in self.folder.replace("\\", "/").split("/") if p.strip()]


@dataclass
class _Folder:
    name: str
    folders: dict[str, "_Folder"] = field(default_factory=dict)
    items: list = field(default_factory=list)  # järjestyksessä: _Folder tai ExportPlaylist


def _build_tree(playlists: list[ExportPlaylist]) -> _Folder:
    root = _Folder("ROOT")
    for pl in playlists:
        node = root
        for part in pl.folder_parts:
            if part not in node.folders:
                f = _Folder(part)
                node.folders[part] = f
                node.items.append(f)
            node = node.folders[part]
        node.items.append(pl)
    return root


def _emit(parent_el: ET.Element, folder: _Folder) -> None:
    for item in folder.items:
        if isinstance(item, _Folder):
            el = ET.SubElement(
                parent_el, "NODE", {"Type": "0", "Name": item.name, "Count": str(len(item.items))}
            )
            _emit(el, item)
        else:
            el = ET.SubElement(
                parent_el,
                "NODE",
                {
                    "Name": item.name,
                    "Type": "1",
                    "KeyType": "0",
                    "Entries": str(len(item.tracks)),
                },
            )
            for t in item.tracks:
                ET.SubElement(el, "TRACK", {"Key": t.track_id})


def build_xml(library: Library, playlists: list[ExportPlaylist]) -> ET.ElementTree:
    root = ET.Element("DJ_PLAYLISTS", {"Version": "1.0.0"})
    ET.SubElement(
        root,
        "PRODUCT",
        {
            "Name": library.product_name or "rekordbox",
            "Version": library.product_version or "7.0.0",
            "Company": library.product_company or "AlphaTheta",
        },
    )

    # Kokoelmaan vain soittolistoilla esiintyvät kappaleet, kukin kerran.
    used: dict[str, Track] = {}
    for pl in playlists:
        for t in pl.tracks:
            used.setdefault(t.track_id, t)
    coll = ET.SubElement(root, "COLLECTION", {"Entries": str(len(used))})
    for t in used.values():
        coll.append(copy.deepcopy(t.element))

    pls = ET.SubElement(root, "PLAYLISTS")
    tree = _build_tree(playlists)
    root_node = ET.SubElement(pls, "NODE", {"Type": "0", "Name": "ROOT", "Count": str(len(tree.items))})
    _emit(root_node, tree)

    ET.indent(root, space="  ")
    return ET.ElementTree(root)


def _same_file(a: Path, b: Path) -> bool:
    try:
        if a.exists() and b.exists():
            return os.path.samefile(a, b)
    except OSError:
        pass
    return a.resolve() == b.resolve()


def export_xml(
    library: Library,
    playlists: list[ExportPlaylist],
    out_path: str | Path,
    overwrite: bool = False,
) -> Path:
    """Kirjoittaa soittolistat uuteen XML-tiedostoon.

    Kieltäytyy kirjoittamasta alkuperäisen kirjastotiedoston päälle aina.
    Olemassa olevan muun tiedoston päälle kirjoitetaan vain, jos overwrite=True.
    """
    out_path = Path(out_path)
    if not playlists:
        raise ExportError("Ei vietäviä soittolistoja.")
    if any(not pl.tracks for pl in playlists):
        empty = ", ".join(pl.name for pl in playlists if not pl.tracks)
        raise ExportError(f"Tyhjiä soittolistoja ei voi viedä: {empty}")
    if _same_file(out_path, Path(library.path)):
        raise ExportError(
            "Alkuperäisen kirjastotiedoston päälle ei kirjoiteta. Valitse uusi tiedostonimi."
        )
    if out_path.exists() and not overwrite:
        raise ExportError(f"Tiedosto on jo olemassa: {out_path}")

    tree = build_xml(library, playlists)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Kirjoitus ensin väliaikaistiedostoon, jotta keskeytys ei jätä rikkinäistä tiedostoa.
    fd, tmp = tempfile.mkstemp(prefix=".setinrakentaja-", suffix=".xml", dir=out_path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            tree.write(f, encoding="UTF-8", xml_declaration=False)
            f.write(b"\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, out_path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return out_path
