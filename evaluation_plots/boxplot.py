import json
import matplotlib.pyplot as plt
import numpy as np

with open("energy_power_data_optuna.json") as f:
    data = json.load(f)

result = data["data"]["result"][0]["values"]
watts = [float(v[1]) for v in result if float(v[1]) > 0]
watts_filtered = [w for w in watts if w > 10]  # Adjust threshold as needed

plt.figure(figsize=(6, 4))
box = plt.boxplot(
    watts,
    showfliers=False,
    medianprops=dict(color='r', linewidth=2)  # Red, thick median line inside the box
)
median = np.median(watts)
plt.ylabel("Power (Watts)")
plt.title("Box Plot of Power Values (Watts, filtered, no outliers)")

# Add median label next to the median line inside the box
plt.text(
    1.1, median, f"Median: {median:.2f} W",
    color='r', va='center', ha='left', fontsize=10
)

plt.tight_layout()
plt.savefig("energy_boxplot_watts_filtered.png")
plt.show()