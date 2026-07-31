import math
import re

EARTH_RADIUS_M = 6_371_000

def bearing_distance(lat1, lon1, lat2, lon2):
    """Inverse of destination_point: initial bearing and great-circle distance from point 1 to point 2."""
    lat1r, lon1r, lat2r, lon2r = (math.radians(v) for v in (lat1, lon1, lat2, lon2))
    dlon = lon2r - lon1r

    y = math.sin(dlon) * math.cos(lat2r)
    x = math.cos(lat1r) * math.sin(lat2r) - math.sin(lat1r) * math.cos(lat2r) * math.cos(dlon)
    bearing_deg = math.degrees(math.atan2(y, x)) % 360

    a = (
        math.sin((lat2r - lat1r) / 2) ** 2
        + math.cos(lat1r) * math.cos(lat2r) * math.sin(dlon / 2) ** 2
    )
    distance_m = EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return bearing_deg, distance_m


_MAIDENHEAD_RE = re.compile(r"^[A-R]{2}[0-9]{2}([A-X]{2})?$", re.IGNORECASE)


def maidenhead_to_latlon(grid):
    """Center lat/lon of a 4- or 6-character Maidenhead grid locator."""
    grid = grid.strip()
    if not _MAIDENHEAD_RE.match(grid):
        raise ValueError(f"Not a valid Maidenhead grid locator: {grid!r}")

    lon = (ord(grid[0].upper()) - ord("A")) * 20 - 180
    lat = (ord(grid[1].upper()) - ord("A")) * 10 - 90
    lon += int(grid[2]) * 2
    lat += int(grid[3]) * 1

    if len(grid) >= 6:
        lon += (ord(grid[4].upper()) - ord("A")) * (2 / 24)
        lat += (ord(grid[5].upper()) - ord("A")) * (1 / 24)
        lon += (2 / 24) / 2
        lat += (1 / 24) / 2
    else:
        lon += 1
        lat += 0.5

    return lat, lon


def destination_point(lat, lon, bearing_deg, distance_m):
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    bearing = math.radians(bearing_deg)

    d = distance_m / EARTH_RADIUS_M

    lat2 = math.asin(
        math.sin(lat1) * math.cos(d)
        + math.cos(lat1) * math.sin(d) * math.cos(bearing)
    )

    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(d) * math.cos(lat1),
        math.cos(d) - math.sin(lat1) * math.sin(lat2)
    )

    return math.degrees(lat2), math.degrees(lon2)