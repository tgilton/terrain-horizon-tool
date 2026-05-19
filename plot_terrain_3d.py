import math
import numpy as np
import plotly.graph_objects as go
import rasterio
from pathlib import Path

DEM_FILE = Path("dem/USGS_13_n44w117.tif")

CENTER_LAT = 43.56751
CENTER_LON = -116.14486

WINDOW_DEG = 0.35  # roughly 30-40 km depending on latitude
DOWNSAMPLE = 8

with rasterio.open(DEM_FILE) as ds:
    left = CENTER_LON - WINDOW_DEG
    right = CENTER_LON + WINDOW_DEG
    bottom = CENTER_LAT - WINDOW_DEG
    top = CENTER_LAT + WINDOW_DEG

    row_min, col_min = ds.index(left, top)
    row_max, col_max = ds.index(right, bottom)

    row_min, row_max = sorted([row_min, row_max])
    col_min, col_max = sorted([col_min, col_max])

    data = ds.read(1)[row_min:row_max:DOWNSAMPLE, col_min:col_max:DOWNSAMPLE]

    rows, cols = data.shape
    lon_vals = np.linspace(left, right, cols)
    lat_vals = np.linspace(bottom, top, rows)

    xs = ((lon_vals - CENTER_LON) * 111.32 * math.cos(math.radians(CENTER_LAT)))

    ys = (
            (lat_vals - CENTER_LAT) * 111.32
    )

fig = go.Figure(
    data=[
        go.Surface(
            x=xs,
            y=ys,
            z=data,
            colorscale="Earth",
            showscale=True,
        )
    ]
)

cube_size = 0.8
x0 = 0
y0 = 0
z0 = 840
station_height = 150

fig.add_trace(
    go.Scatter3d(
        x=[0, 0],
        y=[0, 0],
        z=[840, 840 + station_height],
        mode="lines",
        line=dict(color="red", width=10),
        name="Tower"
    )
)

fig.add_trace(
    go.Scatter3d(
        x=[0],
        y=[0],
        z=[840 + station_height],
        mode="markers",
        marker=dict(size=6, color="yellow"),
        name="Antenna"
    )
)

fig.update_layout(
    title="3D Terrain Around Station",
    scene=dict(
        xaxis_title="East/West Distance (km)",
        yaxis_title="North/South Distance (km)",
        zaxis_title="Elevation, m",
        aspectmode="manual",
        aspectratio=dict(x=1, y=1, z=0.25),
    ),
)

from pathlib import Path
import webbrowser
html_path = Path("output/terrain_3d.html")
fig.write_html(html_path, auto_open=False)
webbrowser.open(html_path.resolve().as_uri())