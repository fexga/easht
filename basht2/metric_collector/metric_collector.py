import time
import functools
import requests
import json
from dotenv import dotenv_values
import os
from kubernetes import client, config
import optuna


class MetricCollector:
    def __init__(self, prometheus_url="http://localhost:9090/api/v1/query"):
        self.prometheus_url = prometheus_url
        self.metrics = {"steps": {}}
        self.timestamps = {}
        self.b_f1_Score = 0
        
        env_file_path = os.path.join(os.getcwd(), ".env")
        self.env_vars = dotenv_values(env_file_path)
        print(f"Loaded .env file from: {env_file_path}")
        print(f"Environment variables: {self.env_vars}")
        
    def measure_power(aggregation_method='sum'):
        def decorator(method):
            @functools.wraps(method)
            def wrapper(self, *args, **kwargs):
                step_name = method.__name__
                print(f"Starting measurements for {step_name} with aggregation method: {aggregation_method}...")

                # Record start timestamp
                start_time = time.time()
                print(f"Start time: {start_time}")

                # Execute the original method
                result = method(self, *args, **kwargs)

                # Record end timestamp
                end_time = time.time()

                # Store timestamps for later processing
                self.timestamps[step_name] = {
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration_seconds': end_time - start_time,
                    'aggregation_method': aggregation_method
                }

                print(f"Recorded timestamps for {step_name} (duration: {end_time - start_time:.2f}s)")
                return result
            
            return wrapper
        return decorator
    
    def calculate_energy_metrics(self):
        """Calculate energy metrics for all recorded steps using timestamps."""
        for step_name, time_data in self.timestamps.items():
            start_time = time_data['start_time']
            end_time = time_data['end_time']
            duration = time_data['duration_seconds']
            aggregation_method = time_data['aggregation_method']

            print(f"Processing {step_name}...")
            if aggregation_method == 'sum':
                # Calculate total energy metrics
                self._calculate_total_energy(step_name, start_time, end_time, duration)

                # Calculate CPU energy metrics
                self._calculate_cpu_energy(step_name, start_time, end_time, duration)

                # Calculate DRAM energy metrics
                self._calculate_dram_energy(step_name, start_time, end_time, duration)

                self._calculate_gpu_energy(step_name, start_time, end_time, duration)

                self._calculate_network_metrics(step_name, start_time, end_time, duration)

             
            elif aggregation_method == 'rate':
                # Calculate total energy metrics using rate
                self._calculate_total_rate(step_name, start_time, end_time, duration)

                # Calculate CPU energy metrics using rate
                self._calculate_cpu_rate(step_name, start_time, end_time, duration)

                # Calculate DRAM energy metrics using rate
                self._calculate_dram_rate(step_name, start_time, end_time, duration)

                self._calculate_gpu_rate(step_name, start_time, end_time, duration)

                self._calculate_network_metrics_rate(step_name, start_time, end_time, duration)

            

        self._calculate_totals()

        self._calculate_epoch_metrics()

        self._add_env_to_meta()

        self._add_hardware_info_to_meta()


        
    def _calculate_epoch_metrics(self):
        """
        Calculate adjusted energy consumption based on the number of epochs.
        Formula: (number of epochs / 1000) * energy consumption of the 'run' step.
        """
        # Load the number of epochs from the .env file
        epochs = int(os.getenv("EPOCHS"))  # Default to 1 if not set

        # Ensure the 'run' step metrics exist
        if "total_energy_kwh" in self.metrics["steps"]["run"]:
            total_kwh = self.metrics["steps"]["run"]["total_energy_kwh"]
            total_energy_cf = self.metrics["steps"]["run"]["total_energy_cf"]

            # Calculate adjusted energy
            energy_per_1000epochs = (1000 / epochs) * total_kwh
            cf_per_1000epochs = (1000 / epochs) * total_energy_cf

            if "total" not in self.metrics:
                self.metrics["total"] = {}

            self.metrics["total"].update({
                "kwh_1000epochs": energy_per_1000epochs,
                "carbon_footprint_1000epochs_g": cf_per_1000epochs
            })

            print(f"kwh_1000epochs saved in 'meta': {energy_per_1000epochs:.2f} joules")
            print(f"carbon_footprint_1000epochs saved in 'meta': {cf_per_1000epochs:.4f} kgCO2e")
        else:
            print("Metrics for 'run' step or 'total_energy_kwh' not found.")

    def _add_env_to_meta(self):
        """
        Add all values from the .env file to the 'meta' field in the metrics.
        """

        # Ensure the 'meta' field exists in the metrics
        if "meta" not in self.metrics:
            self.metrics["meta"] = {}

        # List of environment variables to include in 'meta'
        required_env_vars = ["BATCHSIZE", "EPOCHS", "PERCENT_VALID_EXAMPLES", "CLASSES"]

        # Add the environment variables to the 'meta' field
        for var in required_env_vars:
            value = os.getenv(var)
            if value is not None:
                self.metrics["meta"][var] = value

        print(f"Added all environment variables to 'meta': {self.metrics['meta']}")

    def _set_f1_score(self):
        node_ip = self.get_node_ip()

        # Retrieve the best score from the Optuna database
        study = optuna.create_study(
            study_name="k8s_mlflow",
            storage=f"postgresql://optuna:superSecretPassword@{node_ip}:30032/optunaDatabase",
            load_if_exists=True
        )
         

        time.sleep(20)
        
        best_trial = study.best_trial
        best_score = best_trial.value  # Best validation accuracy or F1 score 


        self.b_f1_Score = best_score

    def _calculate_total_energy(self, step_name, start_time, end_time, duration):
        """Calculate total energy metrics."""
        start_total = self._get_energy_at_timestamp(start_time, 'total')
        end_total = self._get_energy_at_timestamp(end_time, 'total')
        print(f"Total energy: start={start_total}, end={end_total}")

        if "steps" not in self.metrics:
            self.metrics["steps"] = {}

        if step_name not in self.metrics["steps"]:
            self.metrics["steps"][step_name] = {'duration_seconds': duration}

        if end_total is not None and start_total is not None:
            energy_consumed = end_total - start_total
            avg_power = energy_consumed / duration if duration > 0 else 0
            total_kwh = self.joules_to_kwh(energy_consumed)
            carbon_intensity = self._get_carbon_intensity()
            total_cf = total_kwh * carbon_intensity
        elif end_total is not None and start_total is None:
            energy_consumed = end_total - 0
            avg_power = energy_consumed / duration if duration > 0 else 0
            total_kwh = self.joules_to_kwh(energy_consumed)
            carbon_intensity = self._get_carbon_intensity()
            total_cf = total_kwh * carbon_intensity
        else:
            energy_consumed = 0
            avg_power = 0
            total_kwh = 0
            total_cf = 0

        self.metrics["steps"][step_name].update({
            'avg_power_watts': avg_power,
            'total_energy_kwh': total_kwh,
            'total_energy_cf': total_cf
        })
        print(f"Total energy for {step_name}: {energy_consumed:.2f} joules, {total_kwh:.4f} kWh, {total_cf:.4f} gCO2e")

    def _calculate_cpu_energy(self, step_name, start_time, end_time, duration):
        """Calculate CPU energy metrics."""
        start_cpu = self._get_energy_at_timestamp(start_time, 'cpu')
        end_cpu = self._get_energy_at_timestamp(end_time, 'cpu')
        print(f"CPU energy: start={start_cpu}, end={end_cpu}")

        if "steps" not in self.metrics:
            self.metrics["steps"] = {}

        if step_name not in self.metrics["steps"]:
            self.metrics["steps"][step_name] = {'duration_seconds': duration}

        if end_cpu is not None and start_cpu is not None:
            cpu_energy = end_cpu - start_cpu
            avg_cpu_power = cpu_energy / duration if duration > 0 else 0
            cpu_kwh = self.joules_to_kwh(cpu_energy)
            carbon_intensity = self._get_carbon_intensity()
            cpu_cf = cpu_kwh * carbon_intensity
        elif end_cpu is not None and start_cpu is None:
            cpu_energy = end_cpu - 0
            avg_cpu_power = cpu_energy / duration if duration > 0 else 0
            cpu_kwh = self.joules_to_kwh(cpu_energy)
            carbon_intensity = self._get_carbon_intensity()
            cpu_cf = cpu_kwh * carbon_intensity
        else:
            cpu_energy = 0
            avg_cpu_power = 0
            cpu_kwh = 0
            cpu_cf = 0

        self.metrics["steps"][step_name].update({
            'avg_cpu_power_watts': avg_cpu_power,
            'cpu_energy_kwh': cpu_kwh,
            'cpu_energy_cf': cpu_cf
        })
        print(f"CPU energy for {step_name}: {cpu_energy:.2f} joules, {cpu_kwh:.4f} kWh, {cpu_cf:.4f} gCO2e")

    def _calculate_dram_energy(self, step_name, start_time, end_time, duration):
        """Calculate DRAM energy metrics."""
        start_dram = self._get_energy_at_timestamp(start_time, 'dram')
        end_dram = self._get_energy_at_timestamp(end_time, 'dram')
        print(f"DRAM energy: start={start_dram}, end={end_dram}")

        if "steps" not in self.metrics:
            self.metrics["steps"] = {}

        if step_name not in self.metrics["steps"]:
            self.metrics["steps"][step_name] = {'duration_seconds': duration}

        if end_dram is not None and start_dram is not None:
            dram_energy = end_dram - start_dram
            avg_dram_power = dram_energy / duration if duration > 0 else 0
            dram_kwh = self.joules_to_kwh(dram_energy)
            carbon_intensity = self._get_carbon_intensity()
            dram_cf = dram_kwh * carbon_intensity
        elif end_dram is not None and start_dram is None:
            dram_energy = end_dram - 0
            avg_dram_power = dram_energy / duration if duration > 0 else 0
            dram_kwh = self.joules_to_kwh(dram_energy)
            carbon_intensity = self._get_carbon_intensity()
            dram_cf = dram_kwh * carbon_intensity
        else:
            dram_energy = 0
            avg_dram_power = 0
            dram_kwh = 0
            dram_cf = 0

        self.metrics["steps"][step_name].update({
            'avg_dram_power_watts': avg_dram_power,
            'dram_energy_kwh': dram_kwh,
            'dram_energy_cf': dram_cf
        })
        print(f"DRAM energy for {step_name}: {dram_energy:.2f} joules, {dram_kwh:.4f} kWh, {dram_cf:.4f} gCO2e")

    def _calculate_gpu_energy(self, step_name, start_time, end_time, duration):
        """Calculate DRAM energy metrics."""
        start_gpu = self._get_energy_at_timestamp(start_time, 'gpu')
        end_gpu = self._get_energy_at_timestamp(end_time, 'gpu')
        print(f"DRAM energy: start={start_gpu}, end={end_gpu}")

        if end_gpu is not None and start_gpu is not None:
            gpu_energy = end_gpu - start_gpu
            avg_gpu_power = gpu_energy / duration if duration > 0 else 0
            gpu_kwh = self.joules_to_kwh(gpu_energy)
            carbon_intensity = self._get_carbon_intensity()
            gpu_cf = gpu_kwh * carbon_intensity
        elif end_gpu is not None and start_gpu is None:
            gpu_energy = end_gpu - 0
            avg_gpu_power = gpu_energy / duration if duration > 0 else 0
            gpu_kwh = self.joules_to_kwh(gpu_energy)
            carbon_intensity = self._get_carbon_intensity()
            gpu_cf = gpu_kwh * carbon_intensity
        else:
            gpu_energy = 0
            avg_gpu_power = 0
            gpu_kwh = 0
            gpu_cf = 0

        self.metrics["steps"][step_name].update({
            #'gpu_energy_joules': gpu_energy,
            'avg_gpu_power_watts': avg_gpu_power,
            'gpu_energy_kwh': gpu_kwh,
            'gpu_energy_cf': gpu_cf
        })
        print(f"DRAM energy for {step_name}: {gpu_energy:.2f} joules, {gpu_kwh:.4f} kWh, {gpu_cf:.4f} gCO2e")

    def _calculate_network_metrics(self, step_name, start_time, end_time, duration):
        """Calculate network metrics (transmit and receive packets)."""
        start_transmit = self._get_energy_at_timestamp(start_time, 'network_transmit')
        end_transmit = self._get_energy_at_timestamp(end_time, 'network_transmit')
        start_receive = self._get_energy_at_timestamp(start_time, 'network_receive')
        end_receive = self._get_energy_at_timestamp(end_time, 'network_receive')

        print(f"Network transmit: start={start_transmit}, end={end_transmit}")
        print(f"Network receive: start={start_receive}, end={end_receive}")

        if "steps" not in self.metrics:
            self.metrics["steps"] = {}

        if step_name not in self.metrics["steps"]:
            self.metrics["steps"][step_name] = {'duration_seconds': duration}

        if start_transmit is not None and end_transmit is not None:
            transmit_packets = end_transmit - start_transmit
            self.metrics["steps"][step_name].update({
                'network_transmit_bytes': transmit_packets
            })
            print(f"Network transmit bytes for {step_name}: {transmit_packets}")
        elif start_transmit is None and end_transmit is not None:
            transmit_packets = end_transmit - 0
            self.metrics["steps"][step_name].update({
                'network_transmit_bytes': transmit_packets
            })
            print(f"Network transmit bytes for {step_name}: {transmit_packets}")
        elif start_transmit is None and end_transmit is None:
            transmit_packets = 0
            self.metrics["steps"][step_name].update({
                'network_transmit_bytes': transmit_packets
            })
            print(f"Network transmit bytes for {step_name}: {transmit_packets}")

        if start_receive is not None and end_receive is not None:
            receive_packets = end_receive - start_receive
            self.metrics["steps"][step_name].update({
                'network_receive_bytes': receive_packets
            })
            print(f"Network receive bytes for {step_name}: {receive_packets}")
        elif start_receive is None and end_receive is not None:
            receive_packets = end_receive - 0
            self.metrics["steps"][step_name].update({
                'network_receive_bytes': receive_packets
            })
            print(f"Network receive bytes for {step_name}: {receive_packets}")
        elif start_receive is None and end_receive is None:
            receive_packets = 0
            self.metrics["steps"][step_name].update({
                'network_receive_bytes': receive_packets
            })
            print(f"Network receive bytes for {step_name}: {receive_packets}")
            
    def save_metrics(self, filename="kepler_power_metrics.json"):
        """Save the collected metrics to a JSON file with totals section"""
        if self.metrics:

            # Write to JSON file
            with open(filename, 'w') as f:
                json.dump(self.metrics, f, indent=4)

            print(f"Metrics (including CPU, DRAM, and totals) saved to {filename}")
        else:
            print("No metrics to save")

    def _calculate_totals(self):
        """Calculate total values for energy, power, and carbon footprint."""

        total_process_time = 0

        total_process_kwh = 0
        total_cpu_kwh = 0
        total_dram_kwh = 0

        total_process_cf = 0
        total_cpu_cf = 0
        total_dram_cf = 0
    
        for step_name, step_metrics in self.metrics.get("steps", {}).items():
            # Aggregate total energy metrics
            print(f"Calculating totals for {step_name}...")
            total_process_kwh += step_metrics['total_energy_kwh']
            total_process_cf += step_metrics['total_energy_cf']

            # Aggregate CPU energy metrics
            total_cpu_kwh += step_metrics['cpu_energy_kwh']
            total_cpu_cf += step_metrics['cpu_energy_cf']

            # Aggregate DRAM energy metrics
            total_dram_kwh += step_metrics['dram_energy_kwh']
            total_dram_cf += step_metrics['dram_energy_cf']

            # Aggregate GPU energy metrics 
            total_dram_kwh += step_metrics['gpu_energy_kwh']
            total_dram_cf += step_metrics['gpu_energy_cf']

            # Aggregate network metrics
            total_process_kwh += step_metrics['network_transmit_bytes']
            total_process_cf += step_metrics['network_transmit_bytes'] * self._get_carbon_intensity()

            total_process_kwh += step_metrics['network_receive_bytes']
            total_process_cf += step_metrics['network_receive_bytes'] * self._get_carbon_intensity()



        # Aggregate total process time
            total_process_time += step_metrics['duration_seconds']

        f1_score = self.b_f1_Score

        # Update the total metrics in self.metrics
        self.metrics['total'] = {
            'duration_seconds': total_process_time,
            'total_energy_kwh': total_process_kwh,
            'total_energy_cf': total_process_cf,
            'cpu_energy_kwh': total_cpu_kwh,
            'cpu_energy_cf': total_cpu_cf,
            'dram_energy_kwh': total_dram_kwh,
            'dram_energy_cf': total_dram_cf,
            'f1_score': f1_score
        }

        print(f"Total metrics calculated: {self.metrics['total']}")

    def _calculate_total_rate(self, step_name, start_time, end_time, duration):
        """Calculate total energy metrics using the rate function over a time range."""
        total_rate = self._get_energy_rate_in_range('total', start_time, end_time, duration)
        print(f"Total energy rate for {step_name}: {total_rate}")

        if "steps" not in self.metrics:
            self.metrics["steps"] = {}

        if step_name not in self.metrics["steps"]:
            self.metrics["steps"][step_name] = {'duration_seconds': duration}

        if total_rate is not None:
            total_kwh = self.watts_to_kwh(total_rate, duration)
            carbon_intensity = self._get_carbon_intensity()
            total_cf = total_kwh * carbon_intensity
        else:
            total_rate = 0
            total_kwh = 0
            total_cf = 0 

        self.metrics["steps"][step_name].update({
            'total_energy_rate': total_rate,
            'total_energy_kwh': total_kwh,
            'total_energy_cf': total_cf
        })

    def _calculate_cpu_rate(self, step_name, start_time, end_time, duration):
        """Calculate CPU energy metrics using the rate function over a time range."""
        cpu_rate = self._get_energy_rate_in_range('cpu', start_time, end_time, duration)
        print(f"CPU energy rate for {step_name}: {cpu_rate}")

        if "steps" not in self.metrics:
            self.metrics["steps"] = {}

        if step_name not in self.metrics["steps"]:
            self.metrics["steps"][step_name] = {'duration_seconds': duration}

        if cpu_rate is not None:
            cpu_kwh = self.watts_to_kwh(cpu_rate, duration)
            carbon_intensity = self._get_carbon_intensity()
            cpu_cf = cpu_kwh * carbon_intensity
        else:
            cpu_rate = 0
            cpu_kwh = 0
            cpu_cf = 0

        self.metrics["steps"][step_name].update({
            'avg_cpu_power_watts': cpu_rate,
            'cpu_energy_kwh': cpu_kwh,
            'cpu_energy_cf': cpu_cf
        })

    def _calculate_dram_rate(self, step_name, start_time, end_time, duration):
        """Calculate DRAM energy metrics using the rate function over a time range."""
        dram_rate = self._get_energy_rate_in_range('dram', start_time, end_time, duration)
        print(f"DRAM energy rate for {step_name}: {dram_rate}")

        if "steps" not in self.metrics:
            self.metrics["steps"] = {}
    
        if step_name not in self.metrics["steps"]:
            self.metrics["steps"][step_name] = {'duration_seconds': duration}
    
        if dram_rate is not None:
            dram_kwh = self.watts_to_kwh(dram_rate, duration)
            carbon_intensity = self._get_carbon_intensity()
            dram_cf = dram_kwh * carbon_intensity
        else:
            dram_rate = 0
            dram_kwh = 0
            dram_cf = 0
    
        self.metrics["steps"][step_name].update({
            'avg_dram_power_watts': dram_rate,
            'dram_energy_kwh': dram_kwh,
            'dram_energy_cf': dram_cf
        })
    
    def _calculate_gpu_rate(self, step_name, start_time, end_time, duration):
        """Calculate DRAM energy metrics using the rate function over a time range."""
        gpu_rate = self._get_energy_rate_in_range('gpu', start_time, end_time, duration)
        print(f"DRAM energy rate for {step_name}: {gpu_rate}")

        if "steps" not in self.metrics:
            self.metrics["steps"] = {}
    
        if step_name not in self.metrics["steps"]:
            self.metrics["steps"][step_name] = {'duration_seconds': duration}
    
        if gpu_rate is not None:
            gpu_kwh = self.watts_to_kwh(gpu_rate, duration)
            carbon_intensity = self._get_carbon_intensity()
            gpu_cf = gpu_kwh * carbon_intensity
        else:
            gpu_rate = 0
            gpu_kwh = 0
            gpu_cf = 0
    
        self.metrics["steps"][step_name].update({
            'avg_gpu_power_watts': gpu_rate,
            'gpu_energy_kwh': gpu_kwh,
            'gpu_energy_cf': gpu_cf
        })

    #non-functional
    def _calculate_network_metrics_rate(self, step_name, start_time, end_time, duration):
        """Calculate network metrics (transmit and receive packets)."""
        transmit = self._get_energy_rate_in_range('network_transmit', start_time, end_time, duration)
        receive = self._get_energy_rate_in_range('network_receive', start_time, end_time, duration)
    

        if "steps" not in self.metrics:
            self.metrics["steps"] = {}

        if step_name not in self.metrics["steps"]:
            self.metrics["steps"][step_name] = {'duration_seconds': duration}

        if receive is not None:
            receive_packets = receive * duration
            self.metrics["steps"][step_name].update({
                'network_receive_bytes': receive_packets
            })
            print(f"Network receive bytes for {step_name}: {receive_packets}")
        else:
            receive_packets = 0
            self.metrics["steps"][step_name].update({
                'network_receive_bytes': receive_packets
            })
            print(f"Network receive bytes for {step_name}: {receive_packets}")
        
        if transmit is not None:
            transmit_packets = transmit * duration
            self.metrics["steps"][step_name].update({
                'network_transmit_bytes': transmit_packets
            })
            print(f"Network transmit bytes for {step_name}: {transmit_packets}")
        else:
            transmit_packets = 0
            self.metrics["steps"][step_name].update({
                'network_transmit_bytes': transmit_packets
            })
            print(f"Network transmit bytes for {step_name}: {transmit_packets}")


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
            elif energy_type == 'network_transmit':
                query = 'sum(container_network_transmit_bytes_total{container_namespace="default"})'
            elif energy_type == 'network_receive':
                query = 'sum(container_network_receive_bytes_total{container_namespace="default"})'
            elif energy_type == 'gpu':
                query = 'sum(kepler_container_gpu_joules_total{container_namespace="default"})'
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
        
    def _get_energy_rate_in_range(self, energy_type, start_time, end_time, duration):
        """Query Prometheus for energy rates within a specific time range."""
        try:
            # Determine query based on energy type
            if energy_type == 'total':
                query = f'rate(kepler_container_joules_total{{container_namespace="default"}}[{int(duration)}s])'
            elif energy_type == 'cpu':
                query = f'rate(kepler_container_core_joules_total{{container_namespace="default"}}[{int(duration)}s])'
            elif energy_type == 'dram':
                query = f'rate(kepler_container_dram_joules_total{{container_namespace="default"}}[{int(duration)}s])'
            elif energy_type == 'network_transmit':
                query = f'rate(container_network_transmit_bytes_total{{container_namespace="default"}}[{int(duration)}s])'
            elif energy_type == 'network_receive':
                query = f'rate(container_network_receive_bytes_total{{container_namespace="default"}}[{int(duration)}s])'
            elif energy_type == 'gpu':
                query = f'rate(kepler_container_gpu_joules_total{{container_namespace="default"}}[{int(duration)}s])'
            else:
                raise ValueError(f"Unknown energy type: {energy_type}")

            # Query Prometheus
            response = requests.get(
                self.prometheus_url,  # Use the base URL without appending /api/v1/query again
                params={"query": query, 'time': end_time}
            )

            # Print the raw response for debugging
            print(f"Prometheus response for {energy_type}: {response.text}")

            # Parse the JSON response
            response.raise_for_status()
            result = response.json()

            # Extract and aggregate the rate values
            if 'data' in result and 'result' in result['data'] and result['data']['result']:
                value = float(result['data']['result'][0]['value'][1])
                return value
            return None

        except Exception as e:
            print(f"Error querying Prometheus for {energy_type} rate in range: {e}")
            return None
        
    def _add_hardware_info_to_meta(self):
        """
        Add hardware information about the cluster nodes to the 'meta' field in the metrics.
        """
        # Load Kubernetes configuration
        config.load_kube_config()

        # Initialize the CoreV1Api
        core_v1 = client.CoreV1Api()

        # Ensure the 'meta' field exists
        if "meta" not in self.metrics:
            self.metrics["meta"] = {}

        # Retrieve node information
        nodes = core_v1.list_node()
        hardware_info = []

        for node in nodes.items:
            node_info = {
                "name": node.metadata.name,
                "architecture": node.status.node_info.architecture,
                "os_image": node.status.node_info.os_image,
                "kernel_version": node.status.node_info.kernel_version,
                "kubelet_version": node.status.node_info.kubelet_version,
                "cpu_capacity": node.status.capacity.get("cpu", "N/A"),
                "memory_capacity": node.status.capacity.get("memory", "N/A"),
                "gpu_capacity": node.status.capacity.get("nvidia.com/gpu", "0")  # GPU info if available
            }
            hardware_info.append(node_info)

        # Add hardware information to the 'meta' field
        self.metrics["meta"]["hardware_info"] = hardware_info
        print(f"Added hardware information to 'meta': {hardware_info}")

    def joules_to_kwh(self, joules):
        """Convert energy from joules to kilowatt-hours"""
        # 1 kWh = 3,600,000 joules
        return joules / 3_600_000
    
    def watts_to_kwh(self, watts, duration_seconds):
        """Convert power in watts to energy in kilowatt-hours over a given duration."""
        # Convert duration from seconds to hours
        duration_hours = duration_seconds / 3600
        # Convert watts to kilowatts and calculate kWh
        return (watts / 1000) * duration_hours
    
    def _get_carbon_intensity(self, zone="AE"):
        """Fetch the carbon intensity from the API."""
        url = "https://api.electricitymap.org/v3/carbon-intensity/latest"
        headers = {"auth-token": "dIwUCF85zoiOQKDWtQKTKjarwIg2Mpph"}
        params = {"zone": zone}

        response = requests.get(url, headers=headers, params=params)
        data = response.json()

        if "meta" not in self.metrics:
            self.metrics["meta"] = {}
        self.metrics["meta"]["carbon_intensity_zone"] = zone

        return data.get("carbonIntensity")
    
    def get_node_ip(self):
        # Load Kubernetes configuration
        config.load_kube_config()

        # Initialize the CoreV1Api
        core_v1 = client.CoreV1Api()

        # Get the list of nodes
        nodes = core_v1.list_node()

        # Try to find an external IP first
        for node in nodes.items:
            for address in node.status.addresses:
                if address.type == "ExternalIP":
                    return address.address

        # If no external IP is found, fall back to internal IP
        for node in nodes.items:
            for address in node.status.addresses:
                if address.type == "InternalIP":
                    return address.address

        # If no IP is found, raise an exception
        raise RuntimeError("No node with an ExternalIP or InternalIP found in the cluster.")
    