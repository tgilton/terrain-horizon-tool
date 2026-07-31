import argparse
import math
from pathlib import Path
import requests
BASE_URL_TEMPLATE = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/{resolution}/TIFF/current"

def destination_point(lat, lon, bearing_deg, distance_m):
    r = 6_371_000
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    bearing = math.radians(bearing_deg)
    d = distance_m / r
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(bearing))
    lon2 = lon1 + math.atan2(math.sin(bearing) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2))
    return math.degrees(lat2), math.degrees(lon2)

def tile_name_for_point(lat, lon):
    north_edge = math.floor(lat) + 1
    west_edge = math.floor(lon)
    ns = f"n{north_edge:02d}" if north_edge >= 0 else f"s{abs(north_edge):02d}"
    ew = f"w{abs(west_edge):03d}" if west_edge < 0 else f"e{west_edge:03d}"
    return f"{ns}{ew}"

def required_tiles(lat, lon, radius_km):
    north, _ = destination_point(lat, lon, 0, radius_km * 1000)
    south, _ = destination_point(lat, lon, 180, radius_km * 1000)
    _, east = destination_point(lat, lon, 90, radius_km * 1000)
    _, west = destination_point(lat, lon, 270, radius_km * 1000)
    tiles = set()
    lat_start = math.floor(south)
    lat_end = math.ceil(north)
    lon_start = math.floor(west)
    lon_end = math.ceil(east)
    for tile_lat in range(lat_start, lat_end + 1):
        for tile_lon in range(lon_start, lon_end + 1):
            sample_lat = tile_lat + 0.5
            sample_lon = tile_lon + 0.5
            tiles.add(tile_name_for_point(sample_lat, sample_lon))
    return sorted(tiles)

def download_tile(tile, outdir, resolution):
    outdir.mkdir(parents=True, exist_ok=True)
    base_url = BASE_URL_TEMPLATE.format(resolution=resolution)
    filename = f"USGS_{resolution}_{tile}.tif"
    path = outdir / filename
    if path.exists():
        print(f"Already exists: {filename}")
        return
    url = f"{base_url}/{tile}/{filename}"
    print(f"Downloading {filename}")
    r = requests.get(url, stream=True, timeout=60)
    if r.status_code == 404:
        print(f"Not found: {url}")
        return
    r.raise_for_status()
    total = int(r.headers.get("content-length", 0))
    downloaded = 0
    with path.open("wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = 100 * downloaded / total
                    print(f"\r{pct:5.1f}% complete", end="")
    print(f"\nSaved: {path}")

def main():
    parser = argparse.ArgumentParser(description="Download USGS 1/3 arc-second DEM tiles.")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--radius-km", type=float, default=100)
    parser.add_argument("--outdir", default="dem")
    parser.add_argument("--resolution", choices=["1", "13"], default="13")
    args = parser.parse_args()
    outdir = Path(args.outdir)
    tiles = required_tiles(args.lat, args.lon, args.radius_km)
    print("Required tiles:")
    for tile in tiles:
        print(f"  {tile}")
    for tile in tiles:
        download_tile(tile, outdir, args.resolution)
if __name__ == "__main__":
    main()