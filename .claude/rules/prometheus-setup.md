# Accessing Prometheus

## Auto-Discovery

Prometheus URL is auto-discovered via `DefaultValueValidator` in `testsuite/config/__init__.py`, which calls `fetch_prometheus_url()` from `testsuite/config/tools.py`.

The discovery tries two approaches in order:

1. **LoadBalancer service** (Kind / non-OpenShift): Looks up the service specified by `prometheus.service` in the `prometheus.project` namespace and returns its external LoadBalancer IP.
2. **OpenShift route**: Checks `cluster-monitoring-config` ConfigMap for `enableUserWorkload`, then discovers the thanos-querier route URL.

The `prometheus.project` and `prometheus.service` settings (defined in `config/settings.yaml`) control which namespace and service name to look up:
- **Kind default**: `project: "monitoring"`, `service: "prometheus-kube-prometheus-prometheus"`
- **OpenShift default**: `project: "openshift-monitoring"`, `service: "thanos-querier"`

## Manual Override

Setting `prometheus.url` in `config/settings.local.yaml` overrides auto-discovery:

```yaml
default:
  prometheus:
    url: "http://172.18.255.200:9090"
```

To find the Kind LoadBalancer URL manually:

```bash
make get-prometheus-url
```

## Running Observability Tests

```bash
make observability
```