# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
"""Named places of Ettenbüttel, in Müden (Aller): colours for a few listed buildings, and the place list.

The stories are the public ones, from the Niedersachsen monument register and the
municipality's record of the 1974 incorporation. The house the map opens on has
no story beyond its address. Anything only a neighbour would know is left out.

Output: data/build/landmarks.json
"""

import json

import numpy as np

from citygml import load_buildings
from config import BUILD, RAW, VILLAGE_X, VILLAGE_Y, XMAX, XMIN, YMAX, YMIN
from geo import wgs_to_rd

# Brick infill and dark timber, as the monument record describes the hall houses.
# Roofs without an explicit colour take theirs from the aerial photo.
FRAME_WALL, FRAME_TIMBER = (176, 92, 72), (92, 64, 44)

BUILDINGS = [
    {
        "name": "Allertal 15",
        "note": "Vierständer-Hallenhaus",
        "kind": "Baudenkmal",
        "latlon": (52.500937, 10.408575),
        "style": "house",
        "wall": FRAME_WALL,
        "frame": FRAME_TIMBER,
        "text": "An der Allertal 15, der Landesstraße durch Ettenbüttel, steht ein eingeschossiges Vierständer-Hallenhaus mit Ziegelausfachung und Krüppelwalmdach, die Einfahrt in der Mitte der Längsseite. Es ist ein eingetragenes Baudenkmal. Wann es gebaut wurde, sagt diese Karte nicht.",
        "more": "https://denkmalatlas.niedersachsen.de/viewer/metadata/33934218/1/-/",
        "stop": "Allertal 15",
    },
    {
        "name": "Hirtenwinkel 4",
        "note": "Vierständer-Hallenhaus",
        "kind": "Baudenkmal",
        "latlon": (52.498746, 10.410619),
        "style": "house",
        "wall": FRAME_WALL,
        "frame": FRAME_TIMBER,
        "text": "Hirtenwinkel 4 ist ebenfalls ein Vierständer-Hallenhaus, mit Ziegelausfachung unter einem Halbwalmdach und einem quergestellten Stallanbau. Eingetragenes Baudenkmal.",
        "more": "https://denkmalatlas.niedersachsen.de/viewer/metadata/33934242/1/-/",
        "stop": "Hirtenwinkel 4",
    },
    {
        "name": "Speicher Bokelberge",
        "note": "Bokelberge 2",
        "kind": "Speicher · Baudenkmal",
        "latlon": (52.509287, 10.406929),
        "style": "house",
        "wall": FRAME_WALL,
        "frame": FRAME_TIMBER,
        "text": "In Bokelberge, nördlich von Ettenbüttel, steht ein zweigeschossiger Fachwerkspeicher mit vorkragendem Obergeschoss unter einem Satteldach. Eingetragenes Baudenkmal.",
        "more": "https://denkmalatlas.niedersachsen.de/viewer/metadata/33934711/1/-/",
        "stop": "Speicher Bokelberge",
    },
]

POINTS = [
    {
        "name": "Grüne Heide 18",
        "latlon": (52.4951592, 10.4223315),
        "kind": "Adresse",
        "address": "Grüne Heide 18, Ettenbüttel",
        "text": "Wohnhaus an der Grünen Heide 18. Die Karte fängt hier an. Die Straße ist in OpenStreetMap als feiner Kies geführt. Was in dem Haus und auf der Straße los ist, weiß diese Karte nicht.",
    },
]

# The Aller has no house number. It is placed from its OpenStreetMap centre-line, if that line crosses the box.
RIVER = {
    "name": "Aller",
    "kind": "Fluss",
    "text": "Die Aller fließt nördlich an Ettenbüttel vorbei. Westlich des Orts liegt die Oker. Die beiden Flüsse treffen sich im Kernort Müden, etwa fünf Kilometer nordwestlich von hier und außerhalb dieses Blatts.",
    "stop": "An der Aller",
}

CATEGORIES = [
    ("heide", "Grüne Heide", ["Grüne Heide 18"]),
    ("hoefe", "Fachwerk", ["Allertal 15", "Hirtenwinkel 4", "Speicher Bokelberge"]),
    ("fluss", "Am Fluss", ["Aller"]),
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
                # Prefer the stretch north of Allertal, where the houses meet the meadows.
                score = abs(x - VILLAGE_X) + max(0, VILLAGE_Y - y) * 0.25
                if best is None or score < best[0]:
                    best = (score, x, y)
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
                "text": f"{label}, in OpenStreetMap als Naturdenkmal geführt. Mehr dazu weiß diese Karte nicht.",
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
