import os
from kubernetes import client, config, utils, watch
import subprocess
import socket
from basht2.metric_collector.metric_collector import MetricCollector
import time
from dotenv import load_dotenv
from ray.job_submission import JobSubmissionClient

from basht2.benchmark_template.experiment_runner import BenchmarkRunner, Benchmark, HelperFunctions

helper = HelperFunctions()

class OptunaBenchmark(Benchmark, MetricCollector):

    def __init__(self):
        MetricCollector.__init__(self)  # Initialize the KeplerMetrics class
        self.ray_port_forward = None

    @MetricCollector.measure_power(aggregation_method='increase')
    def setup(self):
        config.load_kube_config()

        kuberay_dir = os.path.join(os.path.dirname(__file__), 'kuberay-manifests/default')
        os.makedirs(kuberay_dir, exist_ok=True)

        # Use KubeRay's standard deployment method for Kind
        print("Setting up KubeRay operator...")
        result = subprocess.run(
            ["kubectl", "create", "-k", "github.com/ray-project/kuberay/ray-operator/config/default"],
            check=False,
            capture_output=True,
            text=True
        )

        # Print both stdout and stderr for debugging
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")

        # Wait for Operator pod to be running
        print("Waiting for Operator pod to be ready...")
        helper.wait_for_pods_ready(label_selector="app.kubernetes.io/component=kuberay-operator", number_jobs=1,  target_phase="Running")
        print("Operator deployment complete!")

        print(f"Waiting 15 additional seconds for services to initialize...")
        time.sleep(15)
        print("Extra waiting period complete.")

        raycluster_path = os.path.join(os.path.dirname(__file__), 'raycluster.yaml')
        print(f"Applying Ray cluster configuration from {raycluster_path}...")
        result = subprocess.run(
            ["kubectl", "apply", "-f", raycluster_path],
            check=False,
            capture_output=True,
            text=True
        )

        print("Waiting for Ray Cluster to be ready...")
        helper.wait_for_pods_ready(label_selector="ray.io/node-type=head", number_jobs=1,  target_phase="Running")
        helper.wait_for_pods_ready(label_selector="ray.io/node-type=worker", number_jobs=2,  target_phase="Running")
        print("Ray Cluster deployment complete!")

        # Start port forwarding
        print("Setting up port forwarding...")
        self.ray_port_forward = subprocess.Popen(
            ["kubectl", "port-forward", "svc/raycluster-head-svc", "8265:8265"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Verify port forwarding works
        print("Verifying port forwarding...")
        for attempt in range(10):
            try:
                with socket.create_connection(("127.0.0.1", 8265), timeout=2):
                    print("✓ Port forwarding successful!")
                    break
            except Exception as e:
                print(f"Attempt {attempt+1}/10: Port not ready: {e}")
                time.sleep(3)
        else:
            print("WARNING: Could not verify port forwarding")


        print("Study setup complete!")

    @MetricCollector.measure_power(aggregation_method='increase')
    def trail(self):

        ray_address = os.environ.get("RAY_ADDRESS", "http://127.0.0.1:8265")
        client = JobSubmissionClient(ray_address)

        # Define the runtime environment
        runtime_env = {
            "working_dir": "ray_cluster",  # Directory containing the script and requirements.txt
            "pip": "ray_cluster/requirements.txt",
            "excludes": [                  # Exclude large files
                "**prometheus_snapshots/**",
                "**.git/**"
            ]
        }

        # Submit the job
        job_id = client.submit_job(
            entrypoint="python script.py",
            runtime_env=runtime_env
        )

        # Watch job status until completion - no timeout
        print("Monitoring Ray job status...")
        while True:
            status = client.get_job_status(job_id)
            print(f"Job status: {status} - {time.strftime('%Y-%m-%d %H:%M:%S')}")

            if status in ["SUCCEEDED", "FAILED", "STOPPED", "PENDING_STOP"]:
                if status == "SUCCEEDED":
                    print(f"Job {job_id} completed successfully!")
                else:
                    print(f"Job {job_id} ended with status: {status}")
                break
            
            # Wait before checking again
            time.sleep(10)  # Check every 30 seconds

    @MetricCollector.measure_power(aggregation_method='increase')
    def deprovision(self):
        self.get_optimized_score_raytune("raycluster-head")
        """Delete all resources in the namespace and wait until they are gone."""

        ## Clean up port forwarding
        if self.ray_port_forward:
            self.ray_port_forward.terminate()
            print("Ray dashboard port forwarding stopped")
    
        helper.delete_all_resources_in_namespace()
    
def main():

    # Load environment variables from .env file
    env_file_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(env_file_path)

    worker_template_path = os.path.join(os.path.dirname(__file__), "raycluster.yaml.template")
    worker_yaml_path = os.path.join(os.path.dirname(__file__), "raycluster.yaml")
    helper.generate_worker_yaml_from_env(env_file_path, worker_template_path, worker_yaml_path)
    
    # Set up port forwarding to Prometheus
    prometheus_process = subprocess.Popen(
        ["kubectl", "port-forward", "svc/prometheus-kube-prometheus-prometheus", "9090:9090", "-n", "monitoring"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Give port forwarding time to establish
    time.sleep(5)

    os.environ["RAY_ADDRESS"] = "http://127.0.0.1:8265"
    
    
    try:
        ob = OptunaBenchmark()

        runner = BenchmarkRunner(benchmark_cls=ob)
        helper.validate_env_vars()

        runner.run()

        ob.calculate_energy_metrics()

        # Save metrics with the best score
        ob.save_metrics("ray_mnist_resource_metrics.json")

        ob.save_prometheus_snapshot_locally(local_dir="prometheus_snapshots")
    

    finally:
        pass
        # Stop port forwarding to Prometheus
        if prometheus_process:
            prometheus_process.terminate()
            print("Prometheus port forwarding stopped")



if __name__ == "__main__":
    main()