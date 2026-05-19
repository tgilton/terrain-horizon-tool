import argparse
import math
import time
from pathlib import Path

import rasterio
from pyproj import Transformer

import matplotlib.pyplot as plt
import numpy as np
import requests
from geometry import destination_point
from dem_manager import elevation_at
EARTH_RADIUS_M = 6_371_000

def radial_profile(center_lat, center_lon, bearing, radius_m, samples):
    distances = np.linspace(0, radius_m, samples)
    coords = [
        destination_point(center_lat, center_lon, bearing, d)
        for d in distances
    ]
    elevations = np.array(
        [elevation_at(lat, lon) for lat, lon in coords],
        dtype=float
    )
    return distances, elevations

def curvature_drop_m(distance_m, k_factor=4/3):
    effective_radius_m = EARTH_RADIUS_M * k_factor
    return distance_m**2 / (2 * effective_radius_m)

def analyze(lat, lon, radius_m, n_bearings, samples, antenna_height_m):
    bearings = np.linspace(0, 360, n_bearings, endpoint=False)
    results = []
    profiles = {}

    for bearing in bearings:
        print(f"Analyzing {bearing:.1f}°")

        distances, elevations = radial_profile(
            lat, lon, bearing, radius_m, samples
        )

        valid = ~np.isnan(elevations)
        if valid.sum() < 2:
            print(f"Skipping {bearing:.1f}°: outside DEM coverage")
            continue

        valid_distances = distances[valid]
        valid_elevations = elevations[valid]

        antenna_elevation = valid_elevations[0] + antenna_height_m

        terrain_drop = curvature_drop_m(valid_distances[1:])
        apparent_elevations = valid_elevations[1:] - terrain_drop
        terrain_angles = np.degrees(
            np.arctan2(
                apparent_elevations - antenna_elevation,
                valid_distances[1:],
            )
        )

        max_idx = int(np.argmax(terrain_angles))

        result = {
            "bearing_deg": float(bearing),
            "max_angle_deg": float(terrain_angles[max_idx]),
            "distance_m": float(valid_distances[1:][max_idx]),
            "terrain_elevation_m": float(valid_elevations[1:][max_idx]),
        }

        results.append(result)

        profiles[float(bearing)] = {
            "distance_m": distances,
            "elevation_m": elevations,
            "terrain_angle_deg": np.r_[np.nan, terrain_angles],
        }

    return results, profiles


def save_summary_csv(results, outdir):
    path = outdir / "horizon_summary.csv"

    with path.open("w") as f:
        f.write("bearing_deg,max_angle_deg,distance_m,terrain_elevation_m\n")
        for r in results:
            f.write(
                f"{r['bearing_deg']:.1f},"
                f"{r['max_angle_deg']:.4f},"
                f"{r['distance_m']:.1f},"
                f"{r['terrain_elevation_m']:.1f}\n"
            )


def plot_polar(results, outdir):
    bearings = np.radians([r["bearing_deg"] for r in results])
    angles = np.array([r["max_angle_deg"] for r in results])

    bearings = np.r_[bearings, bearings[0]]
    angles = np.r_[angles, angles[0]]

    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, polar=True)

    ax.plot(bearings, angles, marker="o")
    ax.fill(bearings, angles, alpha=0.2)

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_title("Terrain Horizon Angle vs Azimuth", pad=20)

    path = outdir / "polar_horizon.png"
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.show()


def plot_profile(profiles, requested_bearing, outdir):
    available = np.array(list(profiles.keys()))
    nearest = float(available[np.argmin(np.abs(available - requested_bearing))])
    p = profiles[nearest]

    plt.figure(figsize=(10, 4))
    plt.plot(p["distance_m"] / 1000, p["elevation_m"])

    plt.xlabel("Distance, km")
    plt.ylabel("Elevation, m")
    plt.title(f"Terrain Profile at {nearest:.1f}°")
    plt.grid(True)

    filename = f"profile_{int(round(nearest)):03d}_deg.png"
    plt.savefig(outdir / filename, dpi=200, bbox_inches="tight")
    plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Analyze terrain horizon obstruction around a GPS location."
    )

    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--radius-m", type=float, default=20_000)
    parser.add_argument("--n-bearings", type=int, default=72)
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--antenna-height-m", type=float, default=10)
    parser.add_argument("--profiles", type=float, nargs="*", default=[45, 90, 270])
    parser.add_argument("--outdir", default="output")

    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(exist_ok=True)

    results, profiles = analyze(
        lat=args.lat,
        lon=args.lon,
        radius_m=args.radius_m,
        n_bearings=args.n_bearings,
        samples=args.samples,
        antenna_height_m=args.antenna_height_m,
    )

    save_summary_csv(results, outdir)
    plot_polar(results, outdir)

    for bearing in args.profiles:
        plot_profile(profiles, bearing, outdir)

    print(f"\nSaved output to: {outdir.resolve()}")


if __name__ == "__main__":
    main()