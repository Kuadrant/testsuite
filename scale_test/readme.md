# Control Plane Scale Test

Control Plane scale testing via kube-burner utility. It creates `NUM_GWS` Gateways each having `NUM_LISTENERS` listeners configured. For each Gateway one policy of each Kind (AuthPolicy, DNSPolicy, RateLimitPolicy, TLSPolicy) is created. For each listener one AuthPolicy and one RateLimitPolicy is created.

## Prerequisites

This test assumes that Kuadrant together with all the dependencies (Gateway API, Istio, Certificate Manager etc) are installed. A ClusterIssuer (self-signed one is enough) is expected to exist too. Also make sure to port-forward Prometheus instance so that it is possible for kube-burner to query it.

The following environment variables will need to be set to run the tests:

```
export KUADRANT_AWS_SECRET_ACCESS_KEY=[key]
export KUADRANT_AWS_ACCESS_KEY_ID=[id]
export KUADRANT_ZONE_ROOT_DOMAIN=[domain]
export KUADRANT_AWS_REGION=[region]
export PROMETHEUS_URL=http://127.0.0.1:9090
export PROMETHEUS_TOKEN=""
export OS_INDEXING=true   # if sending metrics to opensearch/elasticsearch
export ES_SERVER=https://[user]:[password]@[host]:[port]

export NUM_GWS=1
export NUM_LISTENERS=1
```

If you want to disable indexing you need to explicitly set related environment variables to an empty string:
```
export OS_INDEXING= # to disable indexing
export ES_SERVER= # to disable indexing
```

## Execution

`kube-burner init -c ./config.yaml --timeout 5m --uuid scale-test-$(openssl rand -hex 3)`

Don't forget to increase the timeout if larger number of CRs are to be created.

## Setting up a local cluster for execution

Follow the instructions in the Prerequisites section.

Clone the [kuadrant-operator](https://github.com/Kuadrant/kuadrant-operator) repo:

```bash
CONTAINER_ENGINE=podman make local-setup
```

Deploy the observability stack, as per the instructions in https://github.com/Kuadrant/kuadrant-operator/blob/main/config/observability/README.md

Create the Kuadrant resource:

```bash
kubectl create -f ./config/samples/kuadrant_v1beta1_kuadrant.yaml -n kuadrant-system
```

Create a ClusterIssuer:

```bash
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned-issuer
spec:
  selfSigned: {}
EOF
```

Port forward to Prometheus:

```bash
kubectl -n monitoring port-forward svc/prometheus-k8s 9090:9090
```

Run kube-burner (described in more detail above):

```bash
kube-burner init -c ./config.yaml --timeout 5m
```

## Adding new metrics

kube-burner gathers metrics from a prometheus endpoint after each job has finished.
The list of metrics to gather is configured in ./metrics.yaml
All gathered metrics are then sent on to an indexer, such as elasticsearch.
Here's an example of a metric:

```yaml
- query: sum(container_memory_usage_bytes{container="",namespace=~"kuadrant-system|istio-system|gateway-system|scale-test-.*"}) by(namespace)
  metricName: namespaceMemory
```

The `query` is a promql query that calculates the memory used by a specific set of namespaces.
The `metricName` is the name to associate with the query and response when sending the metrics to an indexer.

An advantage of sending the metrics on to an indexer is that they get decorated with test specific labels, such as the job uuid and name.
The indexer also serves as long term storage of aggregated test data.
Once the data from multiple test runs have been indexed, it can be queried via the indexer API (e.g. elasticsearch API)
and visualised using tools like Grafana.

Before adding a new metric to the ./metrics.yaml file, it can be helpful to explore and tweak the promql query, and test it in a fast feedback loop.
For example, you could run a test once, then use the prometheus UI to visualise & tweak a query until you are happy that it captures the right data from that test run.
Once you are happy with the query, add it to ./metrics.yaml and execute the test again.
To complete the addition of the metric, you should make use of it in a dashboard.

## Updating Dashboards

Dashboards are created in and exported from Grafana.
The main dashboard json is in ./dashboard.json.
The easiest way to import this dashboard is from the Grafana UI.
If you make changes to a dashboard and want to update it in this repo, make sure to save the dashboard in Grafana, then export it using 'Share' > 'Export' > 'View JSON' in the Grafana UI.

## Elasticsearch queries in Grafana

There are 2 main types of queries you can use against elasticsearch.
You can query the elasticsearch API directly.
Here's an example of a simple query to match everything:

```
GET /_search
{
    "query": {
        "match_all": {}
    }
}
```

and a filtered example:

```
{
  "query": {
    "bool": {
      "must": [
        { "term": { "metricName.keyword": "namespaceMemory" } },
        { "term": { "jobName.keyword": "scale-test-main" } },
        { "term": { "uuid.keyword": "$uuid" } }
      ]
    }
  }
}
```

See https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl.html for more details on the Elasticsearch query language.

However, for most, if not all queries, they'll be using the Lucene syntax from Grafana.
This is like an abstraction on the elasticsearch API to make it easier to construct queries.
Here's a simple query that returns all the jobSummary data that kube-burner pushes to the indexer:

```
metricName: "jobSummary"
```

The response will contain fields and values like the UUID, job name, qps, burst, and start & end time.

Data can be filtered using Grafana template variables. This example filters by the uuid template variable:

```
uuid.keyword: $uuid AND metricName: "jobSummary"
```

You can also filter by a specfic job name. Here's a query that fetches memory usage by namespace, for the scale-test-main job:

```
uuid.keyword: $uuid AND metricName: "namespaceMemory" AND jobName: "scale-test-main"
```

See https://grafana.com/docs/grafana/latest/datasources/elasticsearch/query-editor/ for more details on querying Elasticsearch in Grafana.

As the metrics being sent to the indexer are snapshots of queries, it usually doesn't make sense to visualise the metrics in a time series manner.
Showing the results in a Stat panel or Table tend to work best.
If using a Stat panel, the 'Metrics' query type works well in Grafana.
For a Table panel, the 'Raw Data' query type works well.

To show the data in a meaningful way, 'Transforms' are helpful.
Some common transforms are:

* "Organize fields by name" (to show/hide/rename fields in a table)
* "Group by" (to force grouping by a field, such as namespace, and only show/calculate the *Last* value in the query)
* "Sort by"

Inspecting some of the existing panels in the Kuadrant dashboard and kube-burner dashboards at https://github.com/kube-burner/kube-burner/tree/main/examples/grafana-dashboards can give inspiration as well.
