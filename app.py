import subprocess
import sys
from pathlib import Path
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from horizon_map import build_horizon_map

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
if st.button("Run terrain analysis"):
    with st.spinner("Running analysis..."):
        result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        st.success("Analysis complete")
        st.text(result.stdout[-3000:])
    else:
        st.error("Analysis failed")
        st.text(result.stderr)
summary_file = outdir / "horizon_summary.csv"
polar_file = outdir / "polar_horizon.png"
takeoff_file = outdir / "takeoff_angle_polar.png"
if summary_file.exists():
    df = pd.read_csv(summary_file)

    st.header("Horizon Map")
    st.caption(
        "Each wedge points toward a compass bearing and reaches out to the "
        "terrain obstruction in that direction. Color = takeoff angle needed "
        "to clear the horizon (green = low/clear, red = high/blocked)."
    )
    horizon_map = build_horizon_map(lat, lon, df, show_dx_paths=show_dx_paths)
    st_folium(horizon_map, width=None, height=600, returned_objects=[])

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
if takeoff_file.exists():
    st.header("DX Takeoff Angle")
    st.image(str(takeoff_file))
profile_files = sorted(outdir.glob("profile_*_deg.png"))
if profile_files:
    st.header("Terrain Profiles")
    for path in profile_files:
        st.image(str(path), caption=path.name)