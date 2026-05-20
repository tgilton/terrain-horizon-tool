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

