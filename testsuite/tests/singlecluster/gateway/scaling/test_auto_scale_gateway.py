"""
This module contains tests for auto-scaling the gateway deployment with an HPA watching the cpu usage
"""

import time

import pytest

from testsuite.kuadrant.policy.authorization import JsonResponse, ValueFrom
from testsuite.kubernetes import Selector
from testsuite.kubernetes.deployment import Deployment, VolumeMount, ConfigMapVolume, SecretVolume, EmptyDirVolume
from testsuite.kubernetes.horizontal_pod_autoscaler import HorizontalPodAutoscaler
from testsuite.kubernetes.monitoring import MetricsEndpoint, Relabeling
from testsuite.kubernetes.monitoring.pod_monitor import PodMonitor
from testsuite.kubernetes.monitoring.service_monitor import ServiceMonitor
from testsuite.kubernetes.service_account import ServiceAccount
from testsuite.kubernetes.cluster_role import ClusterRole, Rule
from testsuite.kubernetes.cluster_role import ClusterRoleBinding
from testsuite.kubernetes.role_binding import RoleBinding
from testsuite.kubernetes.service import Service, ServicePort
from testsuite.kubernetes.api_service import APIService
from testsuite.kubernetes.config_map import ConfigMap

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def custom_metrics_sa(cluster, blame, module_label):
    """Creates the ServiceAccount for custom metrics"""
    return ServiceAccount.create_instance(cluster, blame("custom-metrics-apiserver"), labels={"app": module_label})


@pytest.fixture(scope="module")
def custom_metrics_server_role(cluster, blame, module_label):
    """Creates the ClusterRole for custom metrics server resources"""
    rules = [Rule(verbs=["*"], resources=["*"], apiGroups=["custom.metrics.k8s.io"])]
    return ClusterRole.create_instance(
        cluster, blame("custom-metrics-server-resources"), rules, labels={"app": module_label}
    )


@pytest.fixture(scope="module")
def custom_metrics_reader_role(cluster, blame, module_label):
    """Creates the ClusterRole for custom metrics resource reader"""
    rules = [Rule(verbs=["get", "list"], resources=["namespaces", "pods", "services"], apiGroups=[""])]
    return ClusterRole.create_instance(
        cluster, blame("custom-metrics-resource-reader"), rules, labels={"app": module_label}
    )


@pytest.fixture(scope="module")
def rbac_bindings(
    cluster, blame, custom_metrics_sa, custom_metrics_server_role, custom_metrics_reader_role, module_label
):
    """Creates all the RBAC bindings needed for the prometheus adapter"""
    # Create auth delegator binding
    auth_delegator = ClusterRoleBinding.create_instance(
        cluster,
        blame("custom-metrics-auth-delegator"),
        "system:auth-delegator",
        [custom_metrics_sa.name()],
        labels={"app": module_label},
    )

    # Create auth reader binding
    auth_reader = RoleBinding.create_instance(
        cluster.change_project("kube-system"),
        blame("custom-metrics-auth-reader"),
        "extension-apiserver-authentication-reader",
        [custom_metrics_sa.name()],
        labels={"app": module_label},
    )

    # Create resource reader binding
    resource_reader = ClusterRoleBinding.create_instance(
        cluster,
        blame("custom-metrics-resource-reader"),
        custom_metrics_reader_role.name(),
        [custom_metrics_sa.name()],
        labels={"app": module_label},
    )

    # Create HPA controller binding
    hpa_binding = ClusterRoleBinding.create_instance(
        cluster,
        blame("hpa-controller-custom-metrics"),
        custom_metrics_server_role.name(),
        ["horizontal-pod-autoscaler"],
        labels={"app": module_label},
    )

    # Create cluster monitoring view binding
    monitoring_view = ClusterRoleBinding.create_instance(
        cluster,
        blame("custom-metrics-apiserver-cluster-monitoring-view"),
        "cluster-monitoring-view",
        [custom_metrics_sa.name()],
        labels={"app": module_label},
    )

    return auth_delegator, auth_reader, resource_reader, hpa_binding, monitoring_view


@pytest.fixture(scope="module")
def setup_rbac(request, custom_metrics_sa, custom_metrics_server_role, custom_metrics_reader_role, rbac_bindings):
    """Commits all RBAC resources needed for the prometheus adapter"""
    components = [custom_metrics_server_role, custom_metrics_reader_role, custom_metrics_sa, *rbac_bindings]

    # Add finalizers for all components
    for component in components:
        request.addfinalizer(component.delete)

    # Commit roles first
    for role in [custom_metrics_server_role, custom_metrics_reader_role]:
        role.commit()
        if hasattr(role, "wait_for_ready"):
            role.wait_for_ready()

    # Commit service account
    custom_metrics_sa.commit()
    if hasattr(custom_metrics_sa, "wait_for_ready"):
        custom_metrics_sa.wait_for_ready()

    # Commit all bindings
    for binding in rbac_bindings:
        binding.commit()
        if hasattr(binding, "wait_for_ready"):
            binding.wait_for_ready()

    return components


@pytest.fixture(scope="module")
def api_key(create_api_key, blame):
    """Creates API key Secret for a user"""
    annotations = {"kuadrant.io/groups": "users", "secret.kuadrant.io/user-id": "load-generator"}
    secret = create_api_key("api-key", blame("user"), "api_key_value", annotations=annotations)
    return secret


@pytest.fixture(scope="module")
def authorization(authorization, api_key):
    """Create an AuthPolicy with authentication for a simple user with same target as one default"""
    authorization.identity.add_api_key("api-key", selector=api_key.selector)
    authorization.responses.add_success_dynamic(
        "identity",
        JsonResponse({"userid": ValueFrom("{auth.identity.metadata.annotations.secret\\.kuadrant\\.io/user-id}")}),
    )
    return authorization


@pytest.fixture(scope="module")
def service_monitor(blame, cluster):
    """Create a service monitor for the gateway deployment"""
    label = {"istio": "pilot"}
    endpoints = [MetricsEndpoint("/metrics", "http-monitoring")]
    return ServiceMonitor.create_instance(
        cluster.change_project("istio-system"), blame("sm"), endpoints, match_labels=label
    )


@pytest.fixture(scope="module")
def pod_monitor(blame, cluster, module_label):
    """Create a pod monitor for the gateway deployment"""
    relabelings = [
        Relabeling(
            action="keep",
            regex="istio-proxy",
            sourceLabels=["__meta_kubernetes_pod_container_name"],
        ),
        Relabeling(
            action="keep",
            sourceLabels=["__meta_kubernetes_pod_annotationpresent_prometheus_io_scrape"],
        ),
        Relabeling(
            action="replace",
            regex="(\\d+);(([A-Fa-f0-9]{1,4}::?){1,7}[A-Fa-f0-9]{1,4})",
            replacement="[$2]:$1",
            sourceLabels=["__meta_kubernetes_pod_annotation_prometheus_io_port", "__meta_kubernetes_pod_ip"],
            targetLabel="__address__",
        ),
        Relabeling(
            action="replace",
            regex="(\\d+);((([0-9]+?)(\\.|$)){4})",
            replacement="$2:$1",
            sourceLabels=["__meta_kubernetes_pod_annotation_prometheus_io_port", "__meta_kubernetes_pod_ip"],
            targetLabel="__address__",
        ),
        Relabeling(
            action="replace",
            regex="(.+);.*|.*;(.+)",
            replacement="${1}${2}",
            separator=";",
            sourceLabels=["__meta_kubernetes_pod_label_app_kubernetes_io_name", "__meta_kubernetes_pod_label_app"],
            targetLabel="app",
        ),
        Relabeling(
            action="replace",
            regex="(.+);.*|.*;(.+)",
            replacement="${1}${2}",
            separator=";",
            sourceLabels=[
                "__meta_kubernetes_pod_label_app_kubernetes_io_version",
                "__meta_kubernetes_pod_label_version",
            ],
            targetLabel="version",
        ),
        Relabeling(action="replace", replacement="the-mesh-identification-string", targetLabel="mesh_id"),
    ]
    endpoints = [MetricsEndpoint("/stats/prometheus", None, relabelings=relabelings)]
    return PodMonitor.create_instance(
        cluster.change_project("kuadrant"), blame("pm"), endpoints, match_labels={"app": module_label}
    )


@pytest.fixture(scope="module")
def hpa(cluster, blame, gateway, module_label):
    """Add hpa to the gateway deployment"""
    hpa = HorizontalPodAutoscaler.create_instance(
        cluster,
        blame("hpa"),
        gateway.deployment,
        [
            {
                "type": "Pods",
                "pods": {
                    "metric": {"name": "istio_requests_per_second"},
                    "target": {"type": "Value", "averageValue": "500m"},
                },
            }
        ],
        labels={"app": module_label},
        min_replicas=1,
        max_replicas=5,
    )
    return hpa


@pytest.fixture(scope="module")
def load_generator(cluster, blame, api_key, client):
    """Creates a deployment that will generate load on the gateway"""
    labels = {"app": "load-generator"}
    load_generator = Deployment.create_instance(
        cluster,
        blame("load-generator"),
        container_name="siege",
        image="quay.io/acristur/siege:4.1.7",
        selector=Selector(matchLabels=labels),
        labels=labels,
        ports={"http": 8080},  # this is not doing anything, but necessary for the constructor
        command_args=[
            "-H",
            f"Authorization: APIKEY {str(api_key)}",
            "-c",  # concurrent users
            "10",
            "-d",  # delay between requests (1 = 1 second)
            "2",  # 2 second delay = 0.5 requests per second per user
            "-t",  # time to run
            "10m",  # run for 10 minutes to allow HPA to stabilize
            "-b",  # no delay between starting users
            "--no-parser",  # don't parse HTML
            f"{client.base_url.scheme}://{client.base_url.host}/get",  # specific endpoint
        ],
    )
    return load_generator


@pytest.fixture(scope="module")
def prometheus_adapter_service(blame, cluster, module_label):
    """Creates the Service for prometheus adapter"""
    ports = [ServicePort("https", 443, targetPort=6443)]
    return Service.create_instance(
        cluster,
        blame("prometheus-adapter"),
        selector={"app": "prometheus-adapter"},
        ports=ports,
        labels={"name": "prometheus-adapter", "app": module_label},
        annotations={"service.beta.openshift.io/serving-cert-secret-name": "prometheus-adapter-tls"},
    )


@pytest.fixture(scope="module")
def prometheus_adapter_api_service(cluster, prometheus_adapter_service, module_label):
    """Creates the APIService for prometheus adapter"""
    return APIService.create_instance(
        cluster,
        "v1beta2.custom.metrics.k8s.io",
        prometheus_adapter_service.name(),
        "kuadrant",
        "custom.metrics.k8s.io",
        "v1beta2",
        labels={"app": module_label},
        insecure_skip_tls_verify=True,
    )


@pytest.fixture(scope="module")
def adapter_config(blame, cluster, module_label):
    """Creates the ConfigMap for prometheus adapter configuration"""
    config = {
        "config.yaml": """rules:
- seriesQuery: 'istio_requests_total{namespace!="",pod!=""}'
  resources:
    overrides:
      namespace: {resource: "namespace"}
      pod: {resource: "pod"}
  name:
    matches: "^(.*)_total"
    as: "${1}_per_second"
  metricsQuery: 'sum(rate(<<.Series>>{<<.LabelMatchers>>}[2m])) by (<<.GroupBy>>)'"""
    }
    return ConfigMap.create_instance(cluster, blame("adapter-config"), config, labels={"app": module_label})


@pytest.fixture(scope="module")
def prometheus_config(blame, cluster, module_label):
    """Creates the ConfigMap for prometheus configuration"""
    config = {
        "prometheus-config.yaml": """apiVersion: v1
clusters:
- cluster:
    server: https://thanos-querier.openshift-monitoring.svc.cluster.local:9091
    insecure-skip-tls-verify: true
  name: prometheus-k8s
contexts:
- context:
    cluster: prometheus-k8s
    user: prometheus-k8s
  name: prometheus-k8s
current-context: prometheus-k8s
kind: Config
preferences: {}
users:
- name: prometheus-k8s
  user:
    tokenFile: /var/run/secrets/kubernetes.io/serviceaccount/token"""
    }
    return ConfigMap.create_instance(
        cluster, blame("prometheus-adapter-prometheus-config"), config, labels={"app": module_label}
    )


@pytest.fixture(scope="module")
def prometheus_adapter_deployment(blame, cluster, custom_metrics_sa, adapter_config, prometheus_config):
    """Creates the Deployment for prometheus adapter"""
    volumes = [
        SecretVolume("prometheus-adapter-tls", "volume-serving-cert"),
        ConfigMapVolume(adapter_config.name(), {"config.yaml": "config.yaml"}, "config"),
        ConfigMapVolume(
            prometheus_config.name(),
            {"prometheus-config.yaml": "prometheus-config.yaml"},
            "prometheus-adapter-prometheus-config",
        ),
        EmptyDirVolume("tmp-vol"),
    ]
    volume_mounts = [
        VolumeMount("/var/run/serving-cert", "volume-serving-cert"),
        VolumeMount("/etc/adapter/", "config"),
        VolumeMount("/etc/prometheus-config", "prometheus-adapter-prometheus-config", readOnly=False),
        VolumeMount("/tmp", "tmp-vol", readOnly=False),
    ]
    deployment = Deployment.create_instance(
        cluster,
        blame("prometheus-adapter"),
        "prometheus-adapter",
        "k8s.gcr.io/prometheus-adapter/prometheus-adapter:v0.12.0",
        {"https": 6443},
        Selector(matchLabels={"app": "prometheus-adapter"}),
        labels={"app": "prometheus-adapter"},
        command_args=[
            "--prometheus-auth-config=/etc/prometheus-config/prometheus-config.yaml",
            "--secure-port=6443",
            "--tls-cert-file=/var/run/serving-cert/tls.crt",
            "--tls-private-key-file=/var/run/serving-cert/tls.key",
            "--prometheus-url=https://thanos-querier.openshift-monitoring.svc.cluster.local:9091/",
            "--metrics-relist-interval=1m",
            "--v=6",
            "--config=/etc/adapter/config.yaml",
        ],
        volumes=volumes,
        volume_mounts=volume_mounts,
    )

    # Set the service account
    deployment.template.serviceAccountName = custom_metrics_sa.name()  # type: ignore

    return deployment


@pytest.fixture(scope="module")
def prometheus_stack(
    request,
    prometheus,
    service_monitor,
    pod_monitor,
    setup_rbac,  # pylint: disable=unused-argument
    prometheus_adapter_service,
    prometheus_adapter_api_service,
    adapter_config,
    prometheus_config,
    prometheus_adapter_deployment,
    hpa,
    load_generator,
):
    """Create and commit the prometheus stack"""
    components = [
        service_monitor,
        pod_monitor,
        prometheus_adapter_service,
        prometheus_adapter_api_service,
        adapter_config,
        prometheus_config,
        prometheus_adapter_deployment,
        hpa,
        load_generator,
    ]

    # Add finalizers for all components
    for component in components:
        request.addfinalizer(component.delete)

    # Commit all components
    for component in components:
        component.commit()
        if hasattr(component, "wait_for_ready"):
            component.wait_for_ready()

    assert prometheus.is_reconciled(service_monitor)
    assert prometheus.is_reconciled(pod_monitor)
    return components


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, rate_limit, dns_policy, tls_policy):
    """Commits all important stuff before tests"""
    for component in [dns_policy, tls_policy, authorization, rate_limit]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()


def test_auto_scale_gateway(gateway, prometheus_stack, client, auth):  # pylint: disable=unused-argument
    """This test asserts that the policies are working as expected and this behavior does not change after scaling"""
    anon_auth_resp = client.get("/get")
    assert anon_auth_resp is not None
    assert anon_auth_resp.status_code == 401

    responses = client.get_many("/get", 5, auth=auth)
    responses.assert_all(status_code=200)

    assert client.get("/get", auth=auth).status_code == 429

    time.sleep(5)  # sleep in order to reset the rate limit policy time limit.

    gateway.deployment.wait_for_replicas(2)

    anon_auth_resp = client.get("/get")
    assert anon_auth_resp is not None
    assert anon_auth_resp.status_code == 401

    responses = client.get_many("/get", 5, auth=auth)
    responses.assert_all(status_code=200)

    assert client.get("/get", auth=auth).status_code == 429
