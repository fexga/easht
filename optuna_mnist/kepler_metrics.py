import time
import functools
import pandas as pd
import requests

class KeplerMetrics:
    def __init__(self, prometheus_url="http://localhost:9090/api/v1/query"):
        self.prometheus_url = prometheus_url
        self.metrics = {}
        
    def measure_power(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            step_name = method.__name__
            print(f"Starting measurements for {step_name}...")
            
            # Record start time and metrics
            start_time = time.time()
            start_total_energy = self._get_current_energy()
            start_cpu_energy = self._get_cpu_energy()
            start_dram_energy = self._get_dram_energy()
            
            # Execute the original method
            result = method(self, *args, **kwargs)
            
            # Record end time and metrics
            end_time = time.time()
            end_total_energy = self._get_current_energy()
            end_cpu_energy = self._get_cpu_energy()
            end_dram_energy = self._get_dram_energy()
            
            # Calculate metrics
            duration = end_time - start_time
            
            # Store the metrics
            self.metrics[step_name] = {
                'duration_seconds': duration
            }
            
            # Calculate and store total energy
            if end_total_energy is not None and start_total_energy is not None:
                energy_consumed = end_total_energy - start_total_energy
                avg_power = energy_consumed / duration if duration > 0 else 0
                self.metrics[step_name].update({
                    'total_energy_joules': energy_consumed,
                    'avg_power_watts': avg_power
                })
                print(f"Total energy for {step_name}: {energy_consumed:.2f} joules, "
                      f"Average power: {avg_power:.2f} watts")
            else:
                print(f"Could not measure total energy for {step_name}")
            
            # Calculate and store CPU energy
            if end_cpu_energy is not None and start_cpu_energy is not None:
                cpu_energy = end_cpu_energy - start_cpu_energy
                avg_cpu_power = cpu_energy / duration if duration > 0 else 0
                self.metrics[step_name].update({
                    'cpu_energy_joules': cpu_energy,
                    'avg_cpu_power_watts': avg_cpu_power
                })
                print(f"CPU energy for {step_name}: {cpu_energy:.2f} joules")
            else:
                print(f"Could not measure CPU energy for {step_name}")
            
            # Calculate and store DRAM energy
            if end_dram_energy is not None and start_dram_energy is not None:
                dram_energy = end_dram_energy - start_dram_energy
                avg_dram_power = dram_energy / duration if duration > 0 else 0
                self.metrics[step_name].update({
                    'dram_energy_joules': dram_energy,
                    'avg_dram_power_watts': avg_dram_power
                })
                print(f"DRAM energy for {step_name}: {dram_energy:.2f} joules")
            else:
                print(f"Could not measure DRAM energy for {step_name}")
                
            return result
            
        return wrapper
    
    def _get_current_energy(self):
        """Query Kepler for the current total energy consumption"""
        try:
            query = 'sum(kepler_container_joules_total{container_namespace="default"})'
            response = requests.get(self.prometheus_url, params={'query': query})
            result = response.json()['data']['result']
            
            if result and len(result) > 0:
                return float(result[0]['value'][1])
            else:
                print("No energy data available from Kepler")
                return None
        except Exception as e:
            print(f"Error querying Prometheus: {e}")
            return None
    
    def _get_cpu_energy(self):
        """Query Kepler for the current CPU energy consumption"""
        try:
            query = 'sum(kepler_container_package_joules_total{container_namespace="default"})'
            response = requests.get(self.prometheus_url, params={'query': query})
            result = response.json()['data']['result']
            
            if result and len(result) > 0:
                return float(result[0]['value'][1])
            else:
                print("No CPU energy data available from Kepler")
                return None
        except Exception as e:
            print(f"Error querying Prometheus for CPU energy: {e}")
            return None
    
    def _get_dram_energy(self):
        """Query Kepler for the current DRAM energy consumption"""
        try:
            query = 'sum(kepler_container_dram_joules_total{container_namespace="default"})'
            response = requests.get(self.prometheus_url, params={'query': query})
            result = response.json()['data']['result']
            
            if result and len(result) > 0:
                return float(result[0]['value'][1])
            else:
                print("No DRAM energy data available from Kepler")
                return None
        except Exception as e:
            print(f"Error querying Prometheus for DRAM energy: {e}")
            return None
            
    def save_metrics(self, filename="kepler_power_metrics.csv"):
        """Save the collected metrics to a CSV file"""
        if self.metrics:
            df = pd.DataFrame.from_dict(self.metrics, orient='index')
            # Add the step name as a column
            df['step'] = df.index
            df.to_csv(filename, index=False)
            print(f"Metrics (including CPU and DRAM) saved to {filename}")
        else:
            print("No metrics to save")