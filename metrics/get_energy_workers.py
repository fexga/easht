import requests
import matplotlib.pyplot as plt
from datetime import datetime
import json

url = "http://localhost:9090/api/v1/query_range"
params = {
    "query": '(increase(kepler_container_joules_total{container_namespace="default"}[5m]))',
    "start": "2025-07-13T16:00:00Z",
    "end": "2025-07-13T18:00:00Z",
    "step": "5s"
}
response = requests.get(url, params=params)
data = response.json()

# Save the Prometheus response JSON
with open("energy_power_data_optuna_workers.json", "w") as f:
    json.dump(data, f, indent=2)
print("Prometheus data saved as energy_power_data.json")

result_list = data['data']['result']
if not result_list:
    print("No data returned for the given query and time range.")
    exit(1)

fig, ax1 = plt.subplots()

# Find the global start and end time (in seconds)
all_times = [float(t[0]) for series in result_list if series["values"] for t in series["values"]]
global_start_time = min(all_times)
global_end_time = max(all_times)
x_min = 0
x_max = (global_end_time - global_start_time) / 60  # in minutes

seen_labels = set()
for series in result_list:
    pod_name = series['metric'].get('pod_name', '')  # Use 'pod_name' specifically
    label = pod_name if pod_name else str(series['metric'])
    values = series["values"]
    # Duration in minutes from global start time
    times = [((float(t[0]) - global_start_time) / 60) for t in values]
    watts = [float(t[1]) for t in values]
    if label in seen_labels:
        ax1.plot(times, watts)
    else:
        ax1.plot(times, watts, label=label)
        seen_labels.add(label)

ax1.set_xlabel("Duration (minutes)")
ax1.set_ylabel("Power (Watts)")
ax1.tick_params(axis='y')
ax1.set_ylim(bottom=0)
ax1.set_xlim(left=x_min, right=x_max)  # Set x-axis to full duration
plt.title("Power (Watts) Over Duration (per pod_name)")
handles, labels = ax1.get_legend_handles_labels()
if labels:
    ax1.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), borderaxespad=0, frameon=False)  # Legend outside plot, vertically centered

fig.tight_layout()
plt.savefig("energy_power_plot_optuna_workers.png", bbox_inches='tight')
print("Plot saved as energy_power_plot_optuna.png")