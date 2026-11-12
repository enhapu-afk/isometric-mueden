# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "rasterio", "shapely", "tifffile"]
# ///
"""Download the open data for Langlingen and lay it out the way the rest of the pipeline expects.

Niedersachsen, all CC BY 4.0, Landesamt für Geoinformation und Landesvermessung
Niedersachsen (LGLN), in ETRS89 / UTM zone 32N:

  LoD2 buildings   STAC https://lod.stac.lgln.niedersachsen.de  (CityGML)
  DGM1 bare earth  STAC https://dgm.stac.lgln.niedersachsen.de  (1 m, resampled to 0.5 m)
  DOM1 surface     STAC https://dom.stac.lgln.niedersachsen.de  (1 m, resampled to 0.5 m)
  DOP20 aerial     WMS  https://opendata.lgln.niedersachsen.de/doorman/noauth/dop_wms

Roads, water, land cover, routes and places come from OpenStreetMap (ODbL).
The elevation chunks keep the names build_trees.py already reads
(ahn/dsm_05m_{ix}_{iy}.tif, row 0 to the north), so that script stays as it is.
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import rasterio
import tifffile

from config import CHUNK, NX, NY, RAW, XMAX, XMIN, YMAX, YMIN, write_area
from geo import utm_to_wgs, wgs_to_utm

UA = {"User-Agent": "isometric-langlingen/0.1 (personal map; https://github.com/enhapu-afk)"}
TILE = re.compile(r"32_(\d{3})_(\d{4})_")
WMS = "https://opendata.lgln.niedersachsen.de/doorman/noauth/dop_wms"

CATALOGUES = {
    "lod2": ("https://lod.stac.lgln.niedersachsen.de", "lod2", "lod2-gml", "lod2", ".gml"),
    "dgm1": ("https://dgm.stac.lgln.niedersachsen.de", "dgm1", "dgm1-tif", "dgm", ".tif"),
    "dom1": ("https://dom.stac.lgln.niedersachsen.de", "dom1", "dom1-tif", "dom", ".tif"),
}


def get(url, binary=False, data=None, tries=5):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as r:
                body = r.read()
            return body if binary else json.loads(body)
        except Exception as e:  # noqa: BLE001
            if attempt == tries - 1:
                raise
            print(f"retry {attempt + 1} {url[:110]}: {e}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))


def download(url, dest):
    if dest.exists() and dest.stat().st_size > 2000:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
        while True:
            block = r.read(1 << 20)
            if not block:
                break
            f.write(block)
    tmp.rename(dest)
    print(f"got {dest.name} ({dest.stat().st_size // 1024} kB)", file=sys.stderr)


def stac_bbox():
    lats, lons = [], []
    for x in (XMIN, XMAX):
        for y in (YMIN, YMAX):
            lat, lon = utm_to_wgs(x, y)
            lats.append(lat)
            lons.append(lon)
    # A little slack so a tile that only clips a corner is still offered.
    return f"{min(lons) - 0.01:.5f},{min(lats) - 0.01:.5f},{max(lons) + 0.01:.5f},{max(lats) + 0.01:.5f}"


def osm_bbox():
    lats, lons = [], []
    for x in (XMIN, XMAX):
        for y in (YMIN, YMAX):
            lat, lon = utm_to_wgs(x, y)
            lats.append(lat)
            lons.append(lon)
    return f"{min(lats):.6f},{min(lons):.6f},{max(lats):.6f},{max(lons):.6f}"


def stac_search(base, collection):
    url = f"{base}/search?collections={urllib.parse.quote(collection)}&bbox={stac_bbox()}&limit=100"
    feats, seen = [], set()
    for _ in range(20):
        if url in seen:
            break
        seen.add(url)
        page = get(url)
        feats += page.get("features") or []
        nxt = next((l.get("href") for l in page.get("links") or [] if l.get("rel") == "next" and l.get("href")), None)
        if not nxt or not page.get("features"):
            break
        url = nxt
    return feats


def tile_box(item):
    text = item.get("id") or ""
    m = TILE.search(text)
    if not m:
        for asset in item.get("assets", {}).values():
            m = TILE.search(asset.get("href") or "")
            if m:
                break
    if not m:
        return None
    e, n = int(m.group(1)) * 1000, int(m.group(2)) * 1000
    return e, n, e + 1000, n + 1000


def intersects(box):
    e0, n0, e1, n1 = box
    return e0 < XMAX and e1 > XMIN and n0 < YMAX and n1 > YMIN


def newest(items):
    best = {}
    for item in items:
        box = tile_box(item)
        if box is None or not intersects(box):
            continue
        key = (box[0], box[1])
        dt = (item.get("properties") or {}).get("datetime") or ""
        if key not in best or dt > best[key][0]:
            best[key] = (dt, item, box)
    return list(best.values())


def asset_href(item, key):
    assets = item.get("assets") or {}
    if key in assets and assets[key].get("href"):
        return assets[key]["href"]
    for asset in assets.values():
        href = asset.get("href") or ""
        if href.endswith((".tif", ".tiff", ".gml")):
            return href
    raise SystemExit(f"no data asset on {item.get('id')}: {list(assets)}")


def fetch_catalogue(name):
    base, collection, asset, folder, suffix = CATALOGUES[name]
    picked = newest(stac_search(base, collection))
    print(f"{name}: {len(picked)} tiles", file=sys.stderr)
    jobs = []
    for dt, item, box in picked:
        href = asset_href(item, asset)
        dest = RAW / folder / f"{re.sub(r'[^A-Za-z0-9._-]', '_', item['id'])}{suffix}"
        jobs.append((href, dest, dt, box))
    with ThreadPoolExecutor(6) as pool:
        list(pool.map(lambda j: download(j[0], j[1]), jobs))
    return jobs


def note_licences():
    notes = []
    for name, (base, collection, _, _, _) in CATALOGUES.items():
        try:
            meta = get(f"{base}/collections/{collection}")
            notes.append({"id": name, "title": meta.get("title"), "license": meta.get("license"), "url": f"{base}/collections/{collection}"})
            print(f"licence {name}: {meta.get('license')}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            notes.append({"id": name, "error": str(e)})
            print(f"licence {name}: {e}", file=sys.stderr)
    try:
        meta = get("https://dop.stac.lgln.niedersachsen.de/collections/DOP")
        notes.append({"id": "dop20", "title": meta.get("title"), "license": meta.get("license"), "wms": WMS})
        print(f"licence dop20: {meta.get('license')}", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        notes.append({"id": "dop20", "error": str(e), "wms": WMS})
    notes.append({"id": "osm", "title": "OpenStreetMap", "license": "ODbL", "url": "https://www.openstreetmap.org/copyright"})
    (RAW / "licences.json").write_text(json.dumps(notes, indent=1, ensure_ascii=False))


def _sample(data, transform, xs, ys):
    """Nearest source pixel for every output pixel. xs is west to east, ys is north to south."""
    a, b, c = transform.a, transform.b, transform.c
    d, e, f = transform.d, transform.e, transform.f
    det = a * e - b * d
    x = xs[None, :] - c
    y = ys[:, None] - f
    col = (e * x - b * y) / det
    row = (-d * x + a * y) / det
    h, w = data.shape
    inside = (row >= -0.5) & (row < h - 0.5) & (col >= -0.5) & (col < w - 0.5)
    ri = np.clip(np.rint(row).astype(np.int32), 0, h - 1)
    ci = np.clip(np.rint(col).astype(np.int32), 0, w - 1)
    sampled = data[ri, ci]
    return np.where(inside & np.isfinite(sampled), sampled, np.nan)


def _read_tile(path):
    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float32)
        nodata = src.nodata
        if nodata is not None:
            data[np.isclose(data, nodata) | (data == nodata)] = np.nan
        data[(data > 1000) | (data < -100)] = np.nan
        return data, src.transform


def resample(jobs, cov):
    """1 m tiles to 500 m chunks at 0.5 m, row 0 at the north of the chunk. iy 0 is the south of the map."""
    tiles = []
    for _, dest, dt, _box in sorted(jobs, key=lambda j: j[2]):
        tiles.append((dt, *_read_tile(dest)))
    out_dir = RAW / "ahn"
    out_dir.mkdir(parents=True, exist_ok=True)
    px = int(CHUNK / 0.5)
    for ix in range(NX):
        for iy in range(NY):
            dest = out_dir / f"{cov}_{ix}_{iy}.tif"
            if dest.exists() and dest.stat().st_size > 1000:
                continue
            x0, y0 = XMIN + ix * CHUNK, YMIN + iy * CHUNK
            xs = x0 + (np.arange(px) + 0.5) * 0.5
            ys = (y0 + CHUNK) - (np.arange(px) + 0.5) * 0.5
            acc = np.full((px, px), np.nan, np.float32)
            for _dt, data, transform in tiles:
                sampled = _sample(data, transform, xs, ys)
                fresh = np.isfinite(sampled)
                acc[fresh] = sampled[fresh]
            tifffile.imwrite(dest, acc)
            finite = acc[np.isfinite(acc)]
            missing = int(np.isnan(acc).mean() * 100)
            mean = float(finite.mean()) if finite.size else float("nan")
            print(f"{cov} {ix}_{iy}: {missing}% empty, mean {mean:.1f} m", file=sys.stderr)


def fetch_aerial(ix, iy):
    dest = RAW / "aerial" / f"{ix}_{iy}.jpg"
    if dest.exists() and dest.stat().st_size > 5000 and dest.read_bytes()[:2] == b"\xff\xd8":
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    x0, y0 = XMIN + ix * CHUNK, YMIN + iy * CHUNK
    x1, y1 = x0 + CHUNK, y0 + CHUNK
    px = int(CHUNK / 0.25)
    last = b""
    # This MapServer wants easting,northing for EPSG:25832. The swapped order is the fallback.
    for bbox in (f"{x0},{y0},{x1},{y1}", f"{y0},{x0},{y1},{x1}"):
        q = urllib.parse.urlencode(
            {
                "SERVICE": "WMS",
                "VERSION": "1.3.0",
                "REQUEST": "GetMap",
                "LAYERS": "ni_dop20",
                "STYLES": "",
                "CRS": "EPSG:25832",
                "BBOX": bbox,
                "WIDTH": px,
                "HEIGHT": px,
                "FORMAT": "image/jpeg",
            }
        )
        last = get(f"{WMS}?{q}", binary=True)
        if last[:2] == b"\xff\xd8" and len(last) > 5000:
            dest.write_bytes(last)
            print(f"aerial {ix}_{iy}", file=sys.stderr)
            return
    raise SystemExit(f"aerial {ix}_{iy} was not a JPEG: {last[:160]!r}")


def overpass(out, query, what):
    if out.exists() and out.stat().st_size > 40:
        return
    for host in (
        "overpass-api.de/api/interpreter",
        "overpass.private.coffee/api/interpreter",
        "maps.mail.ru/osm/tools/overpass/api/interpreter",
    ):
        try:
            body = urllib.parse.urlencode({"data": query}).encode()
            req = urllib.request.Request(f"https://{host}", data=body, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            json.loads(data)
            out.write_bytes(data)
            print(f"osm {what}: {out.stat().st_size // 1024} kB", file=sys.stderr)
            return
        except Exception as e:  # noqa: BLE001
            print(f"overpass {host} ({what}): {e}", file=sys.stderr)
            time.sleep(3)
    print(f"OpenStreetMap unavailable; {what} left empty", file=sys.stderr)
    out.write_text('{"elements": []}')


def fetch_osm():
    bbox = osm_bbox()
    roads = (
        "motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|"
        "tertiary|tertiary_link|unclassified|residential|living_street|service"
    )
    overpass(
        RAW / "osm_roads.json",
        f"""[out:json][timeout:120];
( way["highway"~"^({roads})$"]({bbox});
  way["highway"~"^(cycleway|footway|path|pedestrian|track|steps|bridleway)$"]({bbox}); );
out geom;""",
        "roads",
    )
    overpass(
        RAW / "osm_routes.json",
        f"""[out:json][timeout:120];
( relation["route"~"^(hiking|foot|walking)$"]({bbox}); node["rwn_ref"]({bbox}); );
out geom;""",
        "routes",
    )
    overpass(
        RAW / "osm_landmarks.json",
        f"""[out:json][timeout:120];
( nwr["amenity"]({bbox}); nwr["tourism"]({bbox}); nwr["historic"]({bbox}); nwr["shop"]({bbox});
  way["leisure"="pitch"]({bbox}); nwr["landuse"="cemetery"]({bbox});
  nwr["leisure"~"^(park|playground|sports_centre|stadium|swimming_pool|nature_reserve|pitch)$"]({bbox});
  node["place"~"^(village|hamlet|suburb|locality)$"]({bbox});
  nwr["railway"~"^(station|halt)$"]({bbox});
  nwr["man_made"~"^(tower|mast|water_tower|chimney)$"]({bbox}); );
out geom tags;""",
        "places",
    )
    overpass(
        RAW / "osm_land.json",
        f"""[out:json][timeout:180];
( way["landuse"]({bbox}); way["natural"]({bbox}); way["waterway"]({bbox});
  way["leisure"~"^(park|garden|pitch|playground|recreation_ground|nature_reserve)$"]({bbox});
  way["railway"~"^(rail|light_rail|disused|abandoned)$"]({bbox});
  way["man_made"~"^(silo|storage_tank)$"]({bbox});
  relation["landuse"]({bbox}); relation["natural"="water"]({bbox});
  relation["waterway"~"^(river|stream|canal)$"]({bbox}); );
out geom;""",
        "land and water",
    )
    overpass(
        RAW / "osm_trees.json",
        f"""[out:json][timeout:90];
node["natural"="tree"]({bbox});
out;""",
        "trees",
    )
    overpass(
        RAW / "osm_addr.json",
        f"""[out:json][timeout:120];
nwr["addr:housenumber"]({bbox});
out center tags;""",
        "addresses",
    )


def write_osm_addresses():
    """House numbers from OSM. LoD2 addresses overwrite these where both exist."""
    pts, seen = [], set()
    for el in json.loads((RAW / "osm_addr.json").read_text()).get("elements") or []:
        tags = el.get("tags") or {}
        street, number = tags.get("addr:street"), tags.get("addr:housenumber")
        if not street or not number:
            continue
        center = el.get("center") or el
        if "lat" not in center:
            continue
        x, y = wgs_to_utm(center["lat"], center["lon"])
        if not (XMIN <= x <= XMAX and YMIN <= y <= YMAX):
            continue
        label = f"{street} {number}"
        if label in seen:
            continue
        seen.add(label)
        pts.append([round(x, 1), round(y, 1), label])
    (RAW / "addresses.json").write_text(json.dumps(pts, ensure_ascii=False))
    print(f"osm addresses: {len(pts)}", file=sys.stderr)


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    write_area()
    note_licences()
    dgm = fetch_catalogue("dgm1")
    dom = fetch_catalogue("dom1")
    fetch_catalogue("lod2")
    resample(dgm, "dtm_05m")
    resample(dom, "dsm_05m")
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda ij: fetch_aerial(*ij), [(i, j) for i in range(NX) for j in range(NY)]))
    fetch_osm()
    write_osm_addresses()
    import osm_ground

    osm_ground.build()
    import citygml

    citygml.write_footprints(citygml.load_buildings())
    print("done", file=sys.stderr)


if __name__ == "__main__":
    main()
