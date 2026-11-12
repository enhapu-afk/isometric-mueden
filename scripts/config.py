"""Shared settings: the area we render, in ETRS89 / UTM zone 32N (EPSG:25832) metres.

Ettenbüttel, an Ortsteil of Müden (Aller), Landkreis Gifhorn. The box is
3.5 x 3.5 km around Grüne Heide. The Kernort of Müden, with St. Petri and the
mouth of the Oker, is about five kilometres northwest and is not on this sheet.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
BUILD = ROOT / "data" / "build"

# Aligned to the 500 m chunk grid. Grüne Heide 18 is at about 596560, 5817064.
XMIN, YMIN, XMAX, YMAX = 595000, 5815500, 598500, 5819000
CX, CY = (XMIN + XMAX) / 2, (YMIN + YMAX) / 2

# The map opens at the house. The evening lamps gather on the through-road, Allertal.
HOME_X, HOME_Y = 596560.3, 5817064.4
VILLAGE_X, VILLAGE_Y = 595613.9, 5817688.8

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
