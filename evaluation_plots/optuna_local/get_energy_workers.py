import requests
import matplotlib.pyplot as plt
import json
from collections import defaultdict

url = "http://localhost:9090/api/v1/query_range"
params = {
    "query": 'sum(rate(kepler_container_joules_total{container_namespace="default"}[5m])) by (pod_name)',
    "start": "2025-07-28T10:30:00Z",
    "end": "2025-07-28T12:15:00Z",
    "step": "3s"
}
response = requests.get(url, params=params)
data = response.json()

# Save the Prometheus response JSON
with open("energy_power_data_optuna_workers.json", "w") as f:
    json.dump(data, f, indent=2)
print("Prometheus data saved as energy_power_data_optuna_workers.json")

result_list = data['data']['result']
if not result_list:
    print("No data returned for the given query and time range.")
    exit(1)

def base_pod_name(pod_name):
    return '-'.join(pod_name.split('-')[:-1])

pod_time_watts = defaultdict(lambda: defaultdict(float))
all_times = set()
for series in result_list:
    pod_name = series['metric'].get('pod_name', '')
    # Only merge for kuberay-operator pods
    if pod_name.startswith("kuberay-operator-"):
        merged_name = base_pod_name(pod_name)
    else:
        merged_name = pod_name
    for t in series["values"]:
        ts = float(t[0])
        watts = float(t[1])
        pod_time_watts[merged_name][ts] += watts
        all_times.add(ts)

# Sort all timestamps
all_times_sorted = sorted(all_times)
global_start_time = min(all_times_sorted)
global_end_time = max(all_times_sorted)
x_min = 0
x_max = (global_end_time - global_start_time) / 60  # in minutes

fig, ax1 = plt.subplots(figsize=(12, 6))

for pod_name, time_watts in pod_time_watts.items():
    times = [((ts - global_start_time) / 60) for ts in all_times_sorted]
    watts = [time_watts.get(ts, 0) for ts in all_times_sorted]
    ax1.plot(times, watts, label=pod_name)

ax1.set_xlabel("Duration (minutes)")
ax1.set_ylabel("Power (Watts)")
ax1.tick_params(axis='y')
ax1.set_ylim(bottom=0)
ax1.set_xlim(left=x_min, right=x_max)
plt.title("Power (Watts) Over Duration (per pod_name)")
handles, labels = ax1.get_legend_handles_labels()
if labels:
    ax1.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), borderaxespad=0, frameon=False)

fig.tight_layout()
plt.savefig("energy_power_plot_optuna_workers.png", bbox_inches='tight')
print("Plot saved as energy_power_plot_optuna_workers.png")