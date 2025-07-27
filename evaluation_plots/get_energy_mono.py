import requests
import matplotlib.pyplot as plt
import json

url = "http://localhost:9090/api/v1/query_range"
params = {
    "query": 'sum(kepler_container_joules_total{container_namespace="default"})',
    "start": "2025-07-13T16:00:00Z",
    "end": "2025-07-13T18:00:00Z",
    "step": "3s"
}
response = requests.get(url, params=params)
data = response.json()

# Save the Prometheus response JSON
with open("energy_total_data_optuna.json", "w") as f:
    json.dump(data, f, indent=2)
print("Prometheus data saved as energy_total_data_optuna.json")

result_list = data['data']['result']
if not result_list:
    print("No data returned for the given query and time range.")
    exit(1)

result = result_list[0]['values']
start_time = float(result[0][0])
times = [((float(t) - start_time) / 60) for t, v in result]  # duration in minutes

# Convert joules to kWh: 1 kWh = 3,600,000 joules
kwh = [float(v) / 3_600_000 for t, v in result]

fig, ax1 = plt.subplots()

cut_idx = None
for i in range(1, len(kwh)):
    if kwh[i] < kwh[i-1]:
        cut_idx = i
        break

if cut_idx is not None:
    times_plot = times[:cut_idx]
    kwh_plot = kwh[:cut_idx]
else:
    times_plot = times
    kwh_plot = kwh

co2_per_kwh = 316  # grams per kWh
co2_grams = [k * co2_per_kwh for k in kwh_plot]

fig, ax1 = plt.subplots()
ax1.plot(times_plot, kwh_plot, 'g-', label='Total Energy (kWh)')
ax1.set_xlabel("Duration (minutes)")
ax1.set_ylabel("Total Energy (kWh)", color='g')
ax1.tick_params(axis='y', labelcolor='g')
ax1.set_ylim(bottom=0)

# Add CO2 emissions on a secondary y-axis
ax2 = ax1.twinx()
ax2.plot(times_plot, co2_grams, 'r--', label='CO₂ Emissions (g)')
ax2.set_ylabel("CO₂ Emissions (g)", color='r')
ax2.tick_params(axis='y', labelcolor='r')
ax2.set_ylim(bottom=0)

plt.title("Total Energy Consumption (kWh) and CO₂ Emissions Over Duration")
fig.tight_layout()
plt.savefig("energy_total_plot_optuna.png")
print("Plot saved as energy_total_plot_optuna.png")
