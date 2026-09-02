# Local application runtimes

The application image is shared by every runtime and loaded into kind:

```sh
docker build -t signaltrade-backend:local backend
kind load docker-image signaltrade-backend:local --name signaltrade-local
```

Run the database migration before deploying application runtimes:

```sh
kubectl apply -k infra/kubernetes/local
kubectl delete job database-migration -n signaltrade --ignore-not-found
kubectl apply -k infra/kubernetes/local/application/migration
kubectl wait -n signaltrade --for=condition=complete job/database-migration --timeout=300s
kubectl apply -k infra/kubernetes/local/application/runtimes
```

API Services are internal ClusterIP Services. Workers intentionally have no
Service. No application container runs Alembic during startup.

Install the plain-manifest ingress-nginx controller before applying the
application runtimes:

```sh
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.15.1/deploy/static/provider/baremetal/deploy.yaml
kubectl wait -n ingress-nginx --for=condition=Available deployment/ingress-nginx-controller --timeout=300s
kubectl apply -k infra/kubernetes/local/ingress
```

`signaltrade.local` routes only to the transitional `backend` facade. Domain
APIs remain ClusterIP-only. A cluster recreated with `kind-config.yaml` exposes
the ingress NodePort on `localhost:8080`; for the existing cluster use a local
port-forward to the ingress controller.

API pods and the three metric-serving workers carry Prometheus pod-discovery
annotations. `notification-worker` and `outbox-publisher` currently do not
open metric endpoints and are deliberately not advertised as scrape targets.

Local Telegram credentials are never committed to Kubernetes YAML. Load only
the allowlisted Telegram values from the existing root `.env`, then restart the
two consumers of those settings:

```sh
infra/kubernetes/local/load-local-secrets.sh .env
```

The helper deliberately does not copy Compose `DATABASE_URL`, JWT secrets or
encryption keys into kind.
