#!/bin/bash
set -ex  # Show commands and exit on error

echo "Adding Kepler Helm repo..."
helm repo add kepler https://sustainable-computing-io.github.io/kepler-helm-chart
helm repo update

echo "Installing Kepler with custom values..."
helm install kepler kepler/kepler \
    --namespace st-felixgraf-kepler \
    #--set extraEnvVars.POWER_EXPORTER=powertop
    #--set serviceMonitor.enabled=true \
    #--set serviceMonitor.labels.release=prometheus \

# service monitor seperate deployment


#echo "Waiting for Kepler pod to be ready..."
#KPLR_POD=$(
#    kubectl get pod \
#        -l app.kubernetes.io/name=kepler \
#        -o jsonpath="{.items[0].metadata.name}" \
#        -n kepler
#)
#echo "Kepler pod: $KPLR_POD"
#kubectl wait --for=condition=Ready pod $KPLR_POD --timeout=300s -n kepler

#kubectl apply -f kepler-config.yaml

echo "Setup complete!"

# helm delete kepler --namespace kepler