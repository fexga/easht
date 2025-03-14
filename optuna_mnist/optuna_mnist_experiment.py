import os
import sys
import docker
from kubernetes import client, config, utils
import yaml
import subprocess
import sys
from benchmark_template.experiment_runner import BenchmarkRunner, Benchmark


class OptunaBenchmark(Benchmark):

    def build_docker_image():
        client = docker.from_env()
        print(f"Building Docker Image optuna-kubernetes-mlflow3:example")
        client.images.build(path=".", tag='optuna-kubernetes-mlflow3:example')

    def push_docker_image(image_name):
        client = docker.from_env()
        print(f"Pushing Docker Image {image_name}\n")
        client.images.push(image_name)

    def deploy():
        config.load_kube_config()
        k8s_client = client.ApiClient()

        utils.create_from_yaml(k8s_client, "postgres-manifest.yaml")

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

    def setup():
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

        utils.create_from_yaml(k8s_client, "study-creator.yaml")
        #for m in manifest:
        #    if m is not None:
        #        utils.create_from_dict(k8s_client, m)
        #    else:
        #        print("Warning: Encountered a NoneType object in the manifest. Skipping.")

    def trails():
        config.load_kube_config()
        k8s_client = client.ApiClient()

        utils.create_from_yaml(k8s_client, "worker.yaml")

    def undeploy(self):

        pass

def main():
    #if is_minikube:
    subprocess.run(["eval", "$(minikube -p docker-env)"], shell=True, check=True)

    # Build Docker Image
    #build_docker_image()

    OptunaBenchmark.build_docker_image()

    runner = BenchmarkRunner(
        benchmark_cls=OptunaBenchmark)
    runner.run()




if __name__ == "__main__":
    #if len(sys.argv) != 3:
    #    print("Usage: python run_experiment.py <is_minikube> <image_name>")
    #    sys.exit(1)

    #is_minikube = sys.argv[1].lower() == "true"
    #image_name = sys.argv[2]

    main()