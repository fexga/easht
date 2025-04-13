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
        
    def measure_power(container_names=None):
        """Decorator to measure power consumption for specific containers"""
        def decorator(method):
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
                print(f"End time: {end_time}")

                # Store timestamps and container names for later processing
                self.timestamps[step_name] = {
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration_seconds': end_time - start_time,
                    'container_names': container_names  # Store container names
                }

                print(f"Recorded timestamps for {step_name} (duration: {end_time - start_time:.2f}s)")
                if container_names:
                    container_str = container_names if isinstance(container_names, str) else ", ".join(container_names)
                    print(f"Will measure containers: {container_str}")
                return result

            return wrapper
    
        # Handle case when decorator is used without parentheses
        if callable(container_names):
            method = container_names
            container_names = None
            return decorator(method)
        return decorator
    
    def calculate_energy_metrics(self):
        """Calculate energy metrics for all recorded steps using timestamps"""
        for step_name, time_data in self.timestamps.items():
            start_time = time_data['start_time']
            end_time = time_data['end_time']
            duration = time_data['duration_seconds']
            container_names = time_data.get('container_names')
            
            # Describe what we're measuring
            container_str = ""
            if container_names:
                container_str = f" for containers: {container_names}"
            print(f"Processing {step_name}{container_str}...")
            
            # Query Prometheus for energy at these timestamps
            start_total = self._get_energy_at_timestamp(start_time, 'total', container_names)
            end_total = self._get_energy_at_timestamp(end_time, 'total', container_names)
            print(f"Total energy: start={start_total}, end={end_total}")
            
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

    def _get_energy_at_timestamp(self, timestamp, energy_type='total', container_names=None):
        """Query Prometheus for energy values at a specific timestamp for specific containers"""
        try:
            # Determine base metric name
            if energy_type == 'total':
                base_metric = 'kepler_container_joules_total'
            elif energy_type == 'cpu':
                base_metric = 'kepler_container_core_joules_total'
            elif energy_type == 'dram':
                base_metric = 'kepler_container_dram_joules_total'
            else:
                raise ValueError(f"Unknown energy type: {energy_type}")

            # Build query based on container names
            if container_names:
                if isinstance(container_names, list):
                    # Multiple container names - create a filter with regex
                    container_pattern = "|".join(container_names)
                    query = f'sum({base_metric}{{container_namespace="default",container_name=~"{container_pattern}"}})' 
                else:
                    # Single container name as string
                    query = f'sum({base_metric}{{container_namespace="default",container_name="{container_names}"}})' 
            else:
                # Default - all containers in the namespace
                query = f'sum({base_metric}{{container_namespace="default"}})'

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