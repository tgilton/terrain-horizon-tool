import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

dx_paths = {
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

df = pd.read_csv("output/horizon_summary.csv")

bearings = np.radians(df["bearing_deg"].values)
angles = df["max_angle_deg"].values

bearings = np.r_[bearings, bearings[0]]
angles = np.r_[angles, angles[0]]

fig = plt.figure(figsize=(8, 8))
ax = fig.add_subplot(111, polar=True)

ax.plot(bearings, angles, marker="o")
ax.fill(bearings, angles, alpha=0.2)

ax.set_theta_zero_location("N")
ax.set_theta_direction(-1)
ax.set_title("Required Takeoff Angle vs Bearing")

rmax = max(angles)

label_radii = {
    "Pituffik/Thule": rmax * 1.22,
    "Iceland": rmax * 1.14,
    "Greenland": rmax * 1.26,
    "Europe": rmax * 1.10,
    "Japan": rmax * 1.08,
    "Alaska": rmax * 1.18,
    "Australia": rmax * 1.15,
    "Hawaii": rmax * 1.05,
    "South America": rmax * 1.12,
}

for label, bearing_deg in dx_paths.items():
    theta = np.radians(bearing_deg)
    ax.plot(
        [theta, theta],
        [0, label_radii[label]],
        linestyle="--",
        linewidth=1,
    )
    ax.text(
        theta,
        label_radii[label],
        label,
        ha="center",
        va="center",
    )

ax.set_ylim(0, rmax * 1.22)

plt.savefig("output/takeoff_angle_polar.png", dpi=200, bbox_inches="tight")
plt.show()