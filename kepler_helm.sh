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

echo "Adding Kepler Helm repo..."
helm repo add kepler https://sustainable-computing-io.github.io/kepler-helm-chart
helm repo update

echo "Installing Kepler with custom values..."
helm install kepler kepler/kepler \
    --namespace kepler \
    --create-namespace \
    -f kepler-values.yaml

echo "Waiting for Kepler pod to be ready..."
KPLR_POD=$(
    kubectl get pod \
        -l app.kubernetes.io/name=kepler \
        -o jsonpath="{.items[0].metadata.name}" \
        -n kepler
)
echo "Kepler pod: $KPLR_POD"
kubectl wait --for=condition=Ready pod $KPLR_POD --timeout=300s -n kepler

kubectl apply -f kepler-config.yaml

echo "Setup complete!"

# helm delete kepler --namespace kepler