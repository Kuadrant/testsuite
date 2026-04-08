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
from testsuite.template_utils import render_template
from testsuite.config import settings

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.skipif(
    not os.environ.get("COLLECTOR_ENABLE"),
    reason="collector was not explicitly enabled",
)


def gather_cluster_versions() -> dict:
    """gather all particular versions into a dictionary"""
    cluster_client = settings["control_plane"]["cluster"]
    project = cluster_client.change_project(settings["service_protection"]["system_project"])
    return {
        "kubernetes": ReportPortalMetadataCollector.get_kubernetes_version(project),
        "openshift": ReportPortalMetadataCollector.get_ocp_version(project),
    }


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
    """Collect cluster properties"""
    cluster_versions = gather_cluster_versions()
    for k, v in cluster_versions.items():
        print(f"recording property {k}:{v}")
        if v:  # filter out None values
            record_testsuite_property(k, v)


def test_kube_context(record_testsuite_property):
    """Record current kube context"""
    kube_context = settings["control_plane"]["cluster"].kubeconfig_path
    print(f"{kube_context=}")
    if kube_context:
        record_testsuite_property("kube_context", kube_context)


def test_kuadrant_properties(record_testsuite_property):
    """Record kuadrant related properties"""
    cluster_client = settings["control_plane"]["cluster"]
    project = cluster_client.change_project("kuadrant-system")
    kuadrant_images = ReportPortalMetadataCollector.get_component_images(project)
    if kuadrant_images:
        print(f"Kuadrant images: {kuadrant_images}")
        for name, tag, _ in kuadrant_images:
            record_testsuite_property(name, tag)


def test_istio_properties(record_testsuite_property):
    """Record Istio related properties"""
    cluster_client = settings["control_plane"]["cluster"]
    project = cluster_client.change_project("istio-system")
    istio_metadata = ReportPortalMetadataCollector.get_istio_metadata(project)
    for key, value in istio_metadata.items():
        print(f"{key}: {value}")
        if key == "istio_version":
            record_testsuite_property(key, value)
