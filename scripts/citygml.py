"""Read LGLN LoD2 CityGML (AdV CityGML 1.0) into the buildings the renderer uses.

Each 1 km tile is one .gml file in data/raw/lod2/. A building is one record with
its footprint and its wall, roof and ground surfaces in UTM metres, absolute
height included. The first call parses the files and caches the result, so
landmarks and the building mesh share one read.

Licence of the source: CC BY 4.0, Landesamt für Geoinformation und
Landesvermessung Niedersachsen (LGLN). The files say so themselves.
"""

import pickle
import xml.etree.ElementTree as ET

import numpy as np

from config import RAW, XMAX, XMIN, YMAX, YMIN

B = "{http://www.opengis.net/citygml/building/1.0}"
G = "{http://www.opengis.net/gml}"
GEN = "{http://www.opengis.net/citygml/generics/1.0}"
CACHE = RAW / "buildings.pkl"

SURFACE = {"WallSurface": 1, "RoofSurface": 2, "GroundSurface": 0, "ClosureSurface": 0}
# AdV building-function codes that are glasshouses. Lidar goes through the glass,
# the same way 3D BAG cannot reconstruct a Dutch kas, so these are extruded.
GREENHOUSE = {"2723", "2463", "2741"}


def _ring(text):
    vals = np.fromstring(text or "", sep=" ")
    if vals.size < 9 or vals.size % 3:
        return None
    pts = vals.reshape(-1, 3)
    if np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    return pts if len(pts) >= 3 else None


def _area(xy):
    return 0.5 * abs(np.dot(xy[:, 0], np.roll(xy[:, 1], 1)) - np.dot(xy[:, 1], np.roll(xy[:, 0], 1)))


def _attr(el, name):
    for sa in el.findall(f"{GEN}stringAttribute"):
        if sa.get("name") == name:
            value = sa.find(f"{GEN}value")
            if value is not None and value.text:
                return value.text
    return None


def _address(el):
    street = number = None
    for node in el.iter():
        tag = node.tag.split("}")[-1]
        if tag == "ThoroughfareName" and node.text:
            street = node.text.strip()
        elif tag in ("ThoroughfareNumber", "BuildingNumber") and node.text:
            number = node.text.strip()
    if street and number:
        return f"{street} {number}"
    return None


def _code(text):
    """'31001_3041' is ALKIS object type plus the building function. Keep the function."""
    if not text:
        return ""
    return text.split("_")[-1]


def _on_map(fp):
    return not (fp[:, 0].max() < XMIN or fp[:, 0].min() > XMAX or fp[:, 1].max() < YMIN or fp[:, 1].min() > YMAX)


def parse_building(el):
    surfaces = []
    grounds = []
    zs = []
    roofs = []
    heights = []
    parts = list(el.iter(f"{B}BuildingPart")) or [el]
    for part in parts:
        code = _code((part.findtext(f"{B}roofType") or "").strip())
        if code:
            roofs.append(code)
        measured = part.findtext(f"{B}measuredHeight")
        if measured:
            try:
                heights.append(float(measured))
            except ValueError:
                pass
        for bounded in part.findall(f"{B}boundedBy"):
            for child in list(bounded):
                name = child.tag.split("}")[-1]
                kind = SURFACE.get(name)
                if kind is None:
                    continue
                rings = []
                for pl in child.findall(f".//{G}posList"):
                    ring = _ring(pl.text)
                    if ring is not None:
                        rings.append(ring)
                        zs.append(ring[:, 2])
                if not rings:
                    continue
                surfaces.append((kind, rings))
                if name in ("GroundSurface", "ClosureSurface"):
                    grounds.append(rings[0][:, :2])
    if not zs:
        return None
    z = np.concatenate(zs)
    ground_z, top_z = float(z.min()), float(z.max())
    if grounds:
        footprint = max(grounds, key=_area)
    else:
        # No floor surface: the outline of every vertex that sits on the ground.
        pts = np.concatenate([r[:, :2] for _, rings in surfaces for r in rings])
        zz = np.concatenate([r[:, 2] for _, rings in surfaces for r in rings])
        low = pts[zz < ground_z + 0.4]
        footprint = low if len(low) >= 3 else pts
        # Keep it as a ring the painter can fill: the axis-aligned box is ugly, so
        # use the convex hull when scipy is around and the raw points otherwise.
        try:
            from scipy.spatial import ConvexHull

            hull = ConvexHull(footprint)
            footprint = footprint[hull.vertices]
        except Exception:
            pass
    if len(footprint) < 3 or not _on_map(footprint):
        return None
    function = _code(el.findtext(f"{B}function"))
    return {
        "id": el.get(f"{G}id") or el.get("id") or "building",
        "function": function,
        "roof": roofs[0] if roofs else "",
        "ground": ground_z,
        "height": max(top_z - ground_z, max(heights, default=0.0)),
        "address": _address(el),
        "greenhouse": function in GREENHOUSE,
        "footprint": np.asarray(footprint, dtype=np.float64),
        "surfaces": surfaces,
    }


def parse_files():
    files = sorted((RAW / "lod2").glob("*.gml"))
    if not files:
        raise SystemExit("no LoD2 CityGML in data/raw/lod2; run fetch.py")
    out = []
    for path in files:
        n = 0
        for _, el in ET.iterparse(path, events=("end",)):
            if el.tag != f"{B}Building":
                continue
            rec = parse_building(el)
            el.clear()
            if rec:
                out.append(rec)
                n += 1
        print(f"citygml {path.name}: {n} buildings on the map", flush=True)
    return out


def load_buildings():
    if CACHE.exists():
        with open(CACHE, "rb") as f:
            return pickle.load(f)
    buildings = parse_files()
    RAW.mkdir(parents=True, exist_ok=True)
    with open(CACHE, "wb") as f:
        pickle.dump(buildings, f, protocol=pickle.HIGHEST_PROTOCOL)
    write_footprints(buildings)
    return buildings


def write_footprints(buildings):
    """The ground painter covers each building with its own colour. LoD2 footprints, not the OSM outline."""
    import json

    feats = []
    addresses = []
    for b in buildings:
        ring = [[round(float(x), 2), round(float(y), 2)] for x, y in b["footprint"]]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        feats.append(
            {
                "type": "Feature",
                "properties": {"lokaal_id": b["id"], "type": "pand"},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )
        if b.get("address"):
            c = b["footprint"].mean(0)
            addresses.append([round(float(c[0]), 1), round(float(c[1]), 1), b["address"]])
    (RAW / "bgt_pand.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    # Official addresses win. OSM addresses filled the file first; keep a house number LoD2 does not have.
    path = RAW / "addresses.json"
    have = {a[2] for a in addresses}
    if path.exists():
        for x, y, label in json.loads(path.read_text()):
            if label not in have:
                addresses.append([x, y, label])
                have.add(label)
    path.write_text(json.dumps(addresses, ensure_ascii=False))
