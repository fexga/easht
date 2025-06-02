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

## Troubleshooting

redis database
```bash
rm -rf /tmp/ray/session_latest
```