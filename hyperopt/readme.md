kubectl apply -k "github.com/kubeflow/katib.git/manifests/v1beta1/installs/katib-standalone?ref=v0.17.0"

docker build -t keras-hpo:latest .

kubectl apply -f katib.yaml

kubectl delete experiment keras-hpo -n kubeflow

kubectl get experiment -n kubeflow

kubectl describe experiment keras-hpo -n kubeflow