import inspect
import json
import os
import random
from abc import ABC, abstractmethod
from datetime import datetime
from time import sleep
from kubernetes import client, config, utils, watch
import time

import docker
import numpy as np
import torch
import logging


class Benchmark(ABC):
    """
    This class serves as an Interface for a benchmark. All neccessary methods have to be implemented in the
    subclass that is using the interface. Make sure to use the predefined static variables. Your benchmark
    will most likely not run properly if the variables value remains to be "None".
    """

    def __init__(self):
        """Initialize the benchmark with an empty components dictionary."""
        self.components = {} 


class BenchmarkComponent:
    """
    A component of a benchmark that can be deployed, set up, run, and undeployed.
    Used for creating modular benchmarks where each component handles a specific part
    of the benchmark (e.g., database, workers, etc.).
    """
    
    def __init__(self, name):
        """Initialize a benchmark component with a name."""
        self.name = name
    
    def record_timestamp(self, event_name):
        """Record a timestamp for a specific event"""
        self.timestamps[event_name] = time.time()
        return self.timestamps[event_name]
    
    def get_timestamp(self, event_name):
        """Get a timestamp for a specific event"""
        return self.timestamps.get(event_name)
        
    def get_duration(self, start_event, end_event):
        """Calculate duration between two events"""
        if start_event in self.timestamps and end_event in self.timestamps:
            return self.timestamps[end_event] - self.timestamps[start_event]
        return None
    
    def deploy(self):
        """Deploy this component."""
        print(f"Deploying component: {self.name}")
    
    def run(self):
        """Run this component."""
        print(f"Running component: {self.name}")
    
    def undeploy(self):
        """Undeploy this component."""
        print(f"Undeploying component: {self.name}")
    
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

                    return

                # Status update every 10 seconds
                elapsed = time.time() - start_time
                if int(elapsed) % 10 == 0:
                    print(f"Waiting: {len(completed_pods)}/{total_pods} pods in {target_phase} state ({elapsed:.0f}s elapsed)")


        except Exception as e:
            print(f"Error watching pods: {e}")
        finally:
            w.stop()


class BenchmarkRunner():

    def __init__(
            self, benchmark_cls: Benchmark,
            #resources: dict,
            name: str = "") -> None:
        """
        This class runs a Benchmark.
        It is responsibile for setting up everything that is needed upfront to run the benchmark and manages
        recording and saving of benchmark results. It aswell records the Latency of every Step of an
        object that inherits the Benchmark ABC.
        Before a Benchmark is run seeds are set to ensure identical results for every probabilistic
        interference.

        On initialization the BenchmarkRunner creates a folder to store results. Benchmark run on tasks, which
        can be varied. Data and necessary static configurations, that do not affect the Benchmark are loaded
        with the task.

        Args:
            benchmark_cls (Benchmark): _description_
            config (dict): _description_
            grid (dict): _description_
            resources (dict): _description_
            task_str (str, optional): _description_. Defaults to "mnist".
        """
        # TODO: add a benchmark validator, which checks if things are correctly defined e.g.: helper functions only: "_functionname"
        # generate a unique name from the config
        #self.rundate = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        #benchmark_path = os.path.abspath(os.path.dirname(inspect.getabsfile(benchmark_cls)))
        #self.bench_name = f"{benchmark_cls.__name__}__{name}__"
        #self.bench_goal = resources.get("goal", "debug")
        #self.benchmark_folder = os.path.join(benchmark_path, f"benchmark__{self.bench_name}")
        #self.create_benchmark_folder(self.benchmark_folder)
        #self.resources = resources
        #self.workload_definition = resources.get("workload")

        # add input and output size to the benchmark.
        self.benchmark = benchmark_cls

        # set seeds
        #self._set_all_seeds()

    def run(self, workflow):
        """
        Runs all functions of a Benchmark using either a custom workflow or the default sequence.

        Args:
            custom_workflow (list, optional): List of (component_name, method_name) tuples defining 
                                              the execution order.

        Example custom_workflow:
            [
                ("postgres", "deploy"),
                ("postgres", "setup"), 
                ("study_creator", "deploy"),
                ("workers", "deploy"),
                ("workers", "run")
            ]
        """
 
        # Execute the custom workflow
        print("Executing custom workflow")
        # Check if the benchmark has components
        if not hasattr(self.benchmark, 'components'):
            raise ValueError("Benchmark must have a 'components' dictionary to use custom workflow")
        # Execute each step in the workflow
        for component_name, method_name in workflow:
            if component_name not in self.benchmark.components:
                raise ValueError(f"Component '{component_name}' not found in benchmark")
            component = self.benchmark.components[component_name]
            if not hasattr(component, method_name):
                raise ValueError(f"Method '{method_name}' not found in component '{component_name}'")
            # Execute the step
            print(f"Executing {component_name}.{method_name}()")
            method = getattr(component, method_name)
            method()
    

