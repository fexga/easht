import os
from kubernetes import client, config, utils, watch
import subprocess
from basht2.metric_collector.metric_collector import MetricCollector
import time
from dotenv import dotenv_values, load_dotenv

from basht2.benchmark_template.experiment_runner import BenchmarkRunner, Benchmark, HelperFunctions

helper = HelperFunctions()

'''
def build_docker_image(image_name):
    dockerfile_path = os.path.join(os.path.dirname(__file__))
    command = f"docker build -t {image_name} {dockerfile_path}"
    subprocess.run(command, shell=True, check=True)

def load_docker_image_into_kind(image_name, ):
    command = f"kind load docker-image {image_name} --name kind"
    subprocess.run(command, shell=True, check=True)

def create_configmap_from_env(env_file_path, configmap_name, namespace="default"):
    """
    Create a Kubernetes ConfigMap from a .env file.

    Args:
        env_file_path (str): Path to the .env file.
        configmap_name (str): Name of the ConfigMap to create.
        namespace (str): Kubernetes namespace to create the ConfigMap in.
    """
    # Load the .env file
    env_vars = dotenv_values(env_file_path)

    # Load Kubernetes configuration
    config.load_kube_config()

    # Define the ConfigMap data
    configmap_data = {key: str(value) for key, value in env_vars.items()}

    # Create the ConfigMap object
    configmap = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(name=configmap_name),
        data=configmap_data
    )

    # Create the ConfigMap in the specified namespace
    core_v1 = client.CoreV1Api()
    try:
        core_v1.create_namespaced_config_map(namespace=namespace, body=configmap)
        print(f"ConfigMap '{configmap_name}' created successfully in namespace '{namespace}'.")
    except client.exceptions.ApiException as e:
        if e.status == 409:  # Conflict: ConfigMap already exists
            print(f"ConfigMap '{configmap_name}' already exists. Skipping creation.")
        else:
            print(f"Error creating ConfigMap: {e}")

def generate_worker_yaml_from_env(env_path, template_path, output_path):
    env = dotenv_values(env_path)
    parallelism = env.get("PARALLELISM", "3")  # Default to 3 if not set

    with open(template_path) as f:
        content = f.read()

    content = content.replace("{{PARALLELISM}}", str(parallelism))

    with open(output_path, "w") as f:
        f.write(content)
'''

class OptunaBenchmark(Benchmark, MetricCollector):

    def __init__(self):
        MetricCollector.__init__(self)  # Initialize the KeplerMetrics class

    '''
    def _wait_for_pods_ready(self, label_selector, number_jobs, namespace_name, target_phase):
        """
        Wait for pods matching the label selector to reach the target phase.

        Args:
            label_selector (str): Kubernetes label selector
            target_phase (str): Target pod phase ('Running', 'Succeeded', etc)
            timeout (int): Maximum time to wait in seconds
        """
        config.load_kube_config()
        core_v1 = client.CoreV1Api()
        batch_v1 = client.BatchV1Api()

        # Get the job to determine expected completions
        #job = batch_v1.read_namespaced_job(name=label_selector, namespace=namespace_name)
        #expected_completions = job.spec.completions or 5
        expected_completions = number_jobs
        print(f"Job expects {expected_completions} completions")

        # Set up monitoring
        completed_pods = set()
        start_time = time.time()

        # Create a watch for pod status changes
        w = watch.Watch()

        try:
            # Watch for pod status changes
            for event in w.stream(
                core_v1.list_namespaced_pod,
                namespace="default",
                label_selector=label_selector,
            ):
                pod = event['object']
                pod_name = pod.metadata.name

                # If the pod succeeded and we haven't counted it yet
                if pod_name not in completed_pods and pod.status.phase == target_phase:
                    completed_pods.add(pod_name)
                    print(f"Pod {pod_name} completed successfully ({len(completed_pods)}/{expected_completions})")

                    # If all expected pods are complete, we're done
                    if len(completed_pods) >= expected_completions:
                        print("All worker pods have completed successfully!")
                        w.stop()
                        break
                

        except Exception as e:
            print(f"Error watching pods: {e}")
        finally:
            # Make sure we stop the watch
            w.stop()

        # Final status report
        elapsed = time.time() - start_time
        print(f"Training job monitoring completed after {elapsed:.1f} seconds")
        print(f"Completed pods: {len(completed_pods)}/{expected_completions}")

    def _delete_all_resources_in_namespace(self, namespace):
        """
        Delete all resources in the specified Kubernetes namespace.

        Args:
            namespace (str): The namespace from which to delete all resources.
        """
        config.load_kube_config()
        core_v1 = client.CoreV1Api()
        apps_v1 = client.AppsV1Api()

        print(f"Deleting all resources in namespace '{namespace}'...")

        # Delete all pods
        pods = core_v1.list_namespaced_pod(namespace=namespace)
        for pod in pods.items:
            try:
                core_v1.delete_namespaced_pod(name=pod.metadata.name, namespace=namespace, body=client.V1DeleteOptions())
                print(f"Deleted pod: {pod.metadata.name}")
            except client.exceptions.ApiException as e:
                print(f"Error deleting pod {pod.metadata.name}: {e}")

        # Delete all deployments
        deployments = apps_v1.list_namespaced_deployment(namespace=namespace)
        for deployment in deployments.items:
            try:
                apps_v1.delete_namespaced_deployment(name=deployment.metadata.name, namespace=namespace, body=client.V1DeleteOptions())
                print(f"Deleted deployment: {deployment.metadata.name}")
            except client.exceptions.ApiException as e:
                print(f"Error deleting deployment {deployment.metadata.name}: {e}")

        # Delete all services
        services = core_v1.list_namespaced_service(namespace=namespace)
        for service in services.items:
            try:
                core_v1.delete_namespaced_service(name=service.metadata.name, namespace=namespace, body=client.V1DeleteOptions())
                print(f"Deleted service: {service.metadata.name}")
            except client.exceptions.ApiException as e:
                print(f"Error deleting service {service.metadata.name}: {e}")

        print("All resources deleted.")
    '''

    @MetricCollector.measure_power(aggregation_method='increase')
    def setup(self):
        config.load_kube_config()
        k8s_client = client.ApiClient()

        manifest_path = os.path.join(os.path.dirname(__file__), 'postgres-manifest.yaml')
        utils.create_from_yaml(k8s_client, manifest_path)

        # Wait for PostgreSQL pod to be running
        print("Waiting for PostgreSQL pods to be ready...")
        helper._wait_for_pods_ready(label_selector="app=postgres", number_jobs=1,  target_phase="Running")
        print("PostgreSQL deployment complete!")

        print(f"Waiting 15 additional seconds for services to initialize...")
        time.sleep(15)
        print("Extra waiting period complete.")


        manifest_path = os.path.join(os.path.dirname(__file__), "study-creator.yaml")
        utils.create_from_yaml(k8s_client, manifest_path)

        print("Waiting for study-creator job to complete...")
        helper._wait_for_pods_ready(label_selector="job-name=study-creator", number_jobs=1,  target_phase="Succeeded")
        print("Study setup complete!")

    @MetricCollector.measure_power(aggregation_method='increase')
    def run(self):
        config.load_kube_config()
        k8s_client = client.ApiClient()

        env_path = os.path.join(os.path.dirname(__file__), ".env")
        env_vars = dotenv_values(env_path)
        number_jobs = int(env_vars.get("PARALLELISM", 3))  # Default to 3 if not set

        manifest_path = os.path.join(os.path.dirname(__file__), "worker.yaml")
        utils.create_from_yaml(k8s_client, manifest_path)

        print("Waiting for worker pods to finish...")
        helper._wait_for_pods_ready(label_selector="job-name=worker", number_jobs=number_jobs,  target_phase="Succeeded")

    @MetricCollector.measure_power(aggregation_method='increase')
    def deprovision(self):
        self._set_f1_score()
        """Delete all resources in the namespace and wait until they are gone."""
        config.load_kube_config()
        apps_v1 = client.AppsV1Api()
        namespace = "default"  # Specify the namespace
    
        print(f"Deleting all resources in namespace '{namespace}'...")
    
        # Delete the StatefulSet
        try:
            print("Deleting StatefulSet: postgres...")
            apps_v1.delete_namespaced_stateful_set(name="postgres", namespace=namespace)
        except client.exceptions.ApiException as e:
            if e.status == 404:
                print("StatefulSet 'postgres' not found, skipping.")
            else:
                print(f"Error deleting StatefulSet 'postgres': {e}")
    
        helper._delete_all_resources_in_namespace()
    
def main():
    
    # Set up port forwarding to Prometheus
    env_file_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(env_file_path)

    worker_template_path = os.path.join(os.path.dirname(__file__), "worker.yaml.template")
    worker_yaml_path = os.path.join(os.path.dirname(__file__), "worker.yaml")
    helper.generate_worker_yaml_from_env(env_file_path, worker_template_path, worker_yaml_path)

    # Create the ConfigMap from the .env file
    helper._create_configmap_from_env(env_file_path, configmap_name="training-config")
    
    # Set up port forwarding to Prometheus
    REQUIRED_ENV_VARS = ["BATCHSIZE", "EPOCHS", "PERCENT_VALID_EXAMPLES", "CLASSES"]
    
    prometheus_process = subprocess.Popen(
        ["kubectl", "port-forward", "svc/prometheus-kube-prometheus-prometheus", "9090:9090", "-n", "monitoring"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Give port forwarding time to establish
    time.sleep(5)
    
    
    try:
        optuna_path = os.path.dirname(__file__)
        helper._build_docker_image("optuna-kubernetes-mlflow3:example", dockerfile_path=optuna_path)
        helper._load_docker_image_into_kind("optuna-kubernetes-mlflow3:example")

        ob = OptunaBenchmark()

        runner = BenchmarkRunner(benchmark_cls=ob)
        helper.validate_env_vars()

        runner.run()

        ob.calculate_energy_metrics()

        # Save metrics with the best score
        ob.save_metrics("optuna_mnist_resource_metrics.json")

        ob.save_prometheus_snapshot_locally(local_dir="prometheus_snapshots")
    

    finally:
        pass
        # Stop port forwarding to Prometheus
        if prometheus_process:
            prometheus_process.terminate()
            print("Prometheus port forwarding stopped")



if __name__ == "__main__":
    main()