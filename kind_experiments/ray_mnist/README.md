# ms_project

## Execution 
```bash
kubectl create -k kuberay-manifests/default --validate=false
```


```bash
kubectl apply -f raycluster.yaml
```

```bash
export RAY_ADDRESS="http://127.0.0.1:8265"
```

```bash
kubectl port-forward svc/raycluster-head-svc 8265:8265
```

```bash
ray job submit --working-dir . --runtime-env-json='{"pip": "requirements.txt"}' -- python script.py
```

reqs
kind 1.26
kubernetes 27.2 >
pip install http-client==0.1.22
helm delete kepler -n kepler
python -m ray_cluster.ray_mnist_experiment

## Troubleshooting

redis database
```bash
rm -rf /tmp/ray/session_latest
```