import json
import matplotlib.pyplot as plt
import numpy as np
import requests

url = "http://localhost:9090/api/v1/query_range"
params = {
    "query": 'sum((rate(kepler_container_joules_total{container_namespace="default"}[5m])))',
    "start": "2025-07-28T10:30:00Z",
    "end": "2025-07-28T12:15:00Z",
    "step": "3s"
}
response = requests.get(url, params=params)
data = response.json()

with open("energy_boxplot_raw.json", "w") as f:
    json.dump(data, f, indent=2)

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
plt.xticks([1], ["Optuna"])

# Add median label next to the median line inside the box
plt.text(
    1.1, median, f"Median: {median:.2f} W",
    color='r', va='center', ha='left', fontsize=10
)

plt.tight_layout()
plt.savefig("energy_boxplot_watts_filtered.png")
plt.show()