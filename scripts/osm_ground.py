"""Turn OpenStreetMap into the ground layers the painter already understands.

The painter (build_ground.py) was written for the Dutch BGT. It keys off a
collection name and a few Dutch property strings. Rather than teach it a second
vocabulary, this writes the same files, in UTM metres, from OSM:

  bgt_begroeidterreindeel, onbegroeidterreindeel, waterdeel,
  ondersteunendwaterdeel, wegdeel, ondersteunendwegdeel, overbruggingsdeel,
  overigbouwwerk, vegetatieobject_punt

Buildings come from the LoD2 CityGML, not from OSM, so bgt_pand is left alone.
Roads that cars drive stay in osm_roads.json; the old railway is drawn here as
a narrow gravel bed and is not a road.
"""

import json

from shapely.geometry import LineString, Polygon, box
from shapely.ops import polygonize, unary_union

from config import RAW, XMAX, XMIN, YMAX, YMIN
from geo import wgs_to_utm

# Half the width of the paved surface, in metres. A residential street is about
# five and a half metres of asphalt; a farm track is narrower.
HALF = {
    "motorway": 11.0,
    "motorway_link": 5.5,
    "trunk": 8.0,
    "trunk_link": 4.5,
    "primary": 5.0,
    "primary_link": 4.0,
    "secondary": 4.0,
    "secondary_link": 3.5,
    "tertiary": 3.5,
    "tertiary_link": 3.0,
    "unclassified": 2.75,
    "residential": 2.75,
    "living_street": 2.6,
    "service": 1.75,
    "track": 1.5,
    "cycleway": 1.1,
    "footway": 0.8,
    "path": 0.7,
    "pedestrian": 2.0,
    "steps": 0.8,
    "bridleway": 1.1,
}

# (plus_fysiek_voorkomen, fysiek_voorkomen, functie) when OSM gives no surface.
DEFAULT = {
    "motorway": ("asfalt", "gesloten verharding", "rijbaan autosnelweg"),
    "trunk": ("asfalt", "gesloten verharding", "rijbaan"),
    "primary": ("asfalt", "gesloten verharding", "rijbaan"),
    "secondary": ("asfalt", "gesloten verharding", "rijbaan"),
    "tertiary": ("asfalt", "gesloten verharding", "rijbaan"),
    "unclassified": ("asfalt", "gesloten verharding", "rijbaan"),
    "residential": ("asfalt", "gesloten verharding", "rijbaan"),
    "living_street": ("betonstraatstenen", "open verharding", "rijbaan"),
    "service": ("asfalt", "gesloten verharding", "rijbaan"),
    "track": ("grind", "half verhard", "rijbaan"),
    "cycleway": ("asfalt", "gesloten verharding", "fietspad"),
    "footway": ("betonstraatstenen", "open verharding", "voetpad"),
    "path": (None, "onverhard", "voetpad"),
    "pedestrian": ("betonstraatstenen", "open verharding", "voetpad"),
    "steps": ("betonstraatstenen", "open verharding", "voetpad"),
    "bridleway": ("grind", "half verhard", "voetpad"),
}

SURFACE = {
    "asphalt": ("asfalt", "gesloten verharding"),
    "cobblestone": ("gebakken klinkers", "open verharding"),
    "sett": ("gebakken klinkers", "open verharding"),
    "concrete": ("cementbeton", "gesloten verharding"),
    "paving_stones": ("betonstraatstenen", "open verharding"),
    "gravel": ("grind", "half verhard"),
    "compacted": ("grind", "half verhard"),
    "fine_gravel": ("grind", "half verhard"),
    "pebblestone": ("grind", "half verhard"),
    "ground": (None, "onverhard"),
    "dirt": (None, "onverhard"),
    "earth": (None, "onverhard"),
    "unpaved": (None, "onverhard"),
    "grass": (None, "onverhard"),
    "wood": ("tegels", "open verharding"),
}

WATER_HALF = {"river": 16.0, "canal": 6.0, "stream": 3.0, "drain": 1.5, "ditch": 1.1}

LAYERS = [
    "begroeidterreindeel",
    "onbegroeidterreindeel",
    "ondersteunendwaterdeel",
    "ondersteunendwegdeel",
    "waterdeel",
    "wegdeel",
    "overigbouwwerk",
    "overbruggingsdeel",
    "vegetatieobject_punt",
]


def _load(name):
    path = RAW / name
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("elements") or []


def _utm(lat, lon):
    return wgs_to_utm(lat, lon)


def _line(points):
    coords = [_utm(p["lat"], p["lon"]) for p in points]
    if len(coords) < 2:
        return None
    line = LineString(coords)
    return line if line.length > 0.4 else None


def _closed(line):
    c = list(line.coords)
    return len(c) >= 4 and (c[0][0] - c[-1][0]) ** 2 + (c[0][1] - c[-1][1]) ** 2 < 0.25


def _relation(el):
    outers, inners, loose = [], [], []
    for m in el.get("members") or []:
        g = m.get("geometry")
        if not g:
            continue
        line = _line(g)
        if line is None:
            continue
        role = m.get("role") or "outer"
        if role == "inner":
            inners.append(line)
        elif _closed(line) or role == "outer":
            outers.append(line)
        else:
            loose.append(line)
    faces = [p for p in polygonize(outers) if p.area > 2] if outers else []
    if faces:
        if inners:
            holes = [p for p in polygonize(inners) if p.area > 1]
            if holes:
                hole = unary_union(holes)
                faces = [f.difference(hole) for f in faces]
        return unary_union(faces)
    lines = outers + loose
    return unary_union(lines) if lines else None


def _way_geom(el, tags):
    line = _line(el.get("geometry") or [])
    if line is None:
        return None
    areaish = any(k in tags for k in ("landuse", "natural", "water", "leisure", "man_made"))
    if tags.get("natural") in ("tree", "tree_row", "cliff"):
        areaish = False
    if tags.get("waterway") and "natural" not in tags and "water" not in tags and "landuse" not in tags:
        areaish = False
    if tags.get("area") == "yes":
        areaish = True
    if tags.get("area") == "no":
        areaish = False
    if areaish and _closed(line):
        poly = Polygon(line.coords)
        return poly if poly.area > 1 else None
    return line


def _parts(geom):
    if geom is None or geom.is_empty:
        return
    if geom.geom_type == "GeometryCollection":
        for g in geom.geoms:
            yield from _parts(g)
        return
    if geom.geom_type in ("MultiPolygon", "MultiLineString"):
        for g in geom.geoms:
            yield from _parts(g)
        return
    if not geom.is_valid:
        geom = geom.buffer(0)
        yield from _parts(geom)
        return
    yield geom


def _feature(geom, props):
    area = box(XMIN, YMIN, XMAX, YMAX)
    out = []
    clipped = geom.intersection(area)
    for g in _parts(clipped):
        if g.geom_type != "Polygon" or g.area < 1.2:
            continue
        rings = [[[round(x, 2), round(y, 2)] for x, y in g.exterior.coords]]
        rings += [[[round(x, 2), round(y, 2)] for x, y in ring.coords] for ring in g.interiors]
        out.append({"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": rings}})
    return out


def _land_layer(tags):
    """A land-cover polygon, as a BGT collection and the properties style_for() reads."""
    if tags.get("man_made") in ("silo", "storage_tank"):
        plus = "voedersilo" if tags["man_made"] == "silo" else "opslagtank"
        return "overigbouwwerk", {"type": "niet-bgt", "plus_type": plus}
    nat, lu, lei = tags.get("natural"), tags.get("landuse"), tags.get("leisure")
    if nat == "water" or tags.get("water") or lu in ("reservoir", "basin"):
        return "waterdeel", {"fysiek_voorkomen": "water"}
    if nat == "wetland" or lu == "wetland":
        return "begroeidterreindeel", {"fysiek_voorkomen": "moeras"}
    if lu == "forest" or nat == "wood":
        return "begroeidterreindeel", {"fysiek_voorkomen": "loofbos"}
    if lu in ("orchard", "vineyard"):
        return "begroeidterreindeel", {"fysiek_voorkomen": "fruitteelt"}
    if nat == "scrub" or lu in ("scrub", "greenfield"):
        return "begroeidterreindeel", {"fysiek_voorkomen": "struiken"}
    if nat == "heath" or lu == "heath":
        return "begroeidterreindeel", {"fysiek_voorkomen": "heide"}
    if lu in ("farmland", "farm"):
        return "begroeidterreindeel", {"fysiek_voorkomen": "bouwland"}
    if nat == "sand" or nat == "beach" or lu == "quarry":
        return "onbegroeidterreindeel", {"fysiek_voorkomen": "zand"}
    if lu in ("residential", "farmyard", "industrial", "commercial", "retail", "construction", "railway"):
        return "onbegroeidterreindeel", {"fysiek_voorkomen": "erf"}
    if lu in ("meadow", "grass") or nat == "grassland" or lu == "cemetery" or lei in (
        "park",
        "garden",
        "pitch",
        "playground",
        "recreation_ground",
        "nature_reserve",
    ):
        return "begroeidterreindeel", {"fysiek_voorkomen": "grasland overig"}
    return None


def _cover_from(elements, lines_ok):
    """Polygons, and (when lines_ok) river and railway centre-lines, from one Overpass file."""
    polys, lines = [], []
    for el in elements:
        tags = el.get("tags") or {}
        if el["type"] == "way":
            geom = _way_geom(el, tags)
        elif el["type"] == "relation":
            geom = _relation(el)
        else:
            continue
        if geom is None:
            continue
        kind = "line" if geom.geom_type in ("LineString", "MultiLineString") else "poly"
        if kind == "line" and not lines_ok:
            continue
        (lines if kind == "line" else polys).append((tags, geom, f"{el['type'][0]}{el.get('id', '')}"))
    return polys, lines


def _pave(tags, highway):
    base = highway.replace("_link", "") if highway.endswith("_link") else highway
    plus, fv, func = DEFAULT.get(base, ("asfalt", "gesloten verharding", "rijbaan"))
    if highway.endswith("_link") and func == "rijbaan autosnelweg":
        func = "rijbaan"
    surf = SURFACE.get(tags.get("surface") or "")
    if surf:
        plus, fv = surf
    return plus, fv, func


def _cut(geoms, blockers):
    if blockers is None or blockers.is_empty:
        return geoms
    out = []
    for g in geoms:
        cut = g.difference(blockers)
        if not cut.is_empty:
            out.append(cut)
    return out


def build():
    groups = {name: [] for name in LAYERS}
    margin = box(XMIN - 40, YMIN - 40, XMAX + 40, YMAX + 40)

    land_polys, land_lines = _cover_from(_load("osm_land.json"), lines_ok=True)
    water_geoms = []
    land_geoms = []  # (geom, coll, props) cut later so a field does not paint over the river
    for tags, geom, oid in land_polys:
        if tags.get("railway"):
            continue
        layer = _land_layer(tags)
        if layer is None:
            continue
        coll, props = layer
        props = {**props, "lokaal_id": oid}
        if coll == "waterdeel":
            water_geoms.append(geom)
            groups[coll] += _feature(geom, props)
        elif coll == "overigbouwwerk":
            groups[coll] += _feature(geom, props)
        else:
            land_geoms.append((geom, coll, props))

    for tags, geom, oid in land_lines:
        ww = tags.get("waterway")
        if ww in WATER_HALF:
            mid = geom.interpolate(0.5, normalized=True)
            if any(w.buffer(1).contains(mid) for w in water_geoms):
                continue
            half = WATER_HALF[ww]
            poly = geom.intersection(margin).buffer(half, cap_style="round")
            fv = "greppel" if ww == "ditch" else "water"
            groups["waterdeel"] += _feature(poly, {"fysiek_voorkomen": fv, "lokaal_id": oid})
            water_geoms.append(poly)
            continue
        rail = tags.get("railway")
        if rail in ("rail", "light_rail", "disused", "abandoned") and not tags.get("highway"):
            poly = geom.intersection(margin).buffer(2.2, cap_style="flat")
            groups["wegdeel"] += _feature(
                poly, {"plus_fysiek_voorkomen": "grind", "fysiek_voorkomen": "half verhard", "functie": "spoor", "lokaal_id": oid}
            )

    road_geoms = []
    for el in _load("osm_roads.json"):
        if el.get("type") != "way":
            continue
        tags = el.get("tags") or {}
        highway = tags.get("highway")
        if highway not in HALF and not str(highway).endswith("_link"):
            continue
        line = _line(el.get("geometry") or [])
        if line is None:
            continue
        half = HALF.get(highway, HALF.get(str(highway).replace("_link", ""), 2.5))
        plus, fv, func = _pave(tags, highway)
        poly = line.intersection(margin).buffer(half, cap_style="round")
        props = {"fysiek_voorkomen": fv, "functie": func, "lokaal_id": f"w{el.get('id', '')}"}
        if plus:
            props["plus_fysiek_voorkomen"] = plus
        coll = "overbruggingsdeel" if tags.get("bridge") in ("yes", "viaduct") else "wegdeel"
        groups[coll] += _feature(poly, props)
        road_geoms.append(poly)
        if func.startswith("rijbaan"):
            verge = line.intersection(margin).buffer(half + 1.3, cap_style="round").difference(poly.buffer(0.15))
            groups["begroeidterreindeel"] += _feature(verge, {"functie": "berm", "lokaal_id": f"berm{el.get('id', '')}"})

    blockers = [g for g in water_geoms + road_geoms if g is not None and not g.is_empty]
    blockers = unary_union(blockers) if blockers else None
    for geom, coll, props in land_geoms:
        for piece in _cut([geom], blockers):
            groups[coll] += _feature(piece, props)

    # The Aller meadows: anything OSM does not colour would otherwise stay the olive gap colour.
    ground = box(XMIN, YMIN, XMAX, YMAX)
    for piece in _cut([ground], blockers):
        groups["begroeidterreindeel"] += _feature(
            piece, {"fysiek_voorkomen": "grasland agrarisch", "lokaal_id": "background"}
        )

    for geom in water_geoms:
        if geom.area < 200:
            continue
        bank = geom.buffer(3.5).difference(geom)
        groups["ondersteunendwaterdeel"] += _feature(bank, {"fysiek_voorkomen": "oever", "lokaal_id": "oever"})

    trees = []
    for el in _load("osm_trees.json"):
        if el.get("type") != "node" or "lat" not in el:
            continue
        x, y = _utm(el["lat"], el["lon"])
        if not (XMIN <= x <= XMAX and YMIN <= y <= YMAX):
            continue
        trees.append(
            {
                "type": "Feature",
                "properties": {"type": "boom", "lokaal_id": f"n{el.get('id', '')}"},
                "geometry": {"type": "Point", "coordinates": [round(x, 2), round(y, 2)]},
            }
        )
    groups["vegetatieobject_punt"] = trees

    for name, feats in groups.items():
        (RAW / f"bgt_{name}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
        print(f"bgt {name}: {len(feats)}", flush=True)


if __name__ == "__main__":
    build()
