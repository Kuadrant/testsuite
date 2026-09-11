"""Helper functions for Kubernetes resource collection, filtering, and YAML output."""

import copy
import logging
import os
from pathlib import Path

import yaml
from openshift_client import invoke, OpenShiftPythonException

logger = logging.getLogger(__name__)


def output_dir() -> Path:
    """Directory for collected YAML files.

    Uses $WORKSPACE when set (Tekton shared workspace), otherwise the current directory.
    """
    return Path(os.environ.get("WORKSPACE", ".")) / "debug-resources"


EXCLUDED_TYPES = frozenset(
    {
        "events",
        "events.events.k8s.io",
        "endpoints",
        "endpointslices.discovery.k8s.io",
        "leases.coordination.k8s.io",
        "controllerrevisions.apps",
        "replicasets.apps",
        "pods.metrics.k8s.io",
    }
)

NON_APPLYABLE_KINDS = frozenset({"Pod", "ReplicaSet", "Endpoints", "EndpointSlice"})

METADATA_NOISE = frozenset({"managedFields"})

ANNOTATION_NOISE = frozenset({"kubectl.kubernetes.io/last-applied-configuration"})

SERVER_ASSIGNED_METADATA = frozenset(
    {"uid", "resourceVersion", "generation", "creationTimestamp", "ownerReferences", "finalizers"}
)

COLLECTION_ERRORS = (OpenShiftPythonException, yaml.YAMLError, OSError, KeyError, RuntimeError)

MAX_DATA_VALUE_LEN = 64

# Node ids already collected, to skip reruns of the same test.
collected_nodes: set[str] = set()


def discover_resource_types() -> list[str]:
    """Discover all namespaced resource types available in the cluster."""
    result = invoke("api-resources", ["--namespaced=true", "--verbs=list", "-o", "name"])
    if result.status() != 0:
        return []
    types = result.out().strip().split("\n")
    return [t.strip() for t in types if t.strip() and t.strip() not in EXCLUDED_TYPES]


def matches_metadata(resource, base_pattern) -> bool:
    """Check if base_pattern appears in resource name or label values."""
    metadata = resource.get("metadata", {})
    if base_pattern in metadata.get("name", ""):
        return True
    return any(base_pattern in str(v) for v in metadata.get("labels", {}).values())


def collect_matching(project, base_pattern, resource_types) -> list[dict]:
    """Fetch all resources of the given types and return raw dicts matching base_pattern."""
    result = invoke("get", [",".join(resource_types), "--ignore-not-found", "-n", project, "-o", "yaml"])
    if result.status() != 0:
        raise RuntimeError(f"Resource query failed: {result.err()}")

    out = result.out().strip()
    if not out:
        return []
    data = yaml.safe_load(out)
    if not data:
        return []
    items = data.get("items", [data])
    return [item for item in items if matches_metadata(item, base_pattern)]


def is_applyable(resource) -> bool:
    """Whether a resource belongs in the apply-able file.

    Controller-managed resources (those with ownerReferences, e.g. the Istio
    Deployment/Service/ServiceAccount generated for a Gateway) and non-applyable
    kinds (Pods, ReplicaSets) are recreated by their controllers, so they are
    excluded - only resources a user would recreate directly are kept. Using
    ownerReferences is more reliable than labels, which controllers often copy
    from the parent resource onto their generated children.
    """
    if resource.get("kind") in NON_APPLYABLE_KINDS:
        return False
    return not resource.get("metadata", {}).get("ownerReferences")


def truncate_data(resource) -> None:
    """Truncate certificate/key payloads; keep config intact for reproducibility."""
    kind = resource.get("kind")
    if kind not in ("Secret", "ConfigMap"):
        return
    for field in ("data", "stringData"):
        data = resource.get(field)
        if not isinstance(data, dict):
            continue
        for key, value in data.items():
            if not isinstance(value, str):
                continue
            if "BEGIN" in value or (kind == "Secret" and len(value) > MAX_DATA_VALUE_LEN):
                data[key] = f"<stripped: {len(value)} chars>"


def strip_cluster_assigned(resource) -> None:
    """Strip cluster-assigned Service fields (clusterIP, nodePort, LB annotations)."""
    if resource.get("kind") != "Service":
        return
    spec = resource.get("spec")
    if isinstance(spec, dict):
        for key in ("clusterIP", "clusterIPs", "healthCheckNodePort"):
            spec.pop(key, None)
        for port in spec.get("ports", []):
            if isinstance(port, dict):
                port.pop("nodePort", None)
    annotations = resource.get("metadata", {}).get("annotations")
    if isinstance(annotations, dict):
        for key in [k for k in annotations if k.startswith("loadbalancer.")]:
            annotations.pop(key, None)


def strip_full(resource) -> dict:
    """Full view: drop managedFields, keep status and cluster metadata."""
    resource = copy.deepcopy(resource)
    metadata = resource.get("metadata")
    if isinstance(metadata, dict):
        for key in METADATA_NOISE:
            metadata.pop(key, None)
        annotations = metadata.get("annotations")
        if isinstance(annotations, dict):
            for key in ANNOTATION_NOISE:
                annotations.pop(key, None)
            if not annotations:
                metadata.pop("annotations", None)
    truncate_data(resource)
    return resource


def strip_apply(resource) -> dict:
    """Apply view: no status, no server/cluster-assigned metadata."""
    resource = strip_full(resource)
    resource.pop("status", None)
    metadata = resource.get("metadata")
    if isinstance(metadata, dict):
        for key in SERVER_ASSIGNED_METADATA:
            metadata.pop(key, None)
    strip_cluster_assigned(resource)
    return resource


class _BlockDumper(yaml.SafeDumper):
    """YAML dumper that renders multiline strings as readable block scalars."""


def _represent_str(dumper, data):
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_BlockDumper.add_representer(str, _represent_str)


def write_yaml(output_file: Path, base_pattern, resources) -> None:
    """Write stripped resources to a YAML file, one document per resource."""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# Resources from the testrun: {base_pattern}\n---\n")
        if resources:
            f.write(
                "\n---\n".join(
                    yaml.dump(r, Dumper=_BlockDumper, default_flow_style=False, sort_keys=False) for r in resources
                )
            )
        else:
            f.write("# No matching resources found\n")
