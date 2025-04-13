import os
import sys
import docker
from kubernetes import client, config, utils, watch
import yaml
import subprocess
import sys
from kepler_metrics import KeplerMetrics
import time

from benchmark_template.experiment_runner import BenchmarkRunner, Benchmark, BenchmarkComponent

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

class PostgresComponent(BenchmarkComponent):
    def __init__(self):
        super().__init__("postgres")
        
    def deploy(self):
        super().deploy()
        self.record_timestamp("postgres_deploy_start")
        config.load_kube_config()
        k8s_client = client.ApiClient()
        manifest_path = os.path.join(os.path.dirname(__file__), 'postgres-manifest.yaml')
        utils.create_from_yaml(k8s_client, manifest_path)
        self._wait_for_pods_ready("app=postgres", "Running")
        print("PostgreSQL deployment complete!")
        self.record_timestamp("postgres_deploy_end")

        
    def run(self):
        self.record_timestamp("postgres_run_start")
        super().run()


class StudyCreatorComponent(BenchmarkComponent):
    def __init__(self):
        super().__init__("study_creator")
        
    def deploy(self):
        self.record_timestamp("study_creator_deploy_start")
        config.load_kube_config()
        k8s_client = client.ApiClient()

        manifest_path = os.path.join(os.path.dirname(__file__), "study-creator.yaml")
        utils.create_from_yaml(k8s_client, manifest_path)

        print("Waiting for study-creator job to complete...")
        self._wait_for_pods_ready("job-name=study-creator", "Succeeded")
        print("Study setup complete!")
        self.record_timestamp("study_creator_deploy_end")
        
    def run(self):
        self.record_timestamp("study_creator_run_start")
        super().run()


class WorkerComponent(BenchmarkComponent):
    def __init__(self, worker_count=5):
        super().__init__("workers")
        self.worker_count = worker_count

    def deploy(self):
        self.record_timestamp("worker_deploy_start")
        super().deploy()
        config.load_kube_config()
        k8s_client = client.ApiClient()

        manifest_path = os.path.join(os.path.dirname(__file__), "worker.yaml")
        utils.create_from_yaml(k8s_client, manifest_path)

        # Wait for the pods to start (initial delay)
        print("Waiting for worker pods to start...")
        time.sleep(10)
        self.record_timestamp("worker_deploy_end")

    def run(self):
        # Get the job to determine expected completions
        self.record_timestamp("worker_run_start")
        core_v1 = client.CoreV1Api() 
        
        expected_completions = self.worker_count
        print(f"Job expects {expected_completions} completions")

        # Set up monitoring
        completed_pods = set()

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
        
        self.record_timestamp("worker_run_end")
        
        if self.postgres_component:
            self.postgres_component.record_timestamp("postgres_run_end")
        
        if self.study_creator_component:
            self.study_creator_component.record_timestamp("study_creator_run_end")

        # Final status report
        print(f"Completed pods: {len(completed_pods)}/{expected_completions}")
        



class OptunaBenchmark(Benchmark, KeplerMetrics):

    def __init__(self):
        Benchmark.__init__(self)  # Initialize the Benchmark class
        KeplerMetrics.__init__(self)  # Initialize the KeplerMetrics class




def main():
    
    # Set up port forwarding to Prometheus
    
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
        build_docker_image("optuna-kubernetes-mlflow3:example")
        load_docker_image_into_kind("optuna-kubernetes-mlflow3:example")

        postgres = PostgresComponent()
        study_creator = StudyCreatorComponent()
        workers = WorkerComponent(worker_count=5, postgres_component=postgres, study_creator_component=study_creator)
        
        ob.components = [postgres, study_creator, workers]

        ob = OptunaBenchmark()
        runner = BenchmarkRunner(benchmark_cls=ob)
        runner.run()

        ob.calculate_energy_metrics()

        ob.save_metrics("optuna_mnist_resource_metrics.csv")
    
    
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