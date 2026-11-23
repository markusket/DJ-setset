"""Luo tests/data/esimerkki_rekordbox.xml (kuvitteelliset kappaleet, Rekordbox 7 -muoto)."""
import random
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import quoteattr

random.seed(7)
GENRES = ["Deep House", "Tech House", "Techno", "Melodic Techno", "Disco", "Afro House"]
KEYS = ["Am", "Em", "Bm", "F#m", "Dbm", "Abm", "Ebm", "Bbm", "Fm", "Cm", "Gm", "Dm",
        "C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F"]
COLOURS = ["", "", "0xFF007F", "0xFF0000", "0xFFA500", "0xFFFF00", "0x00FF00", "0x25FDE9", "0x0000FF", "0x660099"]
ARTISTS = ["Aurora Väinö", "Kalle & Kide", "Nightshift Collective", "Mira Saaristo", "DJ Pohjoistuuli",
           "Lumo", "Signal/Noise", "The Ström Unit", "Kaiku", "Örkki Beats"]
WORDS = ["Yö", "Valo", "Pulse", "Drift", "Neon", "Kuu", "Rise", "Deep", "Groove", "Halo", "Sauna", "Aalto"]
TAGS = ["Peak Time", "Warm Up", "Vocal", "Closing", "Groovy", "Dark"]

lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<DJ_PLAYLISTS Version="1.0.0">',
         '  <PRODUCT Name="rekordbox" Version="7.0.4" Company="AlphaTheta"/>']
tracks = []
for i in range(1, 61):
    artist = random.choice(ARTISTS)
    name = f"{random.choice(WORDS)} {random.choice(WORDS)}" + (" (Extended Mix)" if i % 3 == 0 else "")
    genre = GENRES[i % len(GENRES)]
    bpm = {"Deep House": 120, "Tech House": 125, "Techno": 132, "Melodic Techno": 123,
           "Disco": 116, "Afro House": 122}[genre] + random.randint(-3, 4) + random.choice([0, 0.5])
    folder = genre.replace(" ", "_")
    filename = f"{artist} - {name}.{'mp3' if i % 4 else 'aiff'}"
    loc = "file://localhost" + quote(f"/Users/dj/Music/{folder}/{filename}", safe="/")
    comment_bits = []
    if i % 5 == 0:
        comment_bits.append("Hyvä breikki")
    if i % 2 == 0:
        tags = random.sample(TAGS, 2)
        comment_bits.append("/* " + " / ".join(tags) + " */")
    if i % 7 == 0:
        comment_bits.append(f"Energy {random.randint(3, 10)}")
    attrs = {
        "TrackID": str(10000000 + i * 137), "Name": name, "Artist": artist, "Composer": "",
        "Album": "", "Grouping": "", "Genre": genre, "Kind": "MP3 File" if i % 4 else "AIFF File",
        "Size": str(random.randint(8_000_000, 25_000_000)), "TotalTime": str(random.randint(240, 480)),
        "DiscNumber": "0", "TrackNumber": "0", "Year": str(random.choice([0, 2018, 2020, 2022, 2023, 2024, 2025])),
        "AverageBpm": f"{bpm:.2f}", "DateAdded": f"202{random.randint(3,6)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        "BitRate": "320", "SampleRate": "44100", "Comments": " ".join(comment_bits),
        "PlayCount": str(random.choice([0, 0, 1, 2, 5, 12, 30])), "Rating": str(random.choice([0, 51, 102, 153, 204, 255])),
        "Location": loc, "Remixer": "", "Tonality": random.choice(KEYS), "Label": "Kuvitteellinen Levy-yhtiö",
        "Mix": "", "Colour": random.choice(COLOURS),
    }
    attrs = {k: v for k, v in attrs.items() if not (k == "Colour" and v == "")}
    tracks.append(attrs)

lines.append(f'  <COLLECTION Entries="{len(tracks)}">')
for a in tracks:
    s = " ".join(f"{k}={quoteattr(v)}" for k, v in a.items())
    lines.append(f"    <TRACK {s}>")
    lines.append(f'      <TEMPO Inizio="0.025" Bpm="{a["AverageBpm"]}" Metro="4/4" Battito="1"/>')
    lines.append('      <POSITION_MARK Name="" Type="0" Start="0.025" Num="0" Red="40" Green="226" Blue="20"/>')
    lines.append("    </TRACK>")
lines.append("  </COLLECTION>")
lines += ['  <PLAYLISTS>', '    <NODE Type="0" Name="ROOT" Count="1">',
          '      <NODE Name="Vanha lista" Type="1" KeyType="0" Entries="2">',
          f'        <TRACK Key="{tracks[0]["TrackID"]}"/>', f'        <TRACK Key="{tracks[1]["TrackID"]}"/>',
          '      </NODE>', '    </NODE>', '  </PLAYLISTS>', '</DJ_PLAYLISTS>', '']
out = Path(__file__).parent / "data" / "esimerkki_rekordbox.xml"
out.write_text("\n".join(lines), encoding="utf-8")
print(out)
