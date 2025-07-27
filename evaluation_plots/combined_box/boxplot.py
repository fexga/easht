import json
import matplotlib.pyplot as plt
import numpy as np

# Load first dataset
with open("energy_power_data_ray.json") as f:
    data_ray = json.load(f)
result_ray = data_ray["data"]["result"][0]["values"]
watts_ray = [float(v[1]) for v in result_ray if float(v[1]) > 0]

# Load second dataset
with open("energy_power_data_optuna.json") as f:
    data_optuna = json.load(f)
result_optuna = data_optuna["data"]["result"][0]["values"]
watts_optuna = [float(v[1]) for v in result_optuna if float(v[1]) > 0]

# Combine for boxplot
data = [watts_ray, watts_optuna]
labels = ["RayTune", "Optuna"]

plt.figure(figsize=(6, 4))
box = plt.boxplot(
    data,
    labels=labels,
    showfliers=False,
    medianprops=dict(color='r', linewidth=2),
    widths=0.55
)

# Add median labels
for i, w in enumerate(data):
    median = np.median(w)
    plt.text(i + 0.76, median - 5, f"Median: {median:.2f} W", color='r', va='center', ha='left', fontsize=10)

plt.ylabel("Power (Watts)")
plt.tight_layout()
plt.savefig("energy_boxplot_ray_vs_optuna.png")
plt.show()