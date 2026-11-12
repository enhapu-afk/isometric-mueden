# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
"""Named places of Langlingen: colours and type for a few buildings, and the viewer's place list.

The stories are the public ones: the church and the manor from the village's own
pages and the listed-building record, the dates on the timber houses from the
Niedersachsen monument register. Anything only a neighbour would know is left
out on purpose.

Output: data/build/landmarks.json
"""

import json

import numpy as np

from citygml import load_buildings
from config import BUILD, RAW, XMAX, XMIN, YMAX, YMIN
from geo import wgs_to_rd

# Brick and dark slate for St. Johannis, cream plaster for the manor. The other
# roofs take their colour from the aerial photo.
CHURCH_WALL, CHURCH_ROOF = (148, 72, 58), (70, 74, 80)
MANOR_WALL, MANOR_ROOF = (232, 224, 206), (72, 68, 64)
FRAME_WALL, FRAME_TIMBER = (228, 214, 190), (92, 64, 44)

BUILDINGS = [
    {
        "name": "St. Johannis",
        "note": "Backsteinkirche mit Dachreiter",
        "kind": "Kirche · seit 1257",
        "latlon": (52.556418, 10.288447),
        "style": "church",
        "wall": CHURCH_WALL,
        "roof": CHURCH_ROOF,
        "text": "Die Pfarrei wurde 1257 von der Mutterkirche in Wienhausen getrennt. Im alten Chor saß ein Stein mit der Jahreszahl 1338. 1668 kamen ein hölzerner Anbau im Westen und ein verschalter Dachreiter dazu, 1783 erneuert, mit einer achteckigen Schieferhaube. Bei der Ausbesserung von 1994 bis 1996 kam unter der Decke ein gemalter Engelhimmel wieder zum Vorschein. Der Altar ist von 1675, die Kanzel von 1670, die Orgel ein Werk von Furtwängler aus dem Jahr 1854.",
        "web": "https://kirche-langlingen.wir-e.de/aktuelles",
        "more": "https://de.wikipedia.org/wiki/St._Johannis_(Langlingen)",
        "stop": "St. Johannis",
    },
    {
        "name": "Rittergut Langlingen",
        "note": "Herrenhaus von 1725",
        "kind": "Herrenhaus · 1725",
        "latlon": (52.557263, 10.288209),
        "style": "house",
        "wall": MANOR_WALL,
        "roof": MANOR_ROOF,
        "text": "Das barocke Herrenhaus ließ Ernst Wilhelm von Spörcken 1725 bauen: zwei Geschosse, elf Achsen, Fachwerk, das unter dem Putz wie Stein wirken sollte, mit Mansarddach und einem Türmchen auf dem rechten Flügel. Die von Spörcken hatten das Gut seit dem 14. Jahrhundert. 1827 kaufte es der Pächter Anton Ludwig Wilhelm Mylius, und die Familie Mylius bewirtschaftet es noch. Der Park nördlich des Hauses, am Franzosengraben, ist nicht öffentlich.",
        "more": "https://de.wikipedia.org/wiki/Rittergut_Langlingen",
        "stop": "Rittergut",
    },
    {
        "name": "Hauptstraße 46",
        "note": "Wohn- und Wirtschaftsgebäude",
        "kind": "Fachwerk · 1619",
        "addr": "Hauptstraße 46",
        "style": "house",
        "wall": FRAME_WALL,
        "frame": FRAME_TIMBER,
        "text": "Ein Wohn- und Wirtschaftsgebäude von 1619, in Fachwerk, und ein eingetragenes Baudenkmal. Es gehört zu den ältesten Häusern, die im Dorf noch stehen.",
        "stop": "Fachwerk an der Hauptstraße",
    },
    {
        "name": "Hauptstraße 54",
        "note": "Fachwerkhaus",
        "kind": "Fachwerk · 1776",
        "addr": "Hauptstraße 54",
        "style": "house",
        "wall": FRAME_WALL,
        "frame": FRAME_TIMBER,
        "text": "Fachwerkhaus von 1776, ebenfalls eingetragenes Baudenkmal, ein Stück weiter die Hauptstraße hinunter.",
    },
    {
        "name": "Dorfmuseum",
        "note": "Hauptstraße 44",
        "kind": "Museum",
        "addr": "Hauptstraße 44",
        "style": "house",
        "wall": FRAME_WALL,
        "frame": FRAME_TIMBER,
        "text": "Das Dorfmuseum in der Hauptstraße 44 sammelt, was vom alten Langlingen geblieben ist. Was in den Vitrinen liegt, wissen die Leute hier besser als diese Karte.",
        "stop": "Dorfmuseum",
    },
    {
        "name": "allerHaus",
        "note": "Kirchstraße 1",
        "kind": "Pfarrhaus · 1878",
        "addr": "Kirchstraße 1",
        "style": "house",
        "wall": (214, 206, 190),
        "roof": (120, 72, 56),
        "text": "An der Kirchstraße 1 stehen das Pfarrhaus von 1878 und die Scheune von etwa 1880, die heute das Gemeindehaus ist. Im Dorf heißt das Ensemble allerHaus.",
        "web": "https://www.allerhaus.de",
    },
    {
        "name": "Ehemaliges Küsterhaus",
        "note": "Kirchstraße 3",
        "kind": "Küsterhaus · 1911",
        "addr": "Kirchstraße 3",
        "style": "house",
        "wall": (220, 214, 200),
        "text": "1911 als Wohnung für den Küster und den Lehrer gebaut. Heute ist hier ein Gesundheitszentrum.",
    },
    {
        "name": "Grundschule Langlingen",
        "note": "Bahnhofstraße 6",
        "kind": "Grundschule",
        "addr": "Bahnhofstraße 6",
        "style": "school",
        "wall": (222, 216, 202),
        "text": "Die Grundschule des Dorfs, Bahnhofstraße 6. Wann sie gegründet wurde und welche Farbe die Fassade wirklich hat, steht hier nicht: das wissen die, die hingegangen sind.",
        "stop": "Die Schule",
    },
]

POINTS = [
    {
        "name": "Freiwillige Feuerwehr",
        "latlon": (52.5558417, 10.2826078),
        "kind": "Feuerwehr",
        "address": "Am Flootgarten",
        "text": "Die Freiwillige Feuerwehr Langlingen, am Flootgarten. Was hier an Einsätzen hängen geblieben ist, erzählt die Wehr selbst besser.",
    },
]

# Filled in from OpenStreetMap once the download is in: the river and the old station have no reliable house number.
RIVER = {
    "name": "Aller",
    "kind": "Fluss",
    "text": "Die Aller fließt nördlich am Dorf vorbei. Schon die erste Erwähnung Langlingens, 1257, nennt zu einem Hof der Herren von Meinersen eine Fischerei in der Aller, die visweyde.",
    "stop": "An der Aller",
}
STATION = {
    "name": "Alter Bahnhof",
    "kind": "Bahnstrecke · Personenverkehr bis 1981",
    "text": "Langlingen lag an der Bahn von Gifhorn Stadt nach Celle. Der Personenverkehr endete 1981. Der Damm ist im Gelände noch zu sehen; die Züge fahren hier nicht mehr.",
    "stop": "Der Bahnhof",
}

CATEGORIES = [
    ("kirche", "Kirche und Gut", ["St. Johannis", "Rittergut Langlingen", "allerHaus", "Ehemaliges Küsterhaus"]),
    ("dorf", "Fachwerk und Museum", ["Hauptstraße 46", "Dorfmuseum", "Hauptstraße 54", "Grundschule Langlingen"]),
    ("flur", "Am Fluss und an der Bahn", ["Aller", "Alter Bahnhof", "Freiwillige Feuerwehr"]),
]

INFO = ("note", "kind", "text", "address", "web", "more", "photo", "stop")

# amenity or tourism tag -> a one-line label. Only for places OSM actually names.
TAG_KIND = {
    "place_of_worship": "Kirche",
    "school": "Schule",
    "kindergarten": "Kindergarten",
    "fire_station": "Feuerwehr",
    "townhall": "Gemeinde",
    "community_centre": "Gemeindehaus",
    "library": "Bibliothek",
    "police": "Polizei",
    "doctors": "Arztpraxis",
    "pharmacy": "Apotheke",
    "bank": "Bank",
    "post_office": "Post",
    "cafe": "Café",
    "restaurant": "Gaststätte",
    "pub": "Gaststätte",
    "fast_food": "Imbiss",
    "bakery": "Bäckerei",
    "supermarket": "Laden",
    "farm": "Hofladen",
    "hotel": "Gasthaus",
    "memorial": "Denkmal",
    "cemetery": "Friedhof",
    "playground": "Spielplatz",
    "sports_centre": "Sport",
    "pitch": "Sportplatz",
    "museum": "Museum",
    "information": "Information",
    "station": "Bahnhof",
    "halt": "Haltepunkt",
}


def point_in_ring(x, y, ring):
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, np.roll(ring, -1, axis=0)):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1:
            inside = not inside
    return inside


def address_xy(name):
    path = RAW / "addresses.json"
    if not path.exists():
        return None
    for x, y, label in json.loads(path.read_text()):
        if label == name or label.startswith(name + " ") or label.split(",")[0].strip() == name:
            return x, y
    return None


def locate(entry):
    if "at" in entry:
        return entry["at"]
    if "latlon" in entry:
        return wgs_to_rd(*entry["latlon"])
    if "addr" in entry:
        return address_xy(entry["addr"])
    return None


def building_at(rings, x, y):
    for rid, ring, height in rings:
        if point_in_ring(x, y, ring):
            return rid, height
    best = None
    for rid, ring, height in rings:
        c = ring.mean(0)
        dist = float(np.hypot(c[0] - x, c[1] - y))
        if best is None or dist < best[0]:
            best = (dist, rid, height)
    if best and best[0] < 18:
        return best[1], best[2]
    return None, None


def rings_of(buildings):
    out = []
    for b in buildings:
        fp = np.asarray(b["footprint"], dtype=np.float64)
        if len(fp) >= 3:
            out.append((b["id"], fp, b["height"]))
    return out


def in_box(x, y):
    return XMIN <= x <= XMAX and YMIN <= y <= YMAX


def aller_point():
    """A point on the Aller inside the map, from the OSM centre-line. None if the river misses the box."""
    path = RAW / "osm_land.json"
    if not path.exists():
        return None
    best = None
    for el in json.loads(path.read_text()).get("elements") or []:
        tags = el.get("tags") or {}
        if tags.get("name") != "Aller" and tags.get("waterway") != "river":
            continue
        if tags.get("name") not in (None, "Aller"):
            continue
        geoms = [el.get("geometry") or []]
        geoms += [m.get("geometry") or [] for m in el.get("members") or []]
        for geom in geoms:
            for p in geom:
                x, y = wgs_to_rd(p["lat"], p["lon"])
                if not in_box(x, y):
                    continue
                # Prefer the stretch due north of the church, where the village meets the meadows.
                score = abs(x - 587350) + max(0, 5823707 - y) * 0.25
                if best is None or score < best[0]:
                    best = (score, x, y)
    return None if best is None else (best[1], best[2])


def station_point():
    """The old station if OSM marks one, otherwise a point on the disused railway near Bahnhofstraße."""
    path = RAW / "osm_landmarks.json"
    if path.exists():
        for el in json.loads(path.read_text()).get("elements") or []:
            tags = el.get("tags") or {}
            if tags.get("railway") not in ("station", "halt"):
                continue
            center = el.get("center") or el
            if "lat" not in center and el.get("geometry"):
                g = el["geometry"]
                center = g[len(g) // 2]
            if "lat" not in center:
                continue
            x, y = wgs_to_rd(center["lat"], center["lon"])
            if in_box(x, y):
                return x, y
    land = RAW / "osm_land.json"
    if not land.exists():
        return None
    # Bahnhofstraße runs south of the church. The nearest rail point to that street is the stop.
    target = address_xy("Bahnhofstraße 6") or (587000, 5823450)
    best = None
    for el in json.loads(land.read_text()).get("elements") or []:
        tags = el.get("tags") or {}
        if tags.get("railway") not in ("rail", "disused", "abandoned", "light_rail"):
            continue
        for p in el.get("geometry") or []:
            x, y = wgs_to_rd(p["lat"], p["lon"])
            if not in_box(x, y):
                continue
            dist = (x - target[0]) ** 2 + (y - target[1]) ** 2
            if best is None or dist < best[0]:
                best = (dist, x, y)
    return None if best is None else (best[1], best[2])


def monument_tree():
    """A named tree or a natural monument, if OSM has one. The famous oak is not pinned without a source."""
    path = RAW / "osm_trees.json"
    if not path.exists():
        return None
    for el in json.loads(path.read_text()).get("elements") or []:
        tags = el.get("tags") or {}
        if not (tags.get("name") or tags.get("denotation") == "natural_monument" or tags.get("monument") == "yes"):
            continue
        if "lat" not in el:
            continue
        x, y = wgs_to_rd(el["lat"], el["lon"])
        if in_box(x, y):
            return x, y, tags
    return None


GENUS = {"Quercus": "Eiche", "Fagus": "Buche", "Tilia": "Linde", "Fraxinus": "Esche"}


def osm_extras(taken):
    """Named OSM places that are not already one of ours, with a label taken from the tag and nothing invented."""
    path = RAW / "osm_landmarks.json"
    if not path.exists():
        return []
    out = []
    for el in json.loads(path.read_text()).get("elements") or []:
        if el.get("type") == "relation":
            continue
        tags = el.get("tags") or {}
        name = tags.get("name")
        # Guideposts and cash machines are not places. A name that is only a digit is a route-board number.
        if not name or name in taken or len(name) < 3 or name.isdigit():
            continue
        if tags.get("tourism") == "information" or tags.get("amenity") == "atm":
            continue
        kind = TAG_KIND.get(
            tags.get("amenity") or tags.get("shop") or tags.get("tourism")
            or tags.get("leisure") or tags.get("historic") or tags.get("railway") or ""
        )
        if tags.get("landuse") == "cemetery":
            kind = kind or "Friedhof"
        if "kapelle" in name.lower():
            kind = "Kapelle"
        if not kind:
            continue
        center = el.get("center") or el
        if "lat" not in center and el.get("geometry"):
            g = el["geometry"]
            center = g[len(g) // 2]
        if "lat" not in center:
            continue
        x, y = wgs_to_rd(center["lat"], center["lon"])
        if not in_box(x, y):
            continue
        if any((x - px) ** 2 + (y - py) ** 2 < 40**2 for px, py in taken.values()):
            continue
        taken[name] = (x, y)
        out.append({"name": name, "x": x, "y": y, "kind": kind, "note": kind})
    return out


def add_place(out, rings, entry, xy):
    x, y = xy
    pid, height = building_at(rings, x, y)
    if entry.get("style") and pid is None:
        print(f"{entry['name']}: no building within 18 m, story kept as a point")
    h = round(float(height or 4), 1)
    out["places"].append({"name": entry["name"], "note": entry.get("note"), "x": x, "y": y, "h": h})
    spot = {"name": entry["name"], "x": x, "y": y, **{k: entry[k] for k in INFO if k in entry}}
    if pid:
        spot["pid"] = pid
        if entry.get("style"):
            out["buildings"][pid] = {k: v for k, v in entry.items() if k not in ("at", "latlon", "addr", *INFO)}
    out["hotspots"].append(spot)
    print(f"{entry['name']}: {pid or 'point'} at {x:.0f},{y:.0f}")


def main():
    rings = rings_of(load_buildings())
    out = {"buildings": {}, "places": [], "masts": [], "hotspots": [], "categories": []}
    taken = {}
    for b in BUILDINGS:
        xy = locate(b)
        if xy is None or not in_box(*xy):
            print(f"{b['name']}: skipped, address not on the map")
            continue
        add_place(out, rings, b, xy)
        taken[b["name"]] = xy

    river = aller_point()
    if river:
        add_place(out, rings, RIVER, river)
        taken[RIVER["name"]] = river
    else:
        print("Aller: not inside this box")
    station = station_point()
    if station:
        add_place(out, rings, STATION, station)
        taken[STATION["name"]] = station
    else:
        print("station: no railway inside this box")

    tree = monument_tree()
    if tree:
        x, y, tags = tree
        species = GENUS.get(tags.get("genus") or "")
        label = tags.get("name") or species or "Naturdenkmal"
        kind = "Naturdenkmal" + (f" · {species}" if species and species != label else "")
        add_place(
            out,
            rings,
            {
                "name": label,
                "kind": kind,
                "note": "Naturdenkmal",
                "text": f"{label}, in OpenStreetMap als Naturdenkmal geführt. Ob es die alte Dorfeiche ist, sagt die Karte nicht.",
            },
            (x, y),
        )
        taken[label] = (x, y)

    for p in POINTS:
        xy = locate(p)
        if xy is None or not in_box(*xy):
            print(f"{p['name']}: skipped, off the map")
            continue
        add_place(out, rings, p, xy)
        taken[p["name"]] = xy

    extras = osm_extras(taken)
    names = {h["name"] for h in out["hotspots"]}
    for key, label, members in CATEGORIES:
        keep = [n for n in members if n in names]
        if keep:
            out["categories"].append({"key": key, "label": label, "names": keep})
    if extras:
        for e in extras:
            out["places"].append({"name": e["name"], "note": e["note"], "x": e["x"], "y": e["y"], "h": 3})
            out["hotspots"].append({"name": e["name"], "x": e["x"], "y": e["y"], "kind": e["kind"], "note": e["note"]})
        out["categories"].append({"key": "osm", "label": "Im Dorf", "names": [e["name"] for e in extras]})
        print(f"{len(extras)} more places from OpenStreetMap")

    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "landmarks.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
