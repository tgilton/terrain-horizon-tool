import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import requests


EARTH_RADIUS_M = 6_371_000


def destination_point(lat, lon, bearing_deg, distance_m):
    lat1, lon1 = math.radians(lat), math.radians(lon)
    bearing = math.radians(bearing_deg)
    d = distance_m / EARTH_RADIUS_M

    lat2 = math.asin(
        math.sin(lat1) * math.cos(d)
        + math.cos(lat1) * math.sin(d) * math.cos(bearing)
    )

    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(d) * math.cos(lat1),
        math.cos(d) - math.sin(lat1) * math.sin(lat2),
    )

    return math.degrees(lat2), math.degrees(lon2)


def fetch_elevation(lat, lon):
    url = "https://api.open-meteo.com/v1/elevation"
    r = requests.get(url, params={"latitude": lat, "longitude": lon}, timeout=20)
    r.raise_for_status()
    return float(r.json()["elevation"][0])


def analyze_direction(center_lat, center_lon, bearing, radius_m, samples, antenna_height_m):
    distances = np.linspace(0, radius_m, samples)

    elevations = []
    for d in distances:
        lat, lon = destination_point(center_lat, center_lon, bearing, d)
        elevations.append(fetch_elevation(lat, lon))

    elevations = np.array(elevations)

    antenna_elevation = elevations[0] + antenna_height_m
    terrain_angles = np.degrees(
        np.arctan2(elevations[1:] - antenna_elevation, distances[1:])
    )

    max_idx = np.argmax(terrain_angles)

    return {
        "bearing": bearing,
        "max_angle_deg": terrain_angles[max_idx],
        "distance_m": distances[1:][max_idx],
        "distances": distances,
        "elevations": elevations,
    }


def run_analysis(lat, lon, radius_m, n_bearings, samples, antenna_height_m):
    bearings = np.linspace(0, 360, n_bearings, endpoint=False)
    results = []

    for bearing in bearings:
        print(f"Analyzing {bearing:.1f} degrees...")
        results.append(
            analyze_direction(lat, lon, bearing, radius_m, samples, antenna_height_m)
        )

    return results


def plot_polar(results, outdir):
    bearings = np.radians([r["bearing"] for r in results])
    angles = np.array([r["max_angle_deg"] for r in results])

    bearings = np.append(bearings, bearings[0])
    angles = np.append(angles, angles[0])

    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, polar=True)

    ax.plot(bearings, angles, marker="o")
    ax.fill(bearings, angles, alpha=0.2)

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_title("Terrain Horizon Angle vs Azimuth")

    path = outdir / "polar_horizon.png"
    plt.savefig(path, dpi=200)
    plt.show()


def save_csv(results, outdir):
    path = outdir / "horizon_summary.csv"

    with path.open("w") as f:
        f.write("bearing_deg,max_angle_deg,distance_m\n")
        for r in results:
            f.write(f"{r['bearing']:.1f},{r['max_angle_deg']:.4f},{r['distance_m']:.1f}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--radius-m", type=float, default=20_000)
    parser.add_argument("--n-bearings", type=int, default=36)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--antenna-height-m", type=float, default=10)
    parser.add_argument("--outdir", default="output")

    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(exist_ok=True)

    results = run_analysis(
        args.lat,
        args.lon,
        args.radius_m,
        args.n_bearings,
        args.samples,
        args.antenna_height_m,
    )

    save_csv(results, outdir)
    plot_polar(results, outdir)

    print(f"Saved results in: {outdir.resolve()}")


if __name__ == "__main__":
    main()