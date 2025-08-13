import os
from kubernetes import client, config, utils
import subprocess
from easht.metric_collector.metric_collector import MetricCollector
import time
from dotenv import dotenv_values, load_dotenv

from easht.benchmark_template.experiment_runner import ExperimentRunner, Experiment, HelperFunctions

helper = HelperFunctions(namespace="st-felixgraf2")

class OptunaBenchmark(Experiment, MetricCollector):

    def __init__(self):
        MetricCollector.__init__(self)  # Initialize the KeplerMetrics class
        self.namespace = "st-felixgraf2"

    @MetricCollector.measure_power(aggregation_method='increase')
    def setup(self):
        config.load_kube_config()
        k8s_client = client.ApiClient()

        manifest_path = os.path.join(os.path.dirname(__file__), 'postgres-manifest.yaml')
        utils.create_from_yaml(k8s_client, manifest_path, namespace=self.namespace)

        # Wait for PostgreSQL pod to be running
        print("Waiting for PostgreSQL pods to be ready...")
        helper.wait_for_pods_ready(label_selector="app=postgres", number_jobs=1, target_phase="Running")
        print("PostgreSQL deployment complete!")

        print(f"Waiting 30 additional seconds for services to initialize...")
        time.sleep(30)
        print("Extra waiting period complete.")


        manifest_path = os.path.join(os.path.dirname(__file__), "study-creator.yaml")
        utils.create_from_yaml(k8s_client, manifest_path, namespace=self.namespace)

        print("Waiting for study-creator job to complete...")
        helper.wait_for_pods_ready(label_selector="job-name=study-creator", number_jobs=1,  target_phase="Succeeded")
        print("Study setup complete!")

    @MetricCollector.measure_power(aggregation_method='increase')
    def trail(self):
        config.load_kube_config()
        k8s_client = client.ApiClient()

        env_path = os.path.join(os.path.dirname(__file__), ".env")
        env_vars = dotenv_values(env_path)
        number_jobs = int(env_vars.get("PARALLELISM", 3))  # Default to 3 if not set

        manifest_path = os.path.join(os.path.dirname(__file__), "worker.yaml")
        utils.create_from_yaml(k8s_client, manifest_path, namespace=self.namespace)

        print("Waiting for worker pods to finish...")
        helper.wait_for_pods_ready(label_selector="job-name=worker", number_jobs=number_jobs,  target_phase="Succeeded")

    @MetricCollector.measure_power(aggregation_method='increase')
    def deprovision(self):
        self._set_f1_score()
        """Delete all resources in the namespace and wait until they are gone."""
        config.load_kube_config()
        apps_v1 = client.AppsV1Api()
    
        print(f"Deleting all resources in namespace '{self.namespace}'...")
    
        # Delete the StatefulSet
        try:
            print("Deleting StatefulSet: postgres...")
            apps_v1.delete_namespaced_stateful_set(name="postgres", namespace=self.namespace)
        except client.exceptions.ApiException as e:
            if e.status == 404:
                print("StatefulSet 'postgres' not found, skipping.")
            else:
                print(f"Error deleting StatefulSet 'postgres': {e}")
    
        helper.delete_all_resources_in_namespace()
    
def main():
    
    # Set up port forwarding to Prometheus
    env_file_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(env_file_path)

    worker_template_path = os.path.join(os.path.dirname(__file__), "worker.yaml.template")
    worker_yaml_path = os.path.join(os.path.dirname(__file__), "worker.yaml")
    helper.generate_worker_yaml_from_env(env_file_path, worker_template_path, worker_yaml_path)

    # Create the ConfigMap from the .env file
    helper.create_configmap_from_env(env_file_path, configmap_name="training-config")
    
    # Set up port forwarding to Prometheus
    prometheus_process = subprocess.Popen(
        ["kubectl", "port-forward", "svc/prometheus-kube-prometheus-prometheus", "9090:9090", "-n", "st-felixgraf-monitoring"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Give port forwarding time to establish
    time.sleep(5)
    
    
    try:
        optuna_path = os.path.dirname(__file__)
        helper.build_and_push_image(
            image_name="optuna-mnist:ise-kube",
            dockerfile_dir=os.path.join(optuna_path),
            registry_url="docker.io",
            username="gafex"
        )

        ob = OptunaBenchmark()

        runner = ExperimentRunner(experiment_cls=ob)
        helper.validate_env_vars()

        runner.run()

        ob.calculate_energy_metrics()

        # Save metrics with the best score
        ob.save_metrics("optuna_mnist_resource_metrics.json")

        #ob.save_prometheus_snapshot_locally(local_dir="prometheus_snapshots")
    

    finally:
        pass
        # Stop port forwarding to Prometheus
        if prometheus_process:
            prometheus_process.terminate()
            print("Prometheus port forwarding stopped")



if __name__ == "__main__":
    main()