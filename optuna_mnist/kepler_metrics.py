import time
import functools
import pandas as pd
import requests
import json

class KeplerMetrics:
    def __init__(self, prometheus_url="http://localhost:9090/api/v1/query"):
        self.prometheus_url = prometheus_url
        self.metrics = {}
        self.timestamps = {}
        
    def measure_power(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            step_name = method.__name__
            print(f"Starting measurements for {step_name}...")
            
            # Record only start timestamp
            start_time = time.time()
            print(f"Start time: {start_time}")
            
            # Execute the original method
            result = method(self, *args, **kwargs)
            
            # Record only end timestamp
            end_time = time.time()
            
            # Store timestamps for later processing
            self.timestamps[step_name] = {
                'start_time': start_time,
                'end_time': end_time,
                'duration_seconds': end_time - start_time
            }
            
            print(f"Recorded timestamps for {step_name} (duration: {end_time - start_time:.2f}s)")
            return result
            
        return wrapper
    
    def calculate_energy_metrics(self):
        """Calculate energy metrics for all recorded steps using timestamps"""
        for step_name, time_data in self.timestamps.items():
            start_time = time_data['start_time']
            end_time = time_data['end_time']
            duration = time_data['duration_seconds']
            
            print(f"Processing {step_name}...")
            # Query Prometheus for energy at these timestamps
            start_total = self._get_energy_at_timestamp(start_time, 'total')
            end_total = self._get_energy_at_timestamp(end_time, 'total')
            print(f"Total energy: start={start_total}, end={end_total}")

            start_cpu = self._get_energy_at_timestamp(start_time, 'cpu')
            end_cpu = self._get_energy_at_timestamp(end_time, 'cpu')
            print(f"CPU energy: start={start_cpu}, end={end_cpu}")

            start_dram = self._get_energy_at_timestamp(start_time, 'dram')
            end_dram = self._get_energy_at_timestamp(end_time, 'dram')
            print(f"DRAM energy: start={start_dram}, end={end_dram}")
            
            # Initialize or update metrics dict for this step
            if step_name not in self.metrics:
                self.metrics[step_name] = {'duration_seconds': duration}
            
            # Calculate total energy
            if end_total is not None and start_total is not None:
                energy_consumed = end_total - start_total
                avg_power = energy_consumed / duration if duration > 0 else 0
                self.metrics[step_name].update({
                    'total_energy_joules': energy_consumed,
                    'avg_power_watts': avg_power
                })
                print(f"Total energy for {step_name}: {energy_consumed:.2f} joules")
            
            # Calculate CPU energy
            if end_cpu is not None and start_cpu is not None:
                cpu_energy = end_cpu - start_cpu
                avg_cpu_power = cpu_energy / duration if duration > 0 else 0
                self.metrics[step_name].update({
                    'cpu_energy_joules': cpu_energy,
                    'avg_cpu_power_watts': avg_cpu_power
                })
                print(f"CPU energy for {step_name}: {cpu_energy:.2f} joules")
            
            # Calculate DRAM energy
            if end_dram is not None and start_dram is not None:
                dram_energy = end_dram - start_dram
                avg_dram_power = dram_energy / duration if duration > 0 else 0
                self.metrics[step_name].update({
                    'dram_energy_joules': dram_energy,
                    'avg_dram_power_watts': avg_dram_power
                })
                print(f"DRAM energy for {step_name}: {dram_energy:.2f} joules")

    def _get_energy_at_timestamp(self, timestamp, energy_type='total'):
        """Query Prometheus for energy values at a specific timestamp"""
        try:
            # Determine query based on energy type
            if energy_type == 'total':
                query = 'sum(kepler_container_joules_total{container_namespace="default"})'
            elif energy_type == 'cpu':
                query = 'sum(kepler_container_core_joules_total{container_namespace="default"})'
            elif energy_type == 'dram':
                query = 'sum(kepler_container_dram_joules_total{container_namespace="default"})'
            else:
                raise ValueError(f"Unknown energy type: {energy_type}")
            
            # Query Prometheus with timestamp
            response = requests.get(
                self.prometheus_url, 
                params={'query': query, 'time': timestamp}
            )
            result = response.json()
            
            # Extract value
            if 'data' in result and 'result' in result['data'] and result['data']['result']:
                value = float(result['data']['result'][0]['value'][1])
                return value
            return None
            
        except Exception as e:
            print(f"Error querying Prometheus for {energy_type} energy at timestamp {timestamp}: {e}")
            return None

    def _get_current_energy(self):
        
        try:
            query = 'sum(kepler_container_joules_total{container_namespace="default"})'
            response = requests.get(self.prometheus_url, params={'query': query})
            result = response.json()
            print(result)

            result = result['data']['result']
            print(result)

            first_result = result[0]
            print(first_result)

            value_list = first_result['value']
            print(value_list)

            # Access the second element of the 'value' list
            second_value = value_list[1]
            print(second_value)

            return float(second_value)

        except Exception as e:
            print(f"Error querying Prometheus for CPU energy: {e}")
            return None

    
    def _get_cpu_energy(self):
        """Query Kepler for the current CPU energy consumption"""
        try:
            query = 'sum(kepler_container_core_joules_total{container_namespace="default"})'

            response = requests.get(self.prometheus_url, params={'query': query})
            result = response.json()
            print(result)

            result = result['data']['result']

            first_result = result[0]

            value_list = first_result['value']

            # Access the second element of the 'value' list
            second_value = value_list[1]

            return float(second_value)



        except Exception as e:
            print(f"Error querying Prometheus for CPU energy: {e}")
            return None
    
    def _get_dram_energy(self):
        """Query Kepler for the current DRAM energy consumption"""
        try:
            query = 'sum(kepler_container_dram_joules_total{container_namespace="default"})'

            response = requests.get(self.prometheus_url, params={'query': query})
            result = response.json()
            print(result)

            result = result['data']['result']

            first_result = result[0]

            value_list = first_result['value']

            # Access the second element of the 'value' list
            second_value = value_list[1]

            return float(second_value)


        except Exception as e:
            print(f"Error querying Prometheus for DRAM energy: {e}")
            return None
            
    def save_metrics(self, filename="kepler_power_metrics.csv"):
        """Save the collected metrics to a CSV file"""
        if self.metrics:
            # Create a deep copy to avoid modifying the original metrics
            metrics_with_kwh = {}

            total_process_joules = 0
            total_cpu_joules = 0
            total_dram_joules = 0

            total_process_kwh = 0
            total_cpu_kwh = 0
            total_dram_kwh = 0

            total_process_cf = 0

            total_process_time = 0

            url = "https://api.electricitymap.org/v3/carbon-intensity/latest"
            headers = {
                "auth-token": "dIwUCF85zoiOQKDWtQKTKjarwIg2Mpph"
            }
            params = {
                "zone": "AE"
            }

            response = requests.get(url, headers=headers, params=params)

            data = response.json()
            carbon_intensity = data.get("carbonIntensity")

            for step_name, step_metrics in self.metrics.items():
                metrics_with_kwh[step_name] = step_metrics.copy()

                # Add kWh conversions for energy metrics
                if 'total_energy_joules' in step_metrics:
                    total_kwh = self.joules_to_kwh(
                        step_metrics['total_energy_joules']
                    )

                    metrics_with_kwh[step_name]['total_energy_kwh'] = total_kwh

                    metrics_with_kwh[step_name]['total_energy_cf'] =  total_kwh * carbon_intensity

                    total_process_joules = total_process_joules + step_metrics['total_energy_joules']
                    total_process_kwh = total_process_kwh + total_kwh
                    total_process_cf = total_process_cf + metrics_with_kwh[step_name]['total_energy_cf']

                if 'cpu_energy_joules' in step_metrics:
                    cpu_kwh = self.joules_to_kwh(
                        step_metrics['cpu_energy_joules']
                    )

                    metrics_with_kwh[step_name]['cpu_energy_kwh'] = cpu_kwh

                    metrics_with_kwh[step_name]['cpu_energy_cf'] =  cpu_kwh * carbon_intensity

                    total_cpu_joules = total_cpu_joules + step_metrics['cpu_energy_joules']
                    total_cpu_kwh = total_cpu_kwh + cpu_kwh

                if 'dram_energy_joules' in step_metrics:
                    dram_kwh = self.joules_to_kwh(
                        step_metrics['dram_energy_joules']
                    ) 

                    metrics_with_kwh[step_name]['dram_energy_kwh'] = dram_kwh

                    metrics_with_kwh[step_name]['dram_energy_cf'] = dram_kwh * carbon_intensity

                    total_dram_joules = total_dram_joules + step_metrics['dram_energy_joules']
                    total_dram_kwh = total_dram_kwh + dram_kwh
                
                total_process_time = total_process_time + step_metrics['duration_seconds']
            
            #metrics_with_kwh["total"]['total_energy_joules'] = total_process_joules
            #metrics_with_kwh["total"]["total_energy_kwh"] = total_process_kwh

            #metrics_with_kwh["total"]['cpu_energy_joules'] = total_cpu_joules
            #metrics_with_kwh["total"]["cpu_energy_kwh"] = total_cpu_kwh

            #metrics_with_kwh["total"]['dram_energy_joules'] = total_dram_joules
            #metrics_with_kwh["total"]["dram_energy_kwh"] = total_dram_kwh

            #metrics_with_kwh["total"]['total_energy_cf'] = total_process_cf

            #metrics_with_kwh["total"]['duration_seconds'] = total_process_time


            df = pd.DataFrame.from_dict(metrics_with_kwh, orient='index')
            # Add the step name as a column
            df['step'] = df.index
            df.to_csv(filename, index=False)
            print(f"Metrics (including CPU and DRAM) saved to {filename}")
        else:
            print("No metrics to save")
    
    def joules_to_kwh(self, joules):
        """Convert energy from joules to kilowatt-hours"""
        # 1 kWh = 3,600,000 joules
        return joules / 3_600_000