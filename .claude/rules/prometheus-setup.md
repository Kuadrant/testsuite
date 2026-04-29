# Accessing Prometheus

## Auto-Discovery

Prometheus URL is auto-discovered via `DefaultValueValidator` in `testsuite/config/__init__.py`. It uses `fetch_service_ip` to look up the `prometheus-kube-prometheus-prometheus` LoadBalancer service in the `monitoring` namespace (configured in `config/settings.yaml` under `monitoring.project`).

This works on both Kind (after `make local-setup`) and any cluster where Prometheus is exposed as a LoadBalancer service.

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