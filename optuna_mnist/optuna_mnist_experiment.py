import os
import sys
import docker
from kubernetes import client, config, utils, watch
import yaml
import subprocess
import sys
from kepler_metrics import KeplerMetrics
import time
import optuna
from dotenv import dotenv_values

from benchmark_template.experiment_runner import BenchmarkRunner, Benchmark, validate_env_vars

def build_docker_imageold():
    client = docker.from_env()
    print(f"Building Docker Image optuna-kubernetes-mlflow3:example")
    dockerfile_path = os.path.join(os.path.dirname(__file__))
    client.images.build(path=os.path.dirname(dockerfile_path), tag='optuna-kubernetes-mlflow3:example', dockerfile='Dockerfile', nocache=True)

def build_docker_image(image_name):
    dockerfile_path = os.path.join(os.path.dirname(__file__))
    command = f"docker build -t {image_name} {dockerfile_path}"
    subprocess.run(command, shell=True, check=True)

def load_docker_image_into_kind(image_name, ):
    command = f"kind load docker-image {image_name} --name kind"
    subprocess.run(command, shell=True, check=True)

def push_docker_image(image_name):
    client = docker.from_env()
    print(f"Pushing Docker Image {image_name}\n")
    client.images.push(image_name)

def get_node_ip():
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


class OptunaBenchmark(Benchmark, KeplerMetrics):

    def __init__(self):
        KeplerMetrics.__init__(self)  # Initialize the KeplerMetrics class

    def _wait_for_pods_ready(self, label_selector, target_phase):
        """
        Wait for pods matching the label selector to reach the target phase.

        Args:
            label_selector (str): Kubernetes label selector
            target_phase (str): Target pod phase ('Running', 'Succeeded', etc)
            timeout (int): Maximum time to wait in seconds
        """
        config.load_kube_config()
        core_v1 = client.CoreV1Api()

        start_time = time.time()

        # Keep track of pods we've seen reach the target state
        completed_pods = set()

        w = watch.Watch()
        try:
            for event in w.stream(
                core_v1.list_namespaced_pod,
                namespace="default",
                label_selector=label_selector,
            ):
                pod = event['object']
                pod_name = pod.metadata.name
                current_phase = pod.status.phase

                if current_phase == target_phase and pod_name not in completed_pods:
                    completed_pods.add(pod_name)
                    print(f"Pod {pod_name} reached state: {target_phase}")

                # Get total count of pods with this selector
                pod_list = core_v1.list_namespaced_pod(
                    namespace="default", 
                    label_selector=label_selector
                )
                total_pods = len(pod_list.items)

                # If all pods are ready, we're done
                if len(completed_pods) == total_pods and total_pods > 0:
                    print(f"All {total_pods} pods with selector '{label_selector}' are in {target_phase} state!")
                    w.stop()

                    # Add extra waiting period after pods are ready
                    print(f"Waiting 5 additional seconds for services to initialize...")
                    time.sleep(15)
                    print("Extra waiting period complete.")

                    return

                # Status update every 10 seconds
                elapsed = time.time() - start_time
                if int(elapsed) % 10 == 0:
                    print(f"Waiting: {len(completed_pods)}/{total_pods} pods in {target_phase} state ({elapsed:.0f}s elapsed)")


        except Exception as e:
            print(f"Error watching pods: {e}")
        finally:
            w.stop()

    @KeplerMetrics.measure_power(aggregation_method='sum')
    def deploy(self) -> None:
        config.load_kube_config()
        k8s_client = client.ApiClient()

        manifest_path = os.path.join(os.path.dirname(__file__), 'postgres-manifest.yaml')
        utils.create_from_yaml(k8s_client, manifest_path)

        # Wait for PostgreSQL pod to be running
        print("Waiting for PostgreSQL pods to be ready...")
        self._wait_for_pods_ready("app=postgres", "Running")
        print("PostgreSQL deployment complete!")

        # Load the PostgreSQL manifest
        #with open("postgres-manifest.yaml") as f:
        #    manifest = list(yaml.safe_load_all(f))

        # Apply the manifest
        # print("\nDeploying PostgreSQL to cluster\n")
        #for m in manifest:
        #    if m is not None:
        #        utils.create_from_dict(k8s_client, m)
        #    else:
        #        print("Warning: Encountered a NoneType object in the manifest. Skipping.")

    @KeplerMetrics.measure_power(aggregation_method='sum')
    def setup(self):
        config.load_kube_config()
        k8s_client = client.ApiClient()

        # Wait for study-creator job to complete

        # Load the experiment manifest
        #with open("k8s-manifest.yaml") as f:
            #manifest = list(yaml.safe_load_all(f))

        # Apply the manifest
        #print("\nDeploying experiment to cluster\n")
        #command = ['kubectl', 'apply', '-f', 'k8s-manifest.yaml']
        #subprocess.run(command, check=True)
        #utils.create_from_yaml(k8s_client, "postgres-manifest.yaml")


        manifest_path = os.path.join(os.path.dirname(__file__), "study-creator.yaml")
        utils.create_from_yaml(k8s_client, manifest_path)
        #for m in manifest:
        #    if m is not None:
        #        utils.create_from_dict(k8s_client, m)
        #    else:
        #        print("Warning: Encountered a NoneType object in the manifest. Skipping.")
        print("Waiting for study-creator job to complete...")
        self._wait_for_pods_ready("job-name=study-creator", "Succeeded")
        print("Study setup complete!")

    @KeplerMetrics.measure_power(aggregation_method='sum')
    def run(self):
        config.load_kube_config()
        k8s_client = client.ApiClient()
        core_v1 = client.CoreV1Api()
        batch_v1 = client.BatchV1Api()

        manifest_path = os.path.join(os.path.dirname(__file__), "worker.yaml")
        utils.create_from_yaml(k8s_client, manifest_path)
        # Wait for the pods to start (initial delay)
        print("Waiting for worker pods to start...")
        time.sleep(10)

        # Get the job to determine expected completions
        job = batch_v1.read_namespaced_job(name="worker", namespace="default")
        #expected_completions = job.spec.completions or 5
        expected_completions = 3
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
                label_selector="job-name=worker"
            ):
                pod = event['object']
                pod_name = pod.metadata.name

                # If the pod succeeded and we haven't counted it yet
                if pod_name not in completed_pods and pod.status.phase == "Succeeded":
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

    @KeplerMetrics.measure_power(aggregation_method='rate')
    def undeploy(self):
        self._set_f1_score()
        """Delete all resources in the namespace and wait until they are gone."""
        config.load_kube_config()
        core_v1 = client.CoreV1Api()
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
    
        # List all pods in the namespace
        pods = core_v1.list_namespaced_pod(namespace=namespace)
        pod_names = [pod.metadata.name for pod in pods.items]
    
        # Delete each pod
        for pod_name in pod_names:
            try:
                print(f"Deleting pod: {pod_name}...")
                core_v1.delete_namespaced_pod(name=pod_name, namespace=namespace, body=client.V1DeleteOptions())
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    print(f"Pod {pod_name} not found, skipping.")
                else:
                    print(f"Error deleting pod {pod_name}: {e}")
    
        # Use a watch stream to wait for all pods to be deleted
        print("Waiting for all pods to be deleted...")
        w = watch.Watch()
        start_time = time.time()
    
        try:
            for event in w.stream(core_v1.list_namespaced_pod, namespace=namespace):
                pod = event['object']
                pod_name = pod.metadata.name
                event_type = event['type']
    
                if event_type == "DELETED":
                    print(f"Pod {pod_name} has been deleted.")
    
                # Check if there are any remaining pods
                remaining_pods = core_v1.list_namespaced_pod(namespace=namespace).items
                if not remaining_pods:
                    print("All pods have been successfully deleted.")
                    w.stop()
                    break
                
                # Status update every 10 seconds
                elapsed_time = time.time() - start_time
                if int(elapsed_time) % 10 == 0:
                    remaining_pod_names = [pod.metadata.name for pod in remaining_pods]
                    print(f"Still waiting for pods to be deleted: {', '.join(remaining_pod_names)} ({elapsed_time:.1f}s elapsed)")
    
        except Exception as e:
            print(f"Error watching pods: {e}")
        finally:
            w.stop()
    
def main():
    
    # Set up port forwarding to Prometheus
    env_file_path = os.path.join(os.path.dirname(__file__), ".env")
    

    # Create the ConfigMap from the .env file
    create_configmap_from_env(env_file_path, configmap_name="training-config")
    
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
        # Set Docker environment variables for Minikube
        build_docker_image("optuna-kubernetes-mlflow3:example")
        load_docker_image_into_kind("optuna-kubernetes-mlflow3:example")

        ob = OptunaBenchmark()

        runner = BenchmarkRunner(benchmark_cls=ob)
        validate_env_vars(REQUIRED_ENV_VARS)
        runner.run()

        ob.calculate_energy_metrics()

        # Save metrics with the best score
        ob.save_metrics("optuna_mnist_resource_metrics.json")
    

    finally:
        pass
    '''
        # Stop port forwarding to Prometheus
        if prometheus_process:
            prometheus_process.terminate()
            print("Prometheus port forwarding stopped")
        if postgres_process:
            postgres_process.terminate()
            print("Postgres port forwarding stopped")
    '''
    



if __name__ == "__main__":
    #if len(sys.argv) != 3:
    #    print("Usage: python run_experiment.py <is_minikube> <image_name>")
    #    sys.exit(1)

    #is_minikube = sys.argv[1].lower() == "true"
    #image_name = sys.argv[2]

    main()