# ms_project

## Execution 
```bash
kubectl apply -f rayoperator.yaml
```

```bash
kubectl apply -f crd.yaml
```

```bash
kubectl apply -f raycluster.yaml
```

```bash
kubectl port-forward service/raycluster-complete-head-svc 8265:8265
```

```bash
export RAY_ADDRESS="http://127.0.0.1:8265"
```

```bash
ray start --head
```

```bash
ray job submit --working-dir ./ -- python script.py
```

## Troubleshooting

redis database
```bash
rm -rf /tmp/ray/session_latest
```
