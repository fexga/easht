# Easht - An **E**valuation **A**pproach for **S**ustainabile **H**yperparameter **T**uning##

EASHT provides a framework to measure energy consumption and CO2 emissions of distributed Hyperparameter Optimization in Kubernetes.
This repo is part of the master's thesis "Measuring the Sustainability of Hyperparamater Optimization in the Cloud" submitted in August 2025 at Technische Universität Berlin.

## Approach and Architecture

Conducted HPO experiments are structured and measured in phases using the following step model:

![stepmodel](docs/stepmodel.pdf).

EASHT is composed of the following components: 
- Kepler: responsible for measuring energy consumption in the Kubernetes cluster
- cAdvisor: records network traffic
- Prometheus: scrapes collected metrics from Kepler and cAdvisor
- Experiment Runner: wraps HPO experiments into the aforementioned step model
- Metric Collector: queries metrics from Prometheus and calculates sustainability related metrics
- Configuration file: defines a set of relevant parameters to configure distributed HPO 

After a successful experiment, EASHT produces two files:
- a structured result file, containing calculated metrics for each phase of the step model and the overall process
- a Prometheus snapshot for validating the produced metrics of EASHT

The following diagram illustrates the architecture of easht:

![architecture](docs/architecture.pdf).

## Sample Experiment
This repository contains two sample HPO experiments using Optuna and Ray Tune, which can be run locally and showcase the functionalities of EASHT.

### Prerequisites

- Ubuntu >= 22.04
- Python >= 3.9
- pip >= 21.3
- Docker >= 20.10
- Helm >= 3.0
- kubectl >= 1.25 

### Installation

1. Clone the repository with `git clone <url>`
2. Create a Python environment with `python -m venv .venv`
3. Activate your environment with `source .venv/bin/activate`
4. Upgrade pip with `pip install pip --upgrade`
5. Install required packages with `pip install -e .`

### Install kind

Before installing the monitoring components and starting the sample experiments, a kind cluster be created first.

To install kind, instructions cam be followed [here](https://kind.sigs.k8s.io/docs/user/quick-start/#installation).

### Monitoring components

To install the monitoring components Kepler, cAdvisor and Prometheus required by EASHT, the following commands must be run in order from the root directory of this project:

1. `bash monitoring/prometheus/prometheus_helm.sh`
2. `bash monitoring/kepler/kepler_helm.sh`

#### Ray Tune

To run the Ray Tune experiment, the following command must be executed from the root of this project:

- `python -m kind_experiments.ray_mnist.ray_mnist_experiment`

The result JSON will be stored in the folder `kind_experiments/ray_mnist/results`.
The Prometheus snapshot will be stored in the folder `kind_experiments/ray_mnist/prometheus_snapshots`.


#### Optuna

To run the Optuna experiment, the following command must be executed from the root of this project:

- `python -m kind_experiments.optuna_mnist.optuna_mnist_experiment`

The result JSON will be stored in the folder `kind_experiments/optuna_mnist/results`.
The Prometheus snapshot will be stored in the folder `kind_experiments/optuna_mnist/prometheus_snapshots`.
