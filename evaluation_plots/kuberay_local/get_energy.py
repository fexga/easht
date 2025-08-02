import requests
import matplotlib.pyplot as plt
from datetime import datetime
import matplotlib.dates as mdates
import json

url = "http://localhost:9090/api/v1/query_range"
params = {
    "query": 'sum((rate(kepler_container_joules_total{container_namespace="default"}[5m])))',
    "start": "2025-07-28T09:10:00Z",
    "end": "2025-07-28T10:10:00Z",
    "step": "3s"
}
response = requests.get(url, params=params)
data = response.json()

# Save the Prometheus response JSON
with open("energy_power_data_ray.json", "w") as f:
    json.dump(data, f, indent=2)
print("Prometheus data saved as energy_power_data_ray.json")

result_list = data['data']['result']
if not result_list:
    print("No data returned for the given query and time range.")
    exit(1)

result = result_list[0]['values']
start_time = float(result[0][0])
times = [((float(t) - start_time) / 60) for t, v in result]  # duration in minutes
watts = [float(v) for t, v in result]

fig, ax1 = plt.subplots()

ax1.plot(times, watts, 'b-')
ax1.set_xlabel("Duration (minutes)")
ax1.set_ylabel("Power (Watts)")
ax1.tick_params(axis='y')
ax1.set_ylim(bottom=0)

# Add average power as a dotted line
avg_power = sum(watts) / len(watts)
avg_line = ax1.axhline(avg_power, color='blue', linestyle='dotted', linewidth=2, label=f'Avg Power ({avg_power:.2f} W)')

# Add legend above the plot, in blue
legend = ax1.legend(handles=[avg_line], loc='upper center', bbox_to_anchor=(0.5, 1.15), ncol=1, frameon=False)
for text in legend.get_texts():
    text.set_color('blue')

fig.tight_layout()
plt.savefig("energy_power_plot_ray.png")
print("Plot saved as energy_power_plot_ray.png")