import os
import sys
import docker
from kubernetes import client, config, utils, watch
import yaml
import subprocess
import sys
from kepler_metrics import KeplerMetrics
import time

from benchmark_template.experiment_runner import BenchmarkRunner, Benchmark

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


class OptunaBenchmark(Benchmark, KeplerMetrics):

    def __init__(self):
        KeplerMetrics.__init__(self)  # Initialize the KeplerMetrics class

    @KeplerMetrics.measure_power
    def deploy(self) -> None:
        config.load_kube_config()
        k8s_client = client.ApiClient()

        manifest_path = os.path.join(os.path.dirname(__file__), 'postgres-manifest.yaml')
        utils.create_from_yaml(k8s_client, manifest_path)

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

    @KeplerMetrics.measure_power
    def setup(self):
        config.load_kube_config()
        k8s_client = client.ApiClient()

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

    @KeplerMetrics.measure_power
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
        expected_completions = job.spec.completions or 1
        print(f"Job expects {expected_completions} completions")

        # Set up monitoring
        completed_pods = set()
        max_wait_time = 900  # 15 minutes maximum wait time
        start_time = time.time()

        # Create a watch for pod status changes
        w = watch.Watch()

        try:
            # Watch for pod status changes
            for event in w.stream(
                core_v1.list_namespaced_pod,
                namespace="default",
                label_selector="job-name=worker",
                timeout_seconds=max_wait_time
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
                    
                # Status update every 15 seconds
                elapsed = time.time() - start_time
                if int(elapsed) % 15 == 0:
                    remaining_pods = expected_completions - len(completed_pods)
                    print(f"Waiting: {len(completed_pods)}/{expected_completions} pods completed, {remaining_pods} remaining ({elapsed:.0f}s elapsed)")

                # Check timeout
                if elapsed > max_wait_time:
                    print(f"Reached maximum wait time of {max_wait_time/60:.1f} minutes")
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

    @KeplerMetrics.measure_power
    def undeploy(self):

        pass

def main():
    
    # Set up port forwarding to Prometheus
    
    prometheus_process = subprocess.Popen(
        ["kubectl", "port-forward", "svc/prometheus-kube-prometheus-prometheus", "9090:9090", "-n", "monitoring"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Give port forwarding time to establish
    time.sleep(5)
    
    
    try:
        # Set Docker environment variables for Minikube
        subprocess.run(["eval", "$(minikube -p docker-env)"], shell=True, check=True)
        build_docker_image("optuna-kubernetes-mlflow3:example")
        load_docker_image_into_kind("optuna-kubernetes-mlflow3:example")
        ob = OptunaBenchmark()
        runner = BenchmarkRunner(benchmark_cls=ob)
        runner.run()
    
    
    finally:
        # Stop port forwarding to Prometheus
        if prometheus_process:
            prometheus_process.terminate()
            print("Prometheus port forwarding stopped")
    



if __name__ == "__main__":
    #if len(sys.argv) != 3:
    #    print("Usage: python run_experiment.py <is_minikube> <image_name>")
    #    sys.exit(1)

    #is_minikube = sys.argv[1].lower() == "true"
    #image_name = sys.argv[2]

    main()