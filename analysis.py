import hashlib
import json

import numpy as np
from dem_manager import DEMManager
from geometry import destination_point
EARTH_RADIUS_M = 6_371_000
dem_manager = DEMManager()

def curvature_drop_m(distance_m, k_factor=4/3):
    effective_radius_m = EARTH_RADIUS_M * k_factor
    return distance_m**2 / (2 * effective_radius_m)
def radial_profile(center_lat, center_lon, bearing, radius_m, samples):
    distances = np.linspace(0, radius_m, samples)
    coords = [
        destination_point(center_lat, center_lon, bearing, d)
        for d in distances
    ]

    elevations = np.array(
        [
            dem_manager.elevation_at(
                lat,
                lon,
                d
            )
            for (lat, lon), d in zip(coords, distances)
        ],
        dtype=float
    )
    return distances, elevations

def terrain_angle_along_bearing(lat, lon, bearing, radius_m, samples, antenna_height_m):
    """Exact terrain-obstruction result for one bearing, plus the full profile used to derive it.

    Returns (result, profile) where result is None if the bearing has fewer
    than two valid (DEM-covered) samples.
    """
    distances, elevations = radial_profile(lat, lon, bearing, radius_m, samples)

    valid = ~np.isnan(elevations)
    if valid.sum() < 2:
        return None, None

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

    end_lat, end_lon = destination_point(
        lat,
        lon,
        bearing,
        valid_distances[1:][max_idx]
    )

    result = {
        "bearing_deg": float(bearing),
        "max_angle_deg": float(terrain_angles[max_idx]),
        "distance_m": float(valid_distances[1:][max_idx]),
        "terrain_elevation_m": float(valid_elevations[1:][max_idx]),
        "obstruction_lat": float(end_lat),
        "obstruction_lon": float(end_lon),
    }

    # terrain_angles only covers the valid (non-NaN-elevation) samples,
    # which can be a strict subset of the full profile when part of it
    # falls outside DEM coverage (e.g. offshore). Scatter it back into a
    # full-length array so it lines up with distance_m/elevation_m for
    # plotting.
    valid_indices = np.flatnonzero(valid)
    full_terrain_angles = np.full(samples, np.nan)
    full_terrain_angles[valid_indices[1:]] = terrain_angles

    profile = {
        "distance_m": distances,
        "elevation_m": elevations,
        "terrain_angle_deg": full_terrain_angles,
    }

    return result, profile


def analyze(lat, lon, radius_m, n_bearings, samples, antenna_height_m):
    bearings = np.linspace(0, 360, n_bearings, endpoint=False)
    results = []
    profiles = {}

    for bearing in bearings:
        print(f"Analyzing {bearing:.1f}°")

        result, profile = terrain_angle_along_bearing(
            lat, lon, bearing, radius_m, samples, antenna_height_m
        )
        if result is None:
            print(f"Skipping {bearing:.1f}°: outside DEM coverage")
            continue

        results.append(result)
        profiles[float(bearing)] = profile

    return results, profiles

def save_summary_csv(results, outdir):
    path = outdir / "horizon_summary.csv"

    with path.open("w") as f:
        f.write("bearing_deg,max_angle_deg,distance_m,terrain_elevation_m,obstruction_lat,obstruction_lon\n")
        for r in results:
            f.write(
                f"{r['bearing_deg']:.1f},"
                f"{r['max_angle_deg']:.4f},"
                f"{r['distance_m']:.1f},"
                f"{r['terrain_elevation_m']:.1f},"
                f"{r['obstruction_lat']:.8f},"
                f"{r['obstruction_lon']:.8f}\n"
            )

    return path


def hash_file(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def save_run_params(params, outdir):
    path = outdir / "run_params.json"
    with path.open("w") as f:
        json.dump(params, f)

