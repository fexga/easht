import os
from kubernetes import client, config, utils, watch
import subprocess
from basht2.metric_collector.metric_collector import MetricCollector
import time
from dotenv import dotenv_values, load_dotenv
from ray.job_submission import JobSubmissionClient

from basht2.benchmark_template.experiment_runner import BenchmarkRunner, Benchmark, HelperFunctions

helper = HelperFunctions()

class OptunaBenchmark(Benchmark, MetricCollector):

    def __init__(self):
        MetricCollector.__init__(self)  # Initialize the KeplerMetrics class

    @MetricCollector.measure_power(aggregation_method='increase')
    def setup(self):
        config.load_kube_config()
        k8s_client = client.ApiClient()

        kuberay_path = os.path.join(os.path.dirname(__file__), 'kuberay-manifests/default')
        utils.create_from_directory(k8s_client, kuberay_path)

        # Wait for Operator pod to be running
        print("Waiting for Operator pod to be ready...")
        helper._wait_for_pods_ready(label_selector="app.kubernetes.io/component=kuberay-operator", number_jobs=1,  target_phase="Running")
        print("Operator deployment complete!")

        print(f"Waiting 5 additional seconds for services to initialize...")
        time.sleep(5)
        print("Extra waiting period complete.")

        raycluster_path = os.path.join(os.path.dirname(__file__), 'raycluster.yaml')
        utils.create_from_yaml(k8s_client, raycluster_path)

        print("Waiting for Ray Cluster to complete...")
        helper._wait_for_pods_ready(label_selector="ray.io/node-type=head", number_jobs=1,  target_phase="Running")
        print("Study setup complete!")

    @MetricCollector.measure_power(aggregation_method='increase')
    def run(self):

        ray_address = os.environ.get("RAY_ADDRESS", "http://127.0.0.1:8265")
        client = JobSubmissionClient(ray_address)

        # Define the runtime environment
        runtime_env = {
            "pip": "ray_cluster/requirements.txt"  # Path to requirements.txt
        }

        # Submit the job
        job_id = client.submit_job(
            entrypoint="python script.py",
            runtime_env=runtime_env,
            working_dir="ray_cluster"
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
        self._set_ray_f1_score()
        """Delete all resources in the namespace and wait until they are gone."""
    
        helper._delete_all_resources_in_namespace()
    
def main():
    
    # Set up port forwarding to Prometheus
    env_file_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(env_file_path)

    #worker_template_path = os.path.join(os.path.dirname(__file__), "worker.yaml.template")
    #worker_yaml_path = os.path.join(os.path.dirname(__file__), "worker.yaml")
    #helper.generate_worker_yaml_from_env(env_file_path, worker_template_path, worker_yaml_path)

    # Create the ConfigMap from the .env file
    #helper._create_configmap_from_env(env_file_path, configmap_name="training-config")
    
    # Set up port forwarding to Prometheus
    
    prometheus_process = subprocess.Popen(
        ["kubectl", "port-forward", "svc/prometheus-kube-prometheus-prometheus", "9090:9090", "-n", "monitoring"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Give port forwarding time to establish
    time.sleep(5)
    
    
    try:
        #optuna_path = os.path.dirname(__file__)
        #helper._build_docker_image("optuna-kubernetes-mlflow3:example", dockerfile_path=optuna_path)
        #helper._load_docker_image_into_kind("optuna-kubernetes-mlflow3:example")

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