import json
import math
import subprocess
import sys
from pathlib import Path
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from horizon_map import build_horizon_map
from download_dem import missing_tiles, download_tile, AVG_TILE_SIZE_MB

DEM_DIR = "dem_1"
DEM_RESOLUTION = "1"

st.set_page_config(page_title="Terrain Horizon Tool", layout="wide")
st.title("Terrain Horizon Tool")
st.sidebar.header("Station")
lat = st.sidebar.number_input("Latitude", value=43.56751, format="%.6f")
lon = st.sidebar.number_input("Longitude", value=-116.14486, format="%.6f")
antenna_height = st.sidebar.number_input("Antenna height, m", value=10.0)
st.sidebar.header("Analysis")
radius_m = st.sidebar.number_input("Radius, m", value=400000, step=10000)
n_bearings = st.sidebar.number_input("Bearings", value=72, step=12)
samples = st.sidebar.number_input("Samples per bearing", value=800, step=100)
profiles = st.sidebar.text_input("Profile bearings", value="45 90 180 270")
st.sidebar.header("Map")
show_dx_paths = st.sidebar.checkbox("Show DX azimuths", value=True)

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


def _params_match_current(params_file, lat, lon, radius_m, n_bearings, samples, antenna_height):
    if not params_file.exists():
        return False
    with params_file.open() as f:
        saved = json.load(f)
    return (
        math.isclose(saved.get("lat", 0.0), lat, abs_tol=1e-6)
        and math.isclose(saved.get("lon", 0.0), lon, abs_tol=1e-6)
        and int(saved.get("radius_m", -1)) == int(radius_m)
        and int(saved.get("n_bearings", -1)) == int(n_bearings)
        and int(saved.get("samples", -1)) == int(samples)
        and math.isclose(saved.get("antenna_height_m", -1.0), antenna_height, abs_tol=1e-6)
    )


results_current = _params_match_current(
    params_file, lat, lon, radius_m, n_bearings, samples, antenna_height
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
        "terrain obstruction in that direction. Color = takeoff angle needed "
        "to clear the horizon (green = low/clear, red = high/blocked)."
    )
    horizon_map = build_horizon_map(lat, lon, df, show_dx_paths=show_dx_paths)
    st_folium(horizon_map, width=None, height=600, returned_objects=[])

    st.download_button(
        "Download interactive map (.html)",
        data=horizon_map.get_root().render(),
        file_name=f"horizon_map_{lat:.4f}_{lon:.4f}.html",
        mime="text/html",
        help="A self-contained file you can share -- opens with full pan/zoom/tooltips in any browser, no server needed.",
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