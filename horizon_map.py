import folium
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from branca.colormap import LinearColormap

from geometry import destination_point

DX_PATHS = {
    "Pituffik/Thule": 16,
    "Iceland": 33,
    "Greenland": 37,
    "Europe": 40,
    "Japan": 315,
    "Alaska": 325,
    "Hawaii": 250,
    "Australia": 245,
    "South America": 140,
}

CARDINAL_DIRECTIONS = {"N": 0, "E": 90, "S": 180, "W": 270}


def angle_fraction(angle_deg, threshold_deg):
    """Maps a required-takeoff-angle to [0,1] on a fixed (not data-relative) scale:
    0deg -> 0 (fully green), threshold_deg -> 0.5 (yellow), 2*threshold_deg -> 1 (fully red).

    This is deliberately NOT normalized to the min/max of any particular run's data --
    "red" should always mean "terrain forces an angle notably above what your antenna
    needs," not just "the worst bearing this station happens to have."
    """
    span = 2 * threshold_deg if threshold_deg > 0 else 1.0
    return max(0.0, min(1.0, angle_deg / span))


def angle_color(angle_deg, threshold_deg, cmap):
    return mcolors.to_hex(cmap(angle_fraction(angle_deg, threshold_deg)))


def _wedge_points(lat, lon, bearing_deg, half_width_deg, radius_m, arc_steps=6):
    start = bearing_deg - half_width_deg
    end = bearing_deg + half_width_deg
    arc = [
        destination_point(lat, lon, start + (end - start) * i / arc_steps, radius_m)
        for i in range(arc_steps + 1)
    ]
    return [(lat, lon)] + arc + [(lat, lon)]


def build_horizon_map(lat, lon, df, show_dx_paths=True, dx_radius_m=None, threshold_deg=5.0):
    fmap = folium.Map(location=[lat, lon], zoom_start=9, tiles="OpenStreetMap")

    bearings = sorted(df["bearing_deg"].tolist())
    step = 360.0 / len(bearings) if len(bearings) > 1 else 360.0
    half_width = step / 2

    cmap = cm.get_cmap("RdYlGn_r")

    wedge_layer = folium.FeatureGroup(name="Takeoff angle by bearing")
    for _, row in df.iterrows():
        bearing = float(row["bearing_deg"])
        angle = float(row["max_angle_deg"])
        distance_m = float(row["distance_m"])
        color = angle_color(angle, threshold_deg, cmap)

        points = _wedge_points(lat, lon, bearing, half_width, distance_m)
        folium.Polygon(
            locations=points,
            color=color,
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.55,
            tooltip=(
                f"Bearing {bearing:.0f}°<br>"
                f"Required takeoff angle {angle:.2f}° "
                f"({'clear' if angle <= threshold_deg else 'above your ' + str(threshold_deg) + '° threshold'})<br>"
                f"Obstruction {distance_m / 1000:.1f} km"
            ),
        ).add_to(wedge_layer)
    wedge_layer.add_to(fmap)

    folium.Marker(
        [lat, lon],
        tooltip="QTH",
        icon=folium.Icon(color="blue", icon="tower-broadcast", prefix="fa"),
    ).add_to(fmap)

    cardinal_radius_m = float(df["distance_m"].median())
    cardinal_layer = folium.FeatureGroup(name="Cardinal directions (N/E/S/W)")
    for label, bearing in CARDINAL_DIRECTIONS.items():
        pt_lat, pt_lon = destination_point(lat, lon, bearing, cardinal_radius_m)
        folium.Marker(
            [pt_lat, pt_lon],
            icon=folium.DivIcon(
                html=(
                    '<div style="font-size:10px;font-weight:400;color:#666;'
                    'opacity:0.7;white-space:nowrap;">' + label + "</div>"
                )
            ),
        ).add_to(cardinal_layer)
    cardinal_layer.add_to(fmap)

    if show_dx_paths:
        radius_m = dx_radius_m or float(df["distance_m"].max()) * 1.3
        dx_layer = folium.FeatureGroup(name="DX azimuths")
        for label, bearing in DX_PATHS.items():
            end_lat, end_lon = destination_point(lat, lon, bearing, radius_m)
            folium.PolyLine(
                locations=[(lat, lon), (end_lat, end_lon)],
                color="black",
                weight=1.5,
                dash_array="5,5",
                tooltip=f"{label} ({bearing}°)",
            ).add_to(dx_layer)
            folium.Marker(
                [end_lat, end_lon],
                icon=folium.DivIcon(
                    html=(
                        '<div style="font-size:11px;font-weight:600;white-space:nowrap;'
                        'color:#000;text-shadow:'
                        '-1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff;">'
                        f"{label}</div>"
                    )
                ),
            ).add_to(dx_layer)
        dx_layer.add_to(fmap)

    colormap = LinearColormap(
        colors=[mcolors.to_hex(cmap(0)), mcolors.to_hex(cmap(0.5)), mcolors.to_hex(cmap(1.0))],
        vmin=0,
        vmax=2 * threshold_deg,
        caption=f"Required takeoff angle (deg) -- {threshold_deg:.1f}° antenna threshold = yellow",
    )
    colormap.add_to(fmap)

    folium.LayerControl().add_to(fmap)
    return fmap
