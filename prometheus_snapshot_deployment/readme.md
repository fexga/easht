## usage

copy snapshot


copy directly into promehteus pod and restart




kubectl create configmap prometheus-snapshot-config --from-file=prometheus.yml=./prometheus.yaml


kubectl apply -f prometheus-snapshot-pv.yaml


kubectl apply -f prometheus-snapshot-deployment.yaml


port forward

increase(kepler_container_joules_total{container_namespace="default"}[5 m]) / 300 watts