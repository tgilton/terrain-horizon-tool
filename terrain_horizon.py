import argparse
import math
import time
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


def fetch_elevations(coords, batch_size=25, pause_s=2.0):
    elevations = []
    url = "https://api.open-meteo.com/v1/elevation"

    for i in range(0, len(coords), batch_size):
        batch = coords[i:i + batch_size]

        lat_str = ",".join(f"{lat:.6f}" for lat, _ in batch)
        lon_str = ",".join(f"{lon:.6f}" for _, lon in batch)

        params = {
            "latitude": lat_str,
            "longitude": lon_str,
        }

        for attempt in range(6):
            try:
                r = requests.get(url, params=params, timeout=60)
            except requests.exceptions.RequestException as e:
                wait_s = 10 * (attempt + 1)
                print(f"Request failed: {e}")
                print(f"Waiting {wait_s} seconds...")
                time.sleep(wait_s)
                continue

            if r.status_code == 429:
                wait_s = 10 * (attempt + 1)
                print(f"Rate limited. Waiting {wait_s} seconds...")
                time.sleep(wait_s)
                continue

            r.raise_for_status()
            data = r.json()
            elevations.extend(data["elevation"])
            break

        else:
            raise RuntimeError(
                "Elevation API failed repeatedly with rate limiting."
            )

        time.sleep(pause_s)

    if len(elevations) != len(coords):
        raise RuntimeError(
            f"Elevation count mismatch: got {len(elevations)}, expected {len(coords)}"
        )

    return np.array(elevations, dtype=float)


def radial_profile(center_lat, center_lon, bearing, radius_m, samples):
    distances = np.linspace(0, radius_m, samples)
    coords = [
        destination_point(center_lat, center_lon, bearing, d)
        for d in distances
    ]
    elevations = fetch_elevations(coords)
    return distances, elevations


def analyze(lat, lon, radius_m, n_bearings, samples, antenna_height_m):
    bearings = np.linspace(0, 360, n_bearings, endpoint=False)
    results = []
    profiles = {}

    for bearing in bearings:
        print(f"Analyzing {bearing:.1f}°")

        distances, elevations = radial_profile(
            lat, lon, bearing, radius_m, samples
        )

        antenna_elevation = elevations[0] + antenna_height_m

        terrain_angles = np.degrees(
            np.arctan2(
                elevations[1:] - antenna_elevation,
                distances[1:],
            )
        )

        max_idx = int(np.argmax(terrain_angles))

        result = {
            "bearing_deg": float(bearing),
            "max_angle_deg": float(terrain_angles[max_idx]),
            "distance_m": float(distances[1:][max_idx]),
            "terrain_elevation_m": float(elevations[1:][max_idx]),
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