import argparse
import math
import time
from pathlib import Path

import rasterio
from pyproj import Transformer

import matplotlib.pyplot as plt
import numpy as np
# import requests
from dem_manager import DEMManager
from analysis import analyze, save_summary_csv

EARTH_RADIUS_M = 6_371_000

dem_manager = DEMManager()

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
    bearing = float(available[np.argmin(np.abs(available - requested_bearing))])
    profile = profiles[bearing]
    distance_km = profile["distance_m"] / 1000
    elevation_m = profile["elevation_m"]
    angle_deg = profile["terrain_angle_deg"]
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(distance_km, elevation_m, label="Terrain elevation")
    ax1.set_xlabel("Distance, km")
    ax1.set_ylabel("Elevation, m")
    ax1.grid(True)
    ax2 = ax1.twinx()
    ax2.plot(distance_km, angle_deg, linestyle="--", label="Apparent RF angle")
    ax2.set_ylabel("Apparent angle, degrees")
    ax1.set_title(f"Terrain and RF Obstruction Angle at {bearing:.1f}°")
    fig.tight_layout()
    plt.savefig(outdir / f"profile_{bearing:.0f}_deg.png", dpi=200)
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