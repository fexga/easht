#!/bin/bash
set -ex  # Show commands and exit on error

echo "Adding Prometheus Helm repo..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

echo "Installing Prometheus with custom values..."
helm install prometheus prometheus-community/kube-prometheus-stack \
    --namespace monitoring \
    --create-namespace \
    -f prometheus-values.yaml \
    --wait

helm upgrade prometheus prometheus-community/kube-prometheus-stack \
    --namespace monitoring \
    -f prometheus-values.yaml \
    --wait

echo "Setup complete!"