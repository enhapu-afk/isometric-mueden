"""ETRS89 / UTM zone 32N (EPSG:25832) <-> WGS84, and the isometric projection.

Langlingen is at about 10.3 degrees east, so the metric grid is UTM zone 32.
The Dutch names wgs_to_rd and rd_to_wgs remain as aliases: every other script
still speaks of "RD" where it means "the map's metre coordinates".

The formulas are Snyder's transverse Mercator on the GRS80 ellipsoid (the
ellipsoid of ETRS89). Checked against PROJ, they stay within a few centimetres.
"""

import math

from config import CX, CY, XMAX, XMIN, YMAX, YMIN

A = 6378137.0
F = 1 / 298.257222101  # GRS80
E2 = F * (2 - F)
EP2 = E2 / (1 - E2)
K0 = 0.9996
LON0 = math.radians(9.0)  # zone 32
E0 = 500_000.0

HX, HZ = (XMAX - XMIN) / 2, (YMAX - YMIN) / 2


def _meridian(lat):
    return A * (
        (1 - E2 / 4 - 3 * E2**2 / 64 - 5 * E2**3 / 256) * lat
        - (3 * E2 / 8 + 3 * E2**2 / 32 + 45 * E2**3 / 1024) * math.sin(2 * lat)
        + (15 * E2**2 / 256 + 45 * E2**3 / 1024) * math.sin(4 * lat)
        - (35 * E2**3 / 3072) * math.sin(6 * lat)
    )


def wgs_to_utm(lat, lon):
    """Latitude and longitude in degrees to UTM 32N easting and northing."""
    phi, lam = math.radians(lat), math.radians(lon)
    n = A / math.sqrt(1 - E2 * math.sin(phi) ** 2)
    t = math.tan(phi) ** 2
    c = EP2 * math.cos(phi) ** 2
    aa = (lam - LON0) * math.cos(phi)
    m = _meridian(phi)
    east = E0 + K0 * n * (
        aa
        + (1 - t + c) * aa**3 / 6
        + (5 - 18 * t + t * t + 72 * c - 58 * EP2) * aa**5 / 120
    )
    north = K0 * (
        m
        + n
        * math.tan(phi)
        * (aa**2 / 2 + (5 - t + 9 * c + 4 * c * c) * aa**4 / 24 + (61 - 58 * t + t * t + 600 * c - 330 * EP2) * aa**6 / 720)
    )
    return east, north


def utm_to_wgs(east, north):
    """UTM 32N easting and northing to latitude and longitude in degrees."""
    e1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))
    m = north / K0
    mu = m / (A * (1 - E2 / 4 - 3 * E2**2 / 64 - 5 * E2**3 / 256))
    phi1 = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
        + (1097 * e1**4 / 512) * math.sin(8 * mu)
    )
    n1 = A / math.sqrt(1 - E2 * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = EP2 * math.cos(phi1) ** 2
    r1 = A * (1 - E2) / (1 - E2 * math.sin(phi1) ** 2) ** 1.5
    d = (east - E0) / (n1 * K0)
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1 * c1 - 9 * EP2) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 * t1 - 252 * EP2 - 3 * c1 * c1) * d**6 / 720
    )
    lon = LON0 + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1 * c1 + 8 * EP2 + 24 * t1 * t1) * d**5 / 120
    ) / math.cos(phi1)
    return math.degrees(lat), math.degrees(lon)


# The rest of the pipeline was written for Dutch RD. These names now mean UTM.
wgs_to_rd = wgs_to_utm
rd_to_wgs = utm_to_wgs


def screen(x, z, h=0.0, look=45):
    """Local meters (x east, z south, h up) to the render's screen meters (u right, v up) for a camera looking `look`
    degrees from north, 30 degrees down (render/scene.js). Works on numbers and numpy arrays alike."""
    a = math.radians(look)
    return x * math.cos(a) + z * math.sin(a), (x * math.sin(a) - z * math.cos(a)) * 0.5 + h * math.cos(math.radians(30))


def rd_to_image(x, y, scale=4, height_m=0.0):
    """Pixel position in the full isometric render of a map point at a height above ground (see render/scene.js)."""
    width = round(2 * (HX + HZ) / math.sqrt(2) * scale)
    lx, lz = x - CX, CY - y
    u = (lx + lz) / math.sqrt(2)
    v = (lx - lz) / (2 * math.sqrt(2)) + height_m * math.cos(math.radians(30))
    top = (HX + HZ) / math.sqrt(2) * 0.5 + 32
    return u * scale + width / 2, (top - v) * scale
