"""Ettenbüttel früher: a short tour of the public record, as an overlay for the viewer.

Texts are written for this map from the municipality's articles and the
Niedersachsen monument register. Photos are Wikimedia Commons files with an open
licence, downloaded once and published with a credit. A missing photo does not
stop the build. St. Petri stands in the Kernort, off this sheet, so it is not a stop.

Output: data/build/history.json and data/build/history/*.jpg
"""

import hashlib
import json
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

from config import BUILD
from geo import wgs_to_rd

WIKI = "https://de.wikipedia.org/wiki/Ettenb%C3%BCttel"
MUEDEN = "https://de.wikipedia.org/wiki/M%C3%BCden_(Aller)"
DENKMAL = "https://denkmalatlas.niedersachsen.de/viewer/metadata"

# Coordinates are WGS84. Building stops take their point from landmarks.json.
STOPS = [
    {
        "year": "1974",
        "title": "Ettenbüttel",
        "latlon": (52.500937, 10.408575),
        "zoom": 0.28,
        "text": "Ettenbüttel ist ein Ortsteil von Müden (Aller) im Landkreis Gifhorn, südöstlich des Kernorts. Am 1. März 1974 wurde es mit Dieckhorst, Flettmar und Hahnenhorn nach Müden eingemeindet. Am 1. Mai 2024 lebten hier 644 Menschen. 1668 notierte der Müder Pastor Heinrich Hoffmann, die Einwohner von Ettenbüttel zahlten noch den Zehnten, weil der Ort früher zur Pfarrei Müden gehört hatte. St. Petri, die Kirche des Kernorts, liegt etwa fünf Kilometer nordwestlich und nicht auf diesem Blatt.",
        "photos": [("Ettenbüttel W.jpg", "Ettenbüttel, Kirchenfan, CC0")],
        "source": ("Wikipedia", WIKI),
        "more": MUEDEN,
    },
    {
        "year": "Baudenkmal",
        "title": "Allertal 15",
        "place": "Allertal 15",
        "h": 8,
        "text": "An der Allertal 15, der Landesstraße durch Ettenbüttel, steht ein eingeschossiges Vierständer-Hallenhaus mit Ziegelausfachung und Krüppelwalmdach, die Einfahrt in der Mitte der Längsseite. Es ist ein eingetragenes Baudenkmal. Wann es gebaut wurde, sagt diese Karte nicht.",
        "photos": [("Ettenbüttel Allertal 15 NLD 33934218.jpg", "Allertal 15, Simone Thulke, CC BY 4.0")],
        "source": ("Denkmalatlas Niedersachsen", f"{DENKMAL}/33934218/1/-/"),
        "more": f"{DENKMAL}/33934218/1/-/",
    },
    {
        "year": "Baudenkmal",
        "title": "Hirtenwinkel 4",
        "place": "Hirtenwinkel 4",
        "h": 8,
        "text": "Hirtenwinkel 4 ist ebenfalls ein Vierständer-Hallenhaus, mit Ziegelausfachung unter einem Halbwalmdach und einem quergestellten Stallanbau. Eingetragenes Baudenkmal.",
        "photos": [("Ettenbüttel Hirtenwinkel 04 NLD 33934242.jpg", "Hirtenwinkel 4, Simone Thulke, CC BY 4.0")],
        "source": ("Denkmalatlas Niedersachsen", f"{DENKMAL}/33934242/1/-/"),
        "more": f"{DENKMAL}/33934242/1/-/",
    },
    {
        "year": "Baudenkmal",
        "title": "Speicher Bokelberge",
        "place": "Speicher Bokelberge",
        "h": 8,
        "text": "In Bokelberge, nördlich von Ettenbüttel, steht ein zweigeschossiger Fachwerkspeicher mit vorkragendem Obergeschoss unter einem Satteldach. Eingetragenes Baudenkmal.",
        "photos": [("Ettenbüttel Bockelberg 02 NLD 33934711.jpg", "Speicher Bokelberge, Simone Thulke, CC BY 4.0")],
        "source": ("Denkmalatlas Niedersachsen", f"{DENKMAL}/33934711/1/-/"),
        "more": f"{DENKMAL}/33934711/1/-/",
    },
    {
        "year": "heute",
        "title": "Ettenbüttel heute",
        "place": "Grüne Heide 18",
        "zoom": 0.45,
        "text": "Die Karte öffnet am Wohnhaus Grüne Heide 18. Auf diesem Blatt liegen Ettenbüttel, die Grüne Heide und Bokelberge. Der Kernort Müden mit St. Petri liegt etwa fünf Kilometer nordwestlich, außerhalb. Was nur die Leute hier wissen, fehlt noch: das Fest, die Badestelle, die Namen der Höfe.",
        "source": ("Wikipedia", WIKI),
        "more": WIKI,
    },
]


def download(url, tries=6):
    req = urllib.request.Request(url, headers={"User-Agent": "isometric-mueden/0.1 (personal map)"})
    for attempt in range(tries):
        try:
            data = urllib.request.urlopen(req, timeout=60).read()
            time.sleep(2)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < tries - 1:
                time.sleep(15 * (attempt + 1))
                continue
            raise


def fetch_photo(name):
    """Ask Commons for a thumbnail. Guessing the pixel width gets a 400: only listed sizes exist."""
    q = urllib.parse.urlencode(
        {
            "action": "query",
            "titles": f"File:{name}",
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": 960,
            "format": "json",
        }
    )
    try:
        raw = download("https://commons.wikimedia.org/w/api.php?" + q)
        pages = json.loads(raw).get("query", {}).get("pages", {})
    except (urllib.error.HTTPError, json.JSONDecodeError, TimeoutError) as e:
        print(f"photo {name}: {e}")
        return None
    for page in pages.values():
        info = (page.get("imageinfo") or [None])[0]
        thumb = info and (info.get("thumburl") or info.get("url"))
        if not thumb:
            print(f"photo {name}: not on Commons")
            return None
        try:
            return download(thumb)
        except urllib.error.HTTPError as e:
            print(f"photo {name}: {e}")
            return None
    return None


def place_xy(name):
    path = BUILD / "landmarks.json"
    if not path.exists():
        return None
    for p in json.loads(path.read_text())["places"]:
        if p["name"] == name:
            return p["x"], p["y"]
    return None


def route_order(stops):
    """Nearest-neighbour from the first stop, the last one staying last. Stops on the same spot keep their year."""
    if len(stops) < 3:
        return stops
    first, last, middle = stops[0], stops[-1], stops[1:-1]
    dist = lambda a, b: ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5
    path, todo = [first], middle[:]
    while todo:
        nxt = min(todo, key=lambda s: (dist(path[-1], s), stops.index(s)))
        path.append(nxt)
        todo.remove(nxt)
    path.append(last)
    improved = True
    while improved:
        improved = False
        for i in range(1, len(path) - 2):
            for j in range(i + 1, len(path) - 1):
                before = dist(path[i - 1], path[i]) + dist(path[j], path[j + 1])
                after = dist(path[i - 1], path[j]) + dist(path[i], path[j + 1])
                if after < before - 0.01:
                    path[i : j + 1] = path[i : j + 1][::-1]
                    improved = True
    i = 0
    while i < len(path):
        j = i
        while j + 1 < len(path) - 1 and i > 0 and dist(path[j + 1], path[i]) < 40:
            j += 1
        year = lambda st: int(m.group()) if (m := re.search(r"\d{4}", st["year"])) else 9999
        path[i : j + 1] = sorted(path[i : j + 1], key=lambda st: (year(st), stops.index(st)))
        i = j + 1
    return path


def main():
    out_dir = BUILD / "history"
    out_dir.mkdir(parents=True, exist_ok=True)
    stops = []
    for i, s in enumerate(STOPS, start=1):
        if "place" in s:
            xy = place_xy(s["place"])
            if xy is None:
                print(f"skip {s['title']}: {s['place']} is not on the map")
                continue
            x, y = xy
        else:
            x, y = wgs_to_rd(*s["latlon"])
        stop = {
            "n": i,
            "year": s["year"],
            "title": s["title"],
            "text": s["text"],
            "x": round(x, 1),
            "y": round(y, 1),
            "h": s.get("h", 0),
            "zoom": s.get("zoom", 1.2),
            "source": {"label": s["source"][0], "url": s["source"][1]},
            "more": s.get("more"),
            "photos": [],
        }
        for k, (name, credit) in enumerate(s.get("photos") or []):
            dst = out_dir / f"{i:02d}_{k}.jpg"
            if not dst.exists():
                data = fetch_photo(name)
                if not data:
                    continue
                dst.write_bytes(data)
                subprocess.run(["magick", str(dst), "-resize", "640x640>", "-quality", "82", str(dst)], check=True)
            stop["photos"].append(
                {
                    "src": f"history/{dst.name}",
                    "credit": credit,
                    "url": f"https://commons.wikimedia.org/wiki/File:{urllib.parse.quote(name)}",
                }
            )
        stops.append(stop)
    stops = route_order(stops)
    for n, stop in enumerate(stops, start=1):
        stop["n"] = n
    blobs = [f.read_bytes() for f in sorted(out_dir.glob("*.jpg"))]
    version = hashlib.md5(b"".join(blobs)).hexdigest()[:8] if blobs else "0"
    for stop in stops:
        for ph in stop["photos"]:
            ph["src"] += f"?v={version}"
    (BUILD / "history.json").write_text(json.dumps({"stops": stops}, ensure_ascii=False, indent=1))
    print(f"{len(stops)} stops, {sum(len(s['photos']) for s in stops)} photos")


if __name__ == "__main__":
    main()
