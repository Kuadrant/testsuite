"""Conftest for the auto scale gateway test"""

import pytest
from testsuite.kuadrant.policy import CelPredicate
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit
from testsuite.kubernetes import Selector
from testsuite.kubernetes.api_service import APIService
from testsuite.kubernetes.cluster_role import ClusterRole, ClusterRoleBinding, Rule
from testsuite.kubernetes.config_map import ConfigMap
from testsuite.kubernetes.deployment import ConfigMapVolume, Deployment, EmptyDirVolume, SecretVolume, VolumeMount
from testsuite.kubernetes.monitoring import MetricsEndpoint, Relabeling
from testsuite.kubernetes.monitoring.pod_monitor import PodMonitor
from testsuite.kubernetes.role_binding import RoleBinding
from testsuite.kubernetes.service import Service, ServicePort
from testsuite.kubernetes.service_account import ServiceAccount


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
    return PodMonitor.create_instance(cluster, blame("pm"), endpoints, match_labels={"app": module_label})


@pytest.fixture(scope="module")
def prometheus_adapter_service(testconfig, blame, cluster, module_label):
    """Creates the Service for prometheus adapter"""
    ports = [ServicePort("https", 443, targetPort=6443)]
    return Service.create_instance(
        cluster,
        blame(testconfig["prometheus"]["adapter"]["name"]),
        selector={"app": testconfig["prometheus"]["adapter"]["name"]},
        ports=ports,
        labels={"name": testconfig["prometheus"]["adapter"]["name"]},
        annotations={"service.beta.openshift.io/serving-cert-secret-name": "prometheus-adapter-tls"},
    )


@pytest.fixture(scope="module")
def prometheus_adapter_api_service(testconfig, cluster, prometheus_adapter_service):
    """Creates the APIService for prometheus adapter"""
    return APIService.create_instance(
        cluster,
        "v1beta2.custom.metrics.k8s.io",
        prometheus_adapter_service.name(),
        "custom.metrics.k8s.io",
        "v1beta2",
        labels={"app": testconfig["prometheus"]["adapter"]["name"]},
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
    as: "${1}"
  metricsQuery: 'sum(<<.Series>>{<<.LabelMatchers>>}) by (<<.GroupBy>>)'"""
    }
    return ConfigMap.create_instance(cluster, blame("adapter-config"), config, labels={"app": module_label})


@pytest.fixture(scope="module")
def prometheus_config(prometheus, blame, cluster, module_label):
    """Creates the ConfigMap for prometheus configuration"""
    config = {
        "prometheus-config.yaml": f"""apiVersion: v1
clusters:
- cluster:
    server: {prometheus.service_url}
    insecure-skip-tls-verify: true
  name: prometheus-k8s
contexts:
- context:
    cluster: prometheus-k8s
    user: prometheus-k8s
  name: prometheus-k8s
current-context: prometheus-k8s
kind: Config
preferences: {{}}
users:
- name: prometheus-k8s
  user:
    tokenFile: /var/run/secrets/kubernetes.io/serviceaccount/token"""
    }
    return ConfigMap.create_instance(
        cluster, blame("prometheus-adapter-prometheus-config"), config, labels={"app": module_label}
    )


@pytest.fixture(scope="module")
def prometheus_adapter_deployment(
    testconfig, prometheus, blame, cluster, custom_metrics_sa, adapter_config, prometheus_config
):
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
        testconfig["prometheus"]["adapter"]["name"],
        testconfig["prometheus"]["adapter"]["image"],
        {"https": 6443},
        Selector(matchLabels={"app": testconfig["prometheus"]["adapter"]["name"]}),
        labels={"app": testconfig["prometheus"]["adapter"]["name"]},
        command_args=[
            "--prometheus-auth-config=/etc/prometheus-config/prometheus-config.yaml",
            "--secure-port=6443",
            "--tls-cert-file=/var/run/serving-cert/tls.crt",
            "--tls-private-key-file=/var/run/serving-cert/tls.key",
            f"--prometheus-url={prometheus.service_url}",
            "--config=/etc/adapter/config.yaml",
        ],
        volumes=volumes,
        volume_mounts=volume_mounts,
    )

    # Set the service account
    deployment.template.serviceAccountName = custom_metrics_sa.name()  # type: ignore

    return deployment


@pytest.fixture(scope="module")
def authorization(authorization):
    """Create an AuthPolicy with authentication for a simple user with same target as one default"""
    authorization.metadata.add_user_info("user-info", "default")
    return authorization


@pytest.fixture(scope="module")
def rate_limit(blame, gateway, module_label, cluster):
    """Add limit to the policy"""
    policy = RateLimitPolicy.create_instance(cluster, blame("rlp"), gateway, labels={"app": module_label})
    policy.add_limit("basic", [Limit(10, "5s")], when=[CelPredicate("auth.metadata.userinfo.email != ''")])
    return policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, rate_limit, dns_policy, tls_policy):
    """Commits all important stuff before tests"""
    for component in [dns_policy, tls_policy, authorization, rate_limit]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()
