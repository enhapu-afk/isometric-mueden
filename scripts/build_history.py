"""Langlingen früher: a short tour of the public history, as an overlay for the viewer.

Texts are written for this map from the village articles, the church page and the
listed-building record. Photos are Wikimedia Commons files with an open licence
(CC BY-SA), downloaded once and published with a credit. A missing photo does not
stop the build.

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

WIKI = "https://de.wikipedia.org/wiki/Langlingen"
CHURCH = "https://de.wikipedia.org/wiki/St._Johannis_(Langlingen)"
MANOR = "https://de.wikipedia.org/wiki/Rittergut_Langlingen"
KIRCHE = "https://kirche-langlingen.wir-e.de/aktuelles"

# Coordinates are WGS84. Stops that depend on the river or the railway take their
# point from landmarks.json, which found them in OpenStreetMap.
STOPS = [
    {
        "year": "1257",
        "title": "Langlingen",
        "latlon": (52.556418, 10.288447),
        "zoom": 0.28,
        "text": "1257 steht der Ort zum ersten Mal in einer Urkunde, als Langelege. Die Herren von Meinersen hielten hier einen Hof und den Hof Stegemann, dazu eine Fischerei in der Aller, als Lehen von Braunschweig-Lüneburg. Der Name lief über Langlingen zu der Form, die das Dorf heute trägt.",
        "source": ("Wikipedia", WIKI),
        "more": WIKI,
    },
    {
        "year": "1338",
        "title": "St. Johannis",
        "latlon": (52.556418, 10.288447),
        "h": 12,
        "text": "Die Pfarrei wurde 1257 von Wienhausen getrennt. Im alten Chor saß ein Stein mit der Jahreszahl 1338. 1668 kamen ein hölzerner Anbau im Westen und ein verschalter Dachreiter dazu, 1783 erneuert. Von 1994 bis 1996 legte eine Ausbesserung den gemalten Engelhimmel an der Decke wieder frei.",
        "photos": [
            ("Kirche Langlingen.jpg", "St. Johannis, Clemensfranz, CC BY-SA 3.0"),
            ("Kirche Langlingen 1.jpg", "St. Johannis, ClausNe, CC BY-SA 4.0"),
        ],
        "source": ("Wikipedia", CHURCH),
        "more": KIRCHE,
    },
    {
        "year": "1619",
        "title": "Fachwerk an der Hauptstraße",
        "latlon": (52.5552536, 10.2876928),
        "h": 7,
        "text": "An der Hauptstraße steht ein Wohn- und Wirtschaftsgebäude von 1619, in Fachwerk, und ein Stück weiter eines von 1776. Beide sind eingetragene Baudenkmale. Das Dorfmuseum sitzt dazwischen, in der Nummer 44.",
        "source": ("Denkmalatlas Niedersachsen", "https://denkmalatlas.niedersachsen.de/"),
        "more": WIKI,
    },
    {
        "year": "1725",
        "title": "Rittergut",
        "latlon": (52.557263, 10.288209),
        "h": 10,
        "text": "Ernst Wilhelm von Spörcken ließ 1725 das barocke Herrenhaus bauen: Fachwerk unter Putz, Mansarddach, ein Türmchen auf dem rechten Flügel. Die Familie hatte das Gut seit dem 14. Jahrhundert. 1827 kaufte der Pächter Mylius es, und die Familie bewirtschaftet es noch. Der Park am Franzosengraben ist nicht öffentlich.",
        "photos": [("Gutshof Langlingen.jpg", "Rittergut Langlingen, Clemensfranz, CC BY-SA 3.0")],
        "source": ("Wikipedia", MANOR),
        "more": MANOR,
    },
    {
        "year": "1981",
        "title": "Der Bahnhof",
        "place": "Alter Bahnhof",
        "h": 3,
        "zoom": 0.7,
        "text": "Langlingen lag an der Bahn von Gifhorn Stadt nach Celle. Der Personenverkehr endete 1981. Der Damm liegt noch im Gelände.",
        "source": ("Wikipedia", WIKI),
        "more": WIKI,
    },
    {
        "year": "heute",
        "title": "Langlingen heute",
        "latlon": (52.556418, 10.288447),
        "zoom": 0.35,
        "text": "Ein Dorf an der Aller, Gemeinde im Landkreis Celle, seit 1998 mit Czarne in Polen verbunden. Ende der Rundfahrt. Was nur die Leute hier wissen, fehlt noch: das Fest, die Badestelle, der Name der Eiche.",
        "source": ("Wikipedia", WIKI),
        "more": WIKI,
    },
]


def download(url, tries=6):
    req = urllib.request.Request(url, headers={"User-Agent": "isometric-langlingen/0.1 (personal map)"})
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
