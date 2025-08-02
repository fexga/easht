## usage

copy snapshot


copy directly into promehteus pod and restart
kubectl exec prometheus-snapshot-5b67789c8b-8sn9d -- mkdir -p /prometheus/20250728T113433Z-7e93cc333101a050

kubectl cp /home/felix/Documents/Studium/Masterarbeit/ms_project/kind_experiments/optuna_mnist/prometheus_snapshots/20250728T113433Z-7e93cc333101a050 prometheus-snapshot-5b67789c8b-8sn9d:/prometheus/snapshots/20250728T113433Z-7e93cc333101a050



kubectl create configmap prometheus-snapshot-config --from-file=prometheus.yml=./prometheus.yaml


kubectl apply -f prometheus-snapshot-pv.yaml


kubectl apply -f prometheus-snapshot-deployment.yaml


port forward

increase(kepler_container_joules_total{container_namespace="default"}[5 m]) / 300 watts