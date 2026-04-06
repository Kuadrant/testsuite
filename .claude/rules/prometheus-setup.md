# Accessing Prometheus

## Auto-Discovery

Prometheus is auto-discovered via the `Exposer.prometheus_client()` method:

- **OpenShift (`OpenShiftExposer`)**: Looks up the `thanos-querier` route in `openshift-monitoring`. No configuration needed.
- **Kind/Kubernetes (`LoadBalancerServiceExposer`)**: Looks up the `prometheus-kube-prometheus-prometheus` LoadBalancer service in the `monitoring` namespace. Works out of the box if `make local-setup` was used.

## Manual Override

Setting `prometheus.url` in `config/settings.local.yaml` overrides all auto-discovery:

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