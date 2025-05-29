# ms_project

## Execution 
```bash
kubectl create -k kuberay-manifests/default --validate=false
```


```bash
kubectl create configmap ray-script --from-file=script.py
```

```bash
kubectl apply -f ray-job.pytorch-mnist.yaml
```

## Troubleshooting

redis database
```bash
rm -rf /tmp/ray/session_latest
```
