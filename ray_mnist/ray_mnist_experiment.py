import os
from kubernetes import client, config, utils, watch
import subprocess
from basht2.metric_collector.metric_collector import MetricCollector
import time
from dotenv import dotenv_values, load_dotenv

from basht2.benchmark_template.experiment_runner import BenchmarkRunner, Benchmark, HelperFunctions

class RayBenchmark(Benchmark, MetricCollector):
    def __init__(self):
        MetricCollector.__init__(self)

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
        
