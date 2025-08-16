import os
from abc import ABC, abstractmethod
from dotenv import load_dotenv, dotenv_values
import time
import subprocess
from kubernetes import client, config, watch



class Experiment(ABC):
    """
    This class serves as an Interface for a experiment. All neccessary methods have to be implemented in the
    subclass that is using the interface. 
    """

    @abstractmethod
    def setup(self):
        """
        Every Operation that is needed before the actual optimization (trial) starts.

        """
        pass

    @abstractmethod
    def trial(self):
        """
            Executing the hyperparameter optimization on the deployed platfrom.
        """
        pass

    @abstractmethod
    def deprovision(self):
        # TODO: might be moved before collecting all metrics
        """
            The clean-up procedure to undeploy all components of the HPO Framework that were deployed in the
            Deploy step.
        """
        pass


class ExperimentRunner():

    def __init__(
            self, experiment_cls: Experiment) -> None:
        """
        This class runs a Experiment.
        It is responsibile for setting up everything that is needed upfront to run the experiment and manages
        recording and saving of experiment results.
        """
        self.experiment = experiment_cls

    def run(self):
        """
        Runs all functions of a Experiment. 
        """

        self.experiment.setup()
        self.experiment.trial()
        self.experiment.deprovision()

class HelperFunctions():
    def __init__(self, namespace="default"):
        self.namespace = namespace
        config.load_kube_config()
        self.k8s_client = client.ApiClient()
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.batch_v1 = client.BatchV1Api()

    def build_docker_image(self, image_name, dockerfile_path=None):
        if dockerfile_path is None:
            dockerfile_path = os.path.join(os.path.dirname(__file__))
        command = f"docker build -t {image_name} {dockerfile_path}"
        subprocess.run(command, shell=True, check=True)
    
    def build_and_push_image(self, image_name, dockerfile_dir, registry_url, username):
        """
        Build and push a Docker image to a remote registry.

        Args:
            image_name (str): The name/tag for the image (e.g., "optuna-kubernetes-mlflow3:example").
            dockerfile_dir (str): Directory containing the Dockerfile.
            registry_url (str): Registry URL (e.g., "docker.io" for Docker Hub).
            username (str): Your registry username.
        """
        # Full image path
        full_image = f"{registry_url}/{username}/{image_name}"

        # Build the image
        print(f"Building Docker image: {full_image}")
        subprocess.run(["docker", "build", "-t", full_image, dockerfile_dir], check=True)

        # Push the image
        print(f"Pushing Docker image: {full_image}")
        subprocess.run(["docker", "push", full_image], check=True)

        print("Build and push complete!")
        return full_image

    def load_docker_image_into_kind(self, image_name, ):
        command = f"kind load docker-image {image_name} --name kind"
        subprocess.run(command, shell=True, check=True)

    def create_configmap_from_env(self, env_file_path, configmap_name):
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
        try:
            self.core_v1.create_namespaced_config_map(self.namespace, body=configmap)
            print(f"ConfigMap '{configmap_name}' created successfully in namespace '{self.namespace}'.")
        except client.exceptions.ApiException as e:
            if e.status == 409:  # Conflict: ConfigMap already exists
                print(f"ConfigMap '{configmap_name}' already exists. Skipping creation.")
            else:
                print(f"Error creating ConfigMap: {e}")

    def generate_worker_yaml_from_env(self, env_path, template_path, output_path):
        """Generate a worker YAML file with parameters from .env file."""
        env = dotenv_values(env_path)

        # Get values with defaults
        parallelism = env.get("PARALLELISM")  
        pod_cpu = env.get("POD_CPU")        
        pod_memory = env.get("POD_MEMORY")  

        with open(template_path) as f:
            content = f.read()

        # Replace all placeholders
        content = content.replace("{{PARALLELISM}}", str(parallelism))
        content = content.replace("{{POD_CPU}}", str(pod_cpu))
        content = content.replace("{{POD_MEMORY}}", str(pod_memory))

        with open(output_path, "w") as f:
            f.write(content)

        print(f"Generated {output_path} with PARALLELISM={parallelism}, CPU={pod_cpu}m, Memory={pod_memory}Mi")

    def wait_for_pods_ready(self, label_selector, number_jobs, target_phase):
        """
        Wait for pods matching the label selector to reach the target phase.

        Args:
            label_selector (str): Kubernetes label selector
            target_phase (str): Target pod phase ('Running', 'Succeeded', etc)
            timeout (int): Maximum time to wait in seconds
        """

        # Get the job to determine expected completions
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
                self.core_v1.list_namespaced_pod,
                self.namespace,
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
                        print("All pods have completed successfully!")
                        w.stop()
                        break
                

        except Exception as e:
            print(f"Error watching pods: {e}")
        finally:
            # Make sure we stop the watch
            w.stop()

        print(f"Completed pods: {len(completed_pods)}/{expected_completions}")

    def delete_all_resources_in_namespace(self):
        """
        Delete all resources in the specified Kubernetes namespace.

        Args:
            namespace (str): The namespace from which to delete all resources.
        """

        print(f"Deleting all resources in namespace '{self.namespace}'...")

        # Delete all pods
        pods = self.core_v1.list_namespaced_pod(namespace=self.namespace)
        for pod in pods.items:
            try:
                self.core_v1.delete_namespaced_pod(name=pod.metadata.name, namespace=self.namespace, body=client.V1DeleteOptions())
                print(f"Deleted pod: {pod.metadata.name}")
            except client.exceptions.ApiException as e:
                print(f"Error deleting pod {pod.metadata.name}: {e}")

        # Delete all deployments
        deployments = self.apps_v1.list_namespaced_deployment(namespace=self.namespace)
        for deployment in deployments.items:
            try:
                self.apps_v1.delete_namespaced_deployment(name=deployment.metadata.name, namespace=self.namespace, body=client.V1DeleteOptions())
                print(f"Deleted deployment: {deployment.metadata.name}")
            except client.exceptions.ApiException as e:
                print(f"Error deleting deployment {deployment.metadata.name}: {e}")

        # Delete all services
        services = self.core_v1.list_namespaced_service(namespace=self.namespace)
        for service in services.items:
            try:
                self.core_v1.delete_namespaced_service(name=service.metadata.name, namespace=self.namespace, body=client.V1DeleteOptions())
                print(f"Deleted service: {service.metadata.name}")
            except client.exceptions.ApiException as e:
                print(f"Error deleting service {service.metadata.name}: {e}")

        print("All resources deleted.")

    def validate_env_vars(self,     
        required_vars = [
        "EPOCHS",
        "PARALLELISM",
        "MODEL_IMPLEMENTATION",
        "POD_CPU",
        "POD_MEMORY",
        "ACCELERATOR_TYPE",
        "ACCELERATOR_MEMORY",
        "DATA_LOADING_METHOD",
        "WORKER_NODE_SYNC",
        "COMP_DISTRIBUTION",
        "HPO_FRAMEWORK",
        "HPO_IMPLEMENTATION"
    ]):
        load_dotenv()
        missing_vars = [var for var in required_vars if os.getenv(var) is None]
        if missing_vars:
            raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

    
    
        


