## Accessing Jaeger Tracing

**Local Setup:** Jaeger is deployed automatically and configured for both control and data plane tracing.

1. **Control plane tracing** (kuadrant-operator):
   - OTEL env vars automatically configured when `INSTALL_TRACING=true` (default)
   - Operator sends traces to `jaeger-collector.tools.svc.cluster.local:4317`
   - Trace reconciliation loops, policy processing, and webhook calls

2. **Data plane tracing** (gateway/envoy):
   - Configured in Kuadrant CR: `spec.observability.tracing.defaultEndpoint`
   - Gateway sends request traces to same Jaeger collector
   - Trace HTTP requests, rate limit checks, and auth decisions

3. **Access Jaeger UI:**
   ```bash
   kubectl port-forward -n tools svc/jaeger-query 16686:80
   # Open http://localhost:16686
   ```

4. **Run tracing tests:**
   ```bash
   # Control plane tracing tests (40 tests)
   make testsuite/tests/singlecluster/tracing/control_plane/

   # Data plane tracing tests (10 tests)
   make testsuite/tests/singlecluster/tracing/data_plane_tracing/
   ```

**Disable tracing:**
```bash
INSTALL_TRACING=false make local-setup
```

**View traces:**
- Service: `kuadrant-operator` for control plane traces
- Service: Gateway name for data plane traces
- Filter by operation, tags, or duration
