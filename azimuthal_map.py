import matplotlib.cm as cm
import matplotlib.colors as mcolors
import plotly.graph_objects as go

from geometry import destination_point
from horizon_map import CARDINAL_DIRECTIONS, DX_PATHS, angle_color

GLOBE_RADIUS_M = 19_500_000  # just inside the antipode, ~full hemisphere view
GLOBE_FULL_RADIUS_KM = 20_015  # pi * earth radius -- the antipodal edge, i.e. projection_scale=1


def _geodesic_line(lat, lon, bearing_deg, distance_m, steps=20):
    points = [
        destination_point(lat, lon, bearing_deg, distance_m * i / steps)
        for i in range(steps + 1)
    ]
    lons = [p[1] for p in points]
    lats = [p[0] for p in points]
    return lons, lats


def _colorscale(cmap_name="RdYlGn_r", stops=11):
    cmap = cm.get_cmap(cmap_name)
    return [[i / (stops - 1), mcolors.to_hex(cmap(i / (stops - 1)))] for i in range(stops)]


def build_azimuthal_plot(
    lat, lon, df, show_dx_paths=True, dx_radius_m=None, target=None,
    view_radius_m=None, threshold_deg=5.0,
):
    """Azimuthal-equidistant great-circle map centered on the QTH, with hover tooltips.

    target, if given, is a dict with label/lat/lon/bearing_deg/distance_m/required_angle_deg
    for a specific other station to plot and label distinctly from the DX bearing lines.

    view_radius_m sets the visible extent (None = whole globe), implemented via
    projection.scale rather than Plotly's native scroll/drag zoom -- that native
    interaction has a real bug where it can silently mirror the map. lon/lataxis_range
    was tried and rejected too: for a *rotated* azimuthal projection, Plotly applies
    those ranges in the pre-rotation coordinate frame, so cropping "500km around the
    station" actually crops an unrelated patch of the globe. projection.scale zooms
    around the already-rotated (correct) center and doesn't have either problem.
    """
    dx_radius_m = dx_radius_m or GLOBE_RADIUS_M
    # Scaled off the current view (not always the global dx_radius) so the puck
    # stays a large, easy-to-hover fraction of the frame at any zoom level.
    puck_radius_m = 0.15 * (view_radius_m if view_radius_m is not None else dx_radius_m)

    cmap = cm.get_cmap("RdYlGn_r")

    bearings = sorted(df["bearing_deg"].tolist())
    step = 360.0 / len(bearings) if len(bearings) > 1 else 360.0
    half_width = step / 2

    fig = go.Figure()

    for _, row in df.iterrows():
        bearing = float(row["bearing_deg"])
        angle = float(row["max_angle_deg"])
        color = angle_color(angle, threshold_deg, cmap)

        start, end = bearing - half_width, bearing + half_width
        arc = [
            destination_point(lat, lon, start + (end - start) * i / 6, puck_radius_m)
            for i in range(7)
        ]
        lons = [lon] + [p[1] for p in arc] + [lon]
        lats = [lat] + [p[0] for p in arc] + [lat]
        fig.add_trace(
            go.Scattergeo(
                lon=lons, lat=lats, mode="lines", fill="toself",
                fillcolor=color, line=dict(color=color, width=0.5),
                opacity=0.75, showlegend=False,
                hovertemplate=(
                    f"Bearing {bearing:.0f}°<br>"
                    f"Required takeoff angle: {angle:.2f}° "
                    f"({'clear' if angle <= threshold_deg else f'above your {threshold_deg:g}° threshold'})<br>"
                    f"Local obstruction distance: {row['distance_m'] / 1000:.1f} km"
                    "<extra></extra>"
                ),
            )
        )

    # Invisible trace purely to render a shared colorbar for the wedges above.
    fig.add_trace(
        go.Scattergeo(
            lon=[lon], lat=[lat], mode="markers",
            marker=dict(
                size=0, color=[0], cmin=0, cmax=2 * threshold_deg,
                colorscale=_colorscale(), showscale=True,
                colorbar=dict(
                    title=f"Required takeoff<br>angle (deg)<br><sup>{threshold_deg:g}° threshold = yellow</sup>",
                    len=0.7,
                    tickvals=[0, threshold_deg, 2 * threshold_deg],
                    ticktext=["0", f"{threshold_deg:g} (threshold)", f"{2 * threshold_deg:g}+"],
                ),
            ),
            showlegend=False, hoverinfo="skip",
        )
    )

    if show_dx_paths:
        for label, bearing in DX_PATHS.items():
            lons, lats = _geodesic_line(lat, lon, bearing, dx_radius_m)
            fig.add_trace(
                go.Scattergeo(
                    lon=lons, lat=lats, mode="lines",
                    line=dict(color="black", width=1, dash="dash"),
                    showlegend=False, hoverinfo="skip",
                )
            )
            fig.add_trace(
                go.Scattergeo(
                    lon=[lons[-1]], lat=[lats[-1]], mode="text",
                    text=[label], textposition="middle center",
                    textfont=dict(size=11, color="black", family="Arial Black"),
                    showlegend=False, hoverinfo="skip",
                )
            )

    if target is not None:
        lons, lats = _geodesic_line(
            lat, lon, target["bearing_deg"], target["distance_m"], steps=40
        )
        fig.add_trace(
            go.Scattergeo(
                lon=lons, lat=lats, mode="lines",
                line=dict(color="#d62728", width=2),
                showlegend=False,
                hovertemplate=(
                    f"To {target['label']}<br>"
                    f"Bearing {target['bearing_deg']:.1f}°, "
                    f"{target['distance_m'] / 1000:.0f} km"
                    "<extra></extra>"
                ),
            )
        )
        fig.add_trace(
            go.Scattergeo(
                lon=[target["lon"]], lat=[target["lat"]], mode="markers+text",
                marker=dict(symbol="star", size=13, color="#d62728", line=dict(color="white", width=1)),
                text=[target["label"]], textposition="top center",
                textfont=dict(size=11, color="#d62728", family="Arial Black"),
                showlegend=False,
                hovertemplate=(
                    f"{target['label']}<br>"
                    f"Bearing {target['bearing_deg']:.1f}°, "
                    f"{target['distance_m'] / 1000:.0f} km<br>"
                    f"Terrain-required takeoff angle: "
                    + (
                        f"{target['required_angle_deg']:.2f}°"
                        if target["required_angle_deg"] is not None else "n/a"
                    )
                    + "<extra></extra>"
                ),
            )
        )

    cardinal_radius_m = 1.3 * puck_radius_m
    for label, bearing in CARDINAL_DIRECTIONS.items():
        pt_lat, pt_lon = destination_point(lat, lon, bearing, cardinal_radius_m)
        fig.add_trace(
            go.Scattergeo(
                lon=[pt_lon], lat=[pt_lat], mode="text",
                text=[label], textfont=dict(size=10, color="#666666"),
                showlegend=False, hoverinfo="skip",
            )
        )

    fig.add_trace(
        go.Scattergeo(
            lon=[lon], lat=[lat], mode="markers",
            marker=dict(symbol="triangle-up", size=12, color="blue", line=dict(color="white", width=1)),
            showlegend=False, hoverinfo="skip",
        )
    )

    geos_kwargs = dict(
        projection_type="azimuthal equidistant",
        projection_rotation=dict(lon=lon, lat=lat, roll=0),
        showland=True, landcolor="#f2efe9",
        showocean=True, oceancolor="#cfe3f0",
        showcoastlines=True, coastlinewidth=0.6,
        showcountries=True, countrywidth=0.5,
        showlakes=True, lakecolor="#cfe3f0",
        resolution=50,
    )
    if view_radius_m is not None:
        geos_kwargs["projection_scale"] = GLOBE_FULL_RADIUS_KM / (view_radius_m / 1000)
    fig.update_geos(**geos_kwargs)

    fig.update_layout(
        title=f"Azimuthal Equidistant View — QTH {lat:.4f}, {lon:.4f}<br>"
              "<sup>Straight lines from center = true bearing and distance. Hover a wedge or line for details.</sup>",
        margin=dict(l=0, r=0, t=60, b=0),
        height=700,
        dragmode=False,  # native drag/scroll-zoom on this projection can mirror the map; use the radius control instead
    )
    return fig
