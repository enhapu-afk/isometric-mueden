"""Shared settings: the area we render, in ETRS89 / UTM zone 32N (EPSG:25832) metres.

Langlingen, Landkreis Celle, Niedersachsen. The box is 2.5 x 2.5 km around the
village on the Aller: St. Johannis and the Rittergut sit near the middle, the
Grundschule and the old station road to the south, fields and the river plain
around them.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
BUILD = ROOT / "data" / "build"

# Aligned to the 500 m chunk grid. Church of St. Johannis is at about 587350, 5823707.
XMIN, YMIN, XMAX, YMAX = 586000, 5822500, 588500, 5825000
CX, CY = (XMIN + XMAX) / 2, (YMIN + YMAX) / 2

# Where the map opens, and the centre the evening street lamps gather around.
HOME_X, HOME_Y = 587349.8, 5823707.4
VILLAGE_X, VILLAGE_Y = 587349.8, 5823707.4

# Downloads and ground textures come in square chunks of this many meters.
CHUNK = 500
NX, NY = int((XMAX - XMIN) / CHUNK), int((YMAX - YMIN) / CHUNK)

# Ground raster resolution in meters per pixel.
GROUND_RES = 0.25

# The compass directions the map is rendered from (render/run.mjs --look); the first is the one the viewer opens on.
VIEWS = (45, 135, 225, 315)

# LGLN open data, all CC BY 4.0. The year is the year we fetched them.
ATTRIBUTION = "Quelle: \u00a9 LGLN (2026), CC BY 4.0"


def write_area():
    """The renderer and the viewer read the area from here."""
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "area.json").write_text(
        json.dumps(
            {
                "xmin": XMIN,
                "ymin": YMIN,
                "xmax": XMAX,
                "ymax": YMAX,
                "cx": CX,
                "cy": CY,
                "chunk": CHUNK,
                "nx": NX,
                "ny": NY,
                "crs": "EPSG:25832",
                "home": [HOME_X, HOME_Y],
                "village": [VILLAGE_X, VILLAGE_Y],
            }
        )
    )
