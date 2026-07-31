import json
import math
import subprocess
import sys
from pathlib import Path
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from horizon_map import build_horizon_map
from azimuthal_map import build_azimuthal_plot
from download_dem import missing_tiles, download_tile, AVG_TILE_SIZE_MB
from analysis import hash_file, terrain_angle_along_bearing
from geometry import bearing_distance, maidenhead_to_latlon

DEM_DIR = "dem_1"
DEM_RESOLUTION = "1"

st.set_page_config(page_title="Terrain Horizon Tool", layout="wide")
st.title("Terrain Horizon Tool")
st.sidebar.header("Station")
lat = st.sidebar.number_input("Latitude", value=43.56751, format="%.6f")
lon = st.sidebar.number_input("Longitude", value=-116.14486, format="%.6f")
antenna_height = st.sidebar.number_input("Antenna height, m", value=10.0)
threshold_deg = st.sidebar.number_input(
    "Usable takeoff angle, deg", value=5.0, step=0.5, min_value=0.1,
    help="The takeoff angle your antenna needs for normal DX propagation. Maps color "
    "green below this and red above it -- red means terrain is forcing you higher "
    "than your antenna needs, not just 'worse than your other bearings'.",
)
st.sidebar.header("Analysis")
radius_m = st.sidebar.number_input("Radius, m", value=400000, step=10000)
n_bearings = st.sidebar.number_input("Bearings", value=72, step=12)
samples = st.sidebar.number_input("Samples per bearing", value=800, step=100)
profiles = st.sidebar.text_input("Profile bearings", value="0 90 180 270")
st.sidebar.header("Map")
show_dx_paths = st.sidebar.checkbox("Show DX azimuths", value=True)
show_azimuthal = st.sidebar.checkbox("Show azimuthal-equidistant view", value=False)
st.sidebar.header("DX Check")
target_input = st.sidebar.text_input(
    "Target station",
    value="",
    placeholder="e.g. FN31pr or 41.5,-71.3",
    help="Maidenhead grid locator or 'lat,lon'. Computes true bearing, distance, "
    "and the exact terrain-required takeoff angle toward this station.",
)

outdir = Path("output")
cmd = [
    sys.executable, "terrain_horizon.py",
    "--lat", str(lat),
    "--lon", str(lon),
    "--radius-m", str(int(radius_m)),
    "--n-bearings", str(int(n_bearings)),
    "--samples", str(int(samples)),
    "--antenna-height-m", str(float(antenna_height)),
    "--profiles", *profiles.split(),
]
st.sidebar.header("DEM Coverage (US only)")
radius_km = radius_m / 1000
tiles_needed = missing_tiles(lat, lon, radius_km, DEM_DIR, DEM_RESOLUTION)
if tiles_needed:
    est_mb = len(tiles_needed) * AVG_TILE_SIZE_MB[DEM_RESOLUTION]
    st.sidebar.warning(
        f"{len(tiles_needed)} elevation tile(s) missing for this QTH/radius "
        f"(~{est_mb / 1024:.1f} GB). Some tiles won't exist over ocean/non-US "
        f"area and will be skipped automatically."
    )
    if st.sidebar.button("Download missing tiles"):
        progress = st.sidebar.progress(0.0)
        status = st.sidebar.empty()
        for i, tile in enumerate(tiles_needed):
            status.text(f"Downloading {tile} ({i + 1}/{len(tiles_needed)})")
            download_tile(tile, Path(DEM_DIR), DEM_RESOLUTION)
            progress.progress((i + 1) / len(tiles_needed))
        status.text("Done.")
        st.rerun()
else:
    st.sidebar.success("All elevation tiles present for this QTH/radius.")

if tiles_needed:
    st.button("Run terrain analysis", disabled=True)
    st.caption(
        "Disabled until DEM coverage is verified for this station/radius -- "
        "use 'Download missing tiles' in the sidebar first."
    )
    run_clicked = False
else:
    run_clicked = st.button("Run terrain analysis")

if run_clicked:
    with st.spinner("Running analysis..."):
        result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        st.success("Analysis complete")
        with st.expander("Analysis log"):
            st.text(result.stdout[-3000:])
    else:
        st.error("Analysis failed")
        st.text(result.stderr)
summary_file = outdir / "horizon_summary.csv"
params_file = outdir / "run_params.json"
polar_file = outdir / "polar_horizon.png"


def _params_match_current(
    params_file, summary_file, lat, lon, radius_m, n_bearings, samples, antenna_height
):
    if not params_file.exists() or not summary_file.exists():
        return False
    with params_file.open() as f:
        saved = json.load(f)
    # The hash ties run_params.json to the exact horizon_summary.csv it was
    # written with -- without it, a summary_file swapped in independently
    # (e.g. restored from git) could coincidentally match stale params.
    if saved.get("summary_hash") != hash_file(summary_file):
        return False
    return (
        math.isclose(saved.get("lat", 0.0), lat, abs_tol=1e-6)
        and math.isclose(saved.get("lon", 0.0), lon, abs_tol=1e-6)
        and int(saved.get("radius_m", -1)) == int(radius_m)
        and int(saved.get("n_bearings", -1)) == int(n_bearings)
        and int(saved.get("samples", -1)) == int(samples)
        and math.isclose(saved.get("antenna_height_m", -1.0), antenna_height, abs_tol=1e-6)
    )


def _resolve_target(text, lat, lon, radius_m, samples, antenna_height_m):
    text = text.strip()
    if "," in text:
        parts = [p.strip() for p in text.split(",")]
        if len(parts) != 2:
            raise ValueError("Expected a Maidenhead grid locator or 'lat,lon'.")
        t_lat, t_lon = float(parts[0]), float(parts[1])
    else:
        t_lat, t_lon = maidenhead_to_latlon(text)

    bearing_deg, distance_m = bearing_distance(lat, lon, t_lat, t_lon)
    result, _ = terrain_angle_along_bearing(
        lat, lon, bearing_deg, radius_m, samples, antenna_height_m
    )

    return {
        "label": text,
        "lat": t_lat,
        "lon": t_lon,
        "bearing_deg": bearing_deg,
        "distance_m": distance_m,
        "required_angle_deg": result["max_angle_deg"] if result else None,
    }


def _dx_verdict(distance_m, required_angle_deg, threshold_deg):
    """Is this path terrain-impeded, given the operator's own antenna threshold?

    Short paths (roughly within the skip zone for typical HF bands) are a special
    case: NVIS wants a HIGH takeoff angle on purpose, so terrain forcing the angle
    up there isn't a problem -- it's irrelevant, since NVIS doesn't rely on your
    low-angle response anyway. The threshold comparison only applies once the
    path is long enough that normal (low-angle) propagation is what's needed.
    """
    distance_km = distance_m / 1000

    if required_angle_deg is None:
        return (
            "No DEM coverage along this bearing (open water or outside the analysis "
            "radius) -- terrain is unlikely to be the limiting factor here."
        )

    if distance_km < 500:
        return (
            f"This is short/skip-zone range ({distance_km:.0f} km) -- NVIS "
            f"(near-vertical, high-angle) is the normal mode here, not low-angle DX, "
            f"so the {required_angle_deg:.1f}° terrain floor isn't a real constraint."
        )

    if required_angle_deg <= threshold_deg:
        return (
            f"CLEAR -- terrain requires {required_angle_deg:.1f}°, at or below your "
            f"{threshold_deg:g}° threshold. Your antenna's normal takeoff angle should "
            f"cover this path under normal conditions."
        )
    return (
        f"IMPEDED -- terrain requires {required_angle_deg:.1f}°, above your "
        f"{threshold_deg:g}° threshold. This direction needs unusually good "
        f"propagation (high MUF, ducting, or a multi-hop workaround) to work."
    )


results_current = _params_match_current(
    params_file, summary_file, lat, lon, radius_m, n_bearings, samples, antenna_height
)

if summary_file.exists() and not results_current:
    st.info(
        "The saved results on disk were computed for a different station or "
        "set of parameters. Click 'Run terrain analysis' to compute results "
        "for the station currently entered above."
    )
elif summary_file.exists():
    df = pd.read_csv(summary_file)

    st.header("Horizon Map")
    st.caption(
        "Each wedge points toward a compass bearing and reaches out to the "
        "terrain obstruction in that direction. Color is relative to your "
        f"{threshold_deg:g}° usable-takeoff-angle threshold (set in the sidebar) -- "
        "green means terrain isn't the limiting factor, red means terrain is "
        "forcing you above what your antenna needs for normal DX."
    )
    horizon_map = build_horizon_map(lat, lon, df, show_dx_paths=show_dx_paths, threshold_deg=threshold_deg)
    st_folium(horizon_map, width=None, height=600, returned_objects=[])

    st.download_button(
        "Download interactive map (.html)",
        data=horizon_map.get_root().render(),
        file_name=f"horizon_map_{lat:.4f}_{lon:.4f}.html",
        mime="text/html",
        help="A self-contained file you can share -- opens with full pan/zoom/tooltips in any browser, no server needed.",
    )

    target = None
    if target_input.strip():
        try:
            target = _resolve_target(target_input, lat, lon, radius_m, samples, antenna_height)
        except ValueError as e:
            st.error(str(e))

    if target:
        st.header("DX Check")
        col1, col2, col3 = st.columns(3)
        col1.metric("Bearing", f"{target['bearing_deg']:.1f}°")
        col2.metric("Distance", f"{target['distance_m'] / 1000:,.0f} km")
        col3.metric(
            "Terrain-required takeoff angle",
            f"{target['required_angle_deg']:.2f}°" if target["required_angle_deg"] is not None else "n/a",
        )
        st.caption(_dx_verdict(target["distance_m"], target["required_angle_deg"], threshold_deg))

    if show_azimuthal:
        st.header("Azimuthal Equidistant Map")
        st.caption(
            "Centered on the QTH -- every straight line drawn from the center "
            "has true bearing and true distance, unlike the Mercator map above "
            "(which distorts both, more so with distance and latitude). This "
            "is the classic ham-radio 'great circle map' projection. Hover a "
            "wedge or line for its exact bearing/distance/takeoff angle. Note: "
            "the puck's wedge **length is fixed and not meaningful** here (real "
            "obstruction distances are too small to see at this scale) -- only "
            "**color** carries information, unlike the Horizon Map above where "
            "length is the real obstruction distance."
        )
        view_options = {
            "Global": None, "10,000 km": 10_000_000, "5,000 km": 5_000_000,
            "2,000 km": 2_000_000, "1,000 km": 1_000_000, "500 km": 500_000,
        }
        view_label = st.select_slider("Map view radius", options=list(view_options), value="Global")
        st.caption(
            "This chart's built-in scroll/drag zoom is disabled -- Plotly's azimuthal "
            "projection has a bug where interactive zoom can silently mirror the map. "
            "Use the slider above instead."
        )
        with st.spinner("Rendering azimuthal map..."):
            azimuthal_fig = build_azimuthal_plot(
                lat, lon, df, show_dx_paths=show_dx_paths, target=target,
                view_radius_m=view_options[view_label], threshold_deg=threshold_deg,
            )
        st.plotly_chart(
            azimuthal_fig,
            use_container_width=True,
            config={
                "scrollZoom": False,
                "toImageButtonOptions": {
                    "filename": f"azimuthal_map_{lat:.4f}_{lon:.4f}",
                    "format": "png",
                },
            },
        )

        st.download_button(
            "Download interactive azimuthal map (.html)",
            data=azimuthal_fig.to_html(
                include_plotlyjs=True, full_html=True,
                config={"scrollZoom": False},
            ),
            file_name=f"azimuthal_map_{lat:.4f}_{lon:.4f}.html",
            mime="text/html",
            help="A self-contained file with hover tooltips -- opens in any browser, no server needed. "
            "Use the camera icon in the chart toolbar above to save the current view as a PNG.",
        )

    st.header("Horizon Summary")
    st.dataframe(df)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Best azimuths")
        st.dataframe(df.sort_values("max_angle_deg").head(10))
    with col2:
        st.subheader("Worst azimuths")
        st.dataframe(df.sort_values("max_angle_deg", ascending=False).head(10))

    if polar_file.exists():
        st.header("Terrain Horizon")
        st.image(str(polar_file))
    profile_files = sorted(outdir.glob("profile_*_deg.png"))
    if profile_files:
        st.header("Terrain Profiles")
        for path in profile_files:
            st.image(str(path), caption=path.name)