import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

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

plt.savefig("output/takeoff_angle_polar.png", dpi=200, bbox_inches="tight")
plt.show()