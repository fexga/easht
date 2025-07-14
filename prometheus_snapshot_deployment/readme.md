## usage

copy snapshot

kubectl cp /home/felix/Documents/Studium/Masterarbeit/ms_project/prometheus_snapshots/01JVA1QTNJFK9HG4TXB9Z8HN35/ prometheus-snapshot-64c58f9f7-kjpjh:/prometheus/


kubectl create configmap prometheus-snapshot-config --from-file=prometheus.yml=./prometheus.yaml


kubectl apply -f prometheus-snapshot-pv.yaml


kubectl apply -f prometheus-snapshot-deployment.yaml


port forward

increase(kepler_container_joules_total{container_namespace="default"}[5 m]) / 300 watts