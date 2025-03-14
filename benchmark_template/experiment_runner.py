import inspect
import json
import os
import random
from abc import ABC, abstractmethod
from datetime import datetime
from time import sleep

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

    # TODO: objective and grid are not allowed to be in the benchmark
    resources = None

    @abstractmethod
    def deploy(self) -> None:
        """
            With the completion of this step the desired architecture of the HPO Framework should be running
            on a platform, e.g,. in the case of Kubernetes it referes to the steps nassary to deploy all pods
            and services in kubernetes.
        """
        pass

    @abstractmethod
    def setup(self):
        """
        Every Operation that is needed before the actual optimization (trial) starts and that is not relevant
        for starting up workers or the necessary architecture.
        """
        pass

    @abstractmethod
    def run(self):
        """
            Executing the hyperparameter optimization on the deployed platfrom.
            use the metrics object to collect and store all measurments on the workers.
        """
        pass

    @abstractmethod
    def undeploy(self):
        # TODO: might be moved before collecting all metrics
        """
            The clean-up procedure to undeploy all components of the HPO Framework that were deployed in the
            Deploy step.
        """
        pass


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
        self.bench_name = f"{benchmark_cls.__name__}__{name}__"
        #self.bench_goal = resources.get("goal", "debug")
        #self.benchmark_folder = os.path.join(benchmark_path, f"benchmark__{self.bench_name}")
        #self.create_benchmark_folder(self.benchmark_folder)
        #self.resources = resources
        #self.workload_definition = resources.get("workload")

        # add input and output size to the benchmark.
        #self.benchmark = benchmark_cls(resources)

        # set seeds
        #self._set_all_seeds()

    def run(self):
        """
        Runs all functions of a Benchmark and records its latencies. Saves the results afterwards
        in a predefined folder.

        Raises:
            ValueError: _description_
        """
        benchmark_results = None


        
        self.benchmark.deploy 
        self.benchmark.setup
        self.benchmark.run
        


