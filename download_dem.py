import argparse
import math
from pathlib import Path
import requests

from geometry import destination_point

BASE_URL_TEMPLATE = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/{resolution}/TIFF/current"

# Rough average tile size on disk, used only to give the user a size estimate
# before a bulk download; actual sizes vary with terrain relief and latitude.
AVG_TILE_SIZE_MB = {"1": 48, "13": 400}

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

def missing_tiles(lat, lon, radius_km, outdir, resolution):
    outdir = Path(outdir)
    tiles = required_tiles(lat, lon, radius_km)
    return [
        tile for tile in tiles
        if not (outdir / f"USGS_{resolution}_{tile}.tif").exists()
    ]

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