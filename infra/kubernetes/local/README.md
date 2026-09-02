# SignalTrade local Kubernetes infrastructure

This directory contains only the local infrastructure layer. Application
Deployments are intentionally excluded.

```sh
kind create cluster --name signaltrade-local --config infra/kubernetes/local/kind-config.yaml
kubectl apply -f infra/kubernetes/local/namespace.yaml
kubectl apply -k infra/kubernetes/local
kubectl wait --for=condition=Ready pod --all -n signaltrade --timeout=180s
kubectl apply -f infra/kubernetes/local/tests/dns-check.yaml
kubectl logs -n signaltrade infrastructure-dns-check
```

The checked-in Secret values are local-development credentials only. They must
not be reused outside the `signaltrade-local` kind cluster. A later application
deployment can consume `application-runtime-config` and
`application-runtime-secret` without changing the application environment
variable names.

PostgreSQL uses kind's default dynamic StorageClass and a 2 GiB PVC. Redis and
LocalStack are intentionally ephemeral because Redis stores short-lived
security state and LocalStack recreates queues from the mounted init script.
