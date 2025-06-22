#!/bin/bash
set -ex  # Show commands and exit on error

echo "Adding Prometheus Helm repo..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

echo "Installing Prometheus with custom values..."
helm install prometheus prometheus-community/kube-prometheus-stack \
    --version 72.3.0 \
    --set server.image.tag=v3.3.1 \
    --namespace st-felixgraf-monitoring \
    -f prometheus-values.yaml \
    --wait

echo "Deploying cAdvisor..."
kubectl apply -f cadvisor.yaml

echo "Setup complete!"