"""
This module is not TRUE test. please do not rename to test_

It should only be executed in special mode defined by environment variable COLLECTOR_ENABLE=true
No xdist, only sequential. Supposed to be run before actual testsuite, isolated, to capture the values.

example:
COLLECTOR_ENABLE=true pytest --junit-xml="${RESULTS_PATH}/junit_00_info_collector.xml" /
-o junit_logging=all testsuite/tests/info_collector.py

Report Portal special properties (via record_testsuite_property):
  These are reserved property keys recognized by testsuite-rptool during JUnit XML import.
  See https://github.com/Kuadrant/testsuite-rptool/blob/main/README.md for full documentation and examples.

  __rp_launch_description  - sets the Launch description (top-level run summary)
  __rp_suite_description   - sets the Suite description (test suite level)
  __rp_case_description    - sets the Test Case description (individual test level)
"""

import logging
import os

import openshift_client as oc
import pytest
from dynaconf import ValidationError

from testsuite.component_metadata import ReportPortalMetadataCollector
from testsuite.container_image_versions import SEMVER_PATTERN, ContainerRegistryResolver
from testsuite.template_utils import render_template
from testsuite.config import settings

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.skipif(
    not os.environ.get("COLLECTOR_ENABLE"),
    reason="collector was not explicitly enabled",
)


def _all_cluster_projects(namespace):
    """Yield (cluster_name, cluster_client, project or None) for each configured cluster."""
    for cluster_name, cluster in ReportPortalMetadataCollector.get_cluster_configurations():
        project = cluster.change_project(namespace)
        yield cluster_name, cluster, (project if project.connected else None)


def _print_cluster_data(cluster_data):
    """Print collected data per cluster."""
    for cluster_name, lines in cluster_data.items():
        print(f"\n{cluster_name}:")
        for line in lines:
            print(f"  {line}")


def _record_unique(record_testsuite_property, properties):
    """Record properties, only adding unique ones as attributes."""
    seen = set()
    for key, value in properties:
        if not value:
            continue
        if (key, value) not in seen:
            seen.add((key, value))
            record_testsuite_property(key, value)
            logger.info("recording property %s:%s", key, value)


def get_cluster_information() -> dict:
    """Cluster information collector"""
    cluster_info = {}
    try:
        collector = ReportPortalMetadataCollector()
        collector.collect_all_clusters()
        cluster_info = collector.get_cluster_metadata()
    except (oc.OpenShiftPythonException, AttributeError, KeyError, ValidationError) as e:
        logger.error("Component metadata collection failed: %s", e)

    return cluster_info


def test_launch_description(record_testsuite_property):
    """Collect cluster information and set the Report Portal launch description."""
    cluster_data = get_cluster_information()
    description_data = {"cluster_count": len(cluster_data), "clusters": cluster_data}

    launch_description = render_template("reporting/launch_description.txt.j2", description_data)

    record_testsuite_property("__rp_launch_description", launch_description)


def test_cluster_properties(record_testsuite_property):
    """Collect cluster version properties from all clusters."""
    system_ns = settings["service_protection"]["system_project"]
    properties = []
    cluster_data = {}
    for cluster_name, cluster, project in _all_cluster_projects(system_ns):
        if project is None:
            cluster_data[cluster_name] = [f"namespace '{system_ns}' not found"]
            continue
        versions = {
            "kubernetes": ReportPortalMetadataCollector.get_kubernetes_version(project),
            "openshift": cluster.ocp_version,
        }
        cluster_data[cluster_name] = [f"{k}:{v}" for k, v in versions.items()]
        for key, value in versions.items():
            properties.append((key, value))

    _print_cluster_data(cluster_data)
    _record_unique(record_testsuite_property, properties)


def test_kuadrant_properties(record_testsuite_property):
    """Record kuadrant related properties from all clusters."""
    system_ns = settings["service_protection"]["system_project"]
    properties = []
    cluster_data = {}
    for cluster_name, _, project in _all_cluster_projects(system_ns):
        if project is None:
            cluster_data[cluster_name] = [f"namespace '{system_ns}' not found"]
            continue
        cluster_data[cluster_name] = []
        kuadrant_images = ReportPortalMetadataCollector.get_component_images(project)
        for name, tag, full_image in kuadrant_images:
            if "testsuite-pipelines-tools" in full_image:
                continue
            if tag:
                cluster_data[cluster_name].append(f"{name}:{tag} ({full_image})")
                properties.append((name, tag))
            else:
                cluster_data[cluster_name].append(full_image)

    _print_cluster_data(cluster_data)
    _record_unique(record_testsuite_property, properties)


def _resolve_tools_versions(tools_images):
    """Resolve tool image digests to semver version tags."""
    results = []
    to_resolve = []
    for name, tag, full_image, digest in tools_images:
        if tag and SEMVER_PATTERN.match(tag):
            results.append((name, tag, full_image))
        else:
            to_resolve.append((name, tag, full_image, digest))

    if to_resolve:
        try:
            with ContainerRegistryResolver() as resolver:
                for name, tag, full_image, digest in to_resolve:
                    resolved = resolver.resolve_digest_to_tag(full_image, digest)
                    results.append((name, resolved or tag, full_image))
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Registry resolution failed: %s", exc)
            for name, tag, full_image, _ in to_resolve:
                results.append((name, tag, full_image))

    return results


def test_tools_properties(record_testsuite_property):
    """Record tools version properties from all clusters."""
    properties = []
    cluster_data = {}
    for cluster_name, _, project in _all_cluster_projects("tools"):
        if project is None:
            cluster_data[cluster_name] = ["namespace 'tools' not found"]
            continue
        cluster_data[cluster_name] = []
        tools_images = ReportPortalMetadataCollector.get_pod_images(project)
        resolved = _resolve_tools_versions(tools_images)
        for name, version, full_image in resolved:
            if version:
                cluster_data[cluster_name].append(f"{name}:{version} ({full_image})")
                properties.append((name, version))
            else:
                cluster_data[cluster_name].append(full_image)

    _print_cluster_data(cluster_data)
    _record_unique(record_testsuite_property, properties)


def test_istio_properties(record_testsuite_property):
    """Record Istio installation type and metadata from all clusters."""
    properties = []
    cluster_data = {}
    for cluster_name, cluster, _ in _all_cluster_projects("default"):
        istio_type, namespace = ReportPortalMetadataCollector.get_istio_type(cluster)
        cluster_data[cluster_name] = [f"istio_type:{istio_type}"]
        properties.append(("istio_type", istio_type))

        if namespace is None:
            continue

        project = cluster.change_project(namespace)
        if not project.connected:
            cluster_data[cluster_name].append(f"namespace '{namespace}' not found")
            continue

        istio_metadata = ReportPortalMetadataCollector.get_istio_metadata(project)
        for key, value in istio_metadata.items():
            cluster_data[cluster_name].append(f"{key}:{value}")
            if key == "istio_version":
                properties.append((key, value))

    _print_cluster_data(cluster_data)
    _record_unique(record_testsuite_property, properties)
