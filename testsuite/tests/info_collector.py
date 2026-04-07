"""
This module is not TRUE test. please do not rename to test_

It should only be executed in special mode defined by environment variable COLLECTOR_ENABLE=true
No xdist, only sequential. Supposed to be run before actual testsuite, isolated, to capture the values.

example:
COLLECTOR_ENABLE=true pytest --junit-xml="${RESULTS_PATH}/junit_00_info_collector.xml" /
-o junit_logging=all testsuite/tests/info_collector.py
"""

import logging
import os
import sys

import openshift_client as oc
import pytest
from dynaconf import ValidationError

from testsuite.component_metadata import ReportPortalMetadataCollector
from testsuite.template_utils import render_template
from testsuite.config import settings

logger = logging.getLogger(__name__)


def gather_cluster_versions() -> dict:
    """gather all particular versions into a dictionary"""
    cluster_client = settings["control_plane"]["cluster"]
    project = cluster_client.change_project(settings["service_protection"]["system_project"])
    return {
        "kubernetes": ReportPortalMetadataCollector.get_kubernetes_version(project),
        "openshift": ReportPortalMetadataCollector.get_ocp_version(project),
    }


@pytest.fixture(scope="session")
def properties_collector(record_testsuite_property):  # pylint: disable=unused-argument
    """Main property collector - properties added here will be promoted to Launch level"""
    # Placeholder for any additional properties that need to be collected at session level
    # Properties can be added here if needed in the future


@pytest.fixture(scope="session")
def rp_suite_description(record_testsuite_property):
    """Ability to add something to suite description"""
    suite_description = """ This is an example how to set Suite description """
    record_testsuite_property("__rp_suite_description", suite_description)


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


@pytest.mark.skipif(not os.environ.get("COLLECTOR_ENABLE"), reason="collector was not excplicitly enabled")
def test_launch_description(record_testsuite_property):
    """Direct modification of RP Lauch description via promoted attribute
    description provided via commandline will be pre-pended to this
    """
    cluster_data = get_cluster_information()
    description_data = {"cluster_count": len(cluster_data), "clusters": cluster_data}

    launch_description = render_template("reporting/launch_description.txt.j2", description_data)

    record_testsuite_property("__rp_launch_description", launch_description)


@pytest.mark.skipif(not os.environ.get("COLLECTOR_ENABLE"), reason="collector was not excplicitly enabled")
def test_cluster_properties(record_testsuite_property):
    """Collect cluster properties"""

    # cluster version
    cluster_versions = gather_cluster_versions()
    for k, v in cluster_versions.items():
        print(f"recording property {k}:{v}")
        if v:  # filter out None values
            record_testsuite_property(k, v)


@pytest.mark.skipif(not os.environ.get("COLLECTOR_ENABLE"), reason="collector was not excplicitly enabled")
def test_kube_context(record_testsuite_property):
    """Record current kube context"""

    kube_context = settings["control_plane"]["cluster"].kubeconfig_path
    print(f"{kube_context=}")
    if kube_context:
        record_testsuite_property("kube_context", kube_context)


@pytest.mark.skipif(not os.environ.get("COLLECTOR_ENABLE"), reason="collector was not excplicitly enabled")
def test_kuadrant_properties(record_testsuite_property):
    """Record kuadrant related properties"""
    # Get Kuadrant component versions
    cluster_client = settings["control_plane"]["cluster"]
    project = cluster_client.change_project("kuadrant-system")
    kuadrant_images = ReportPortalMetadataCollector.get_component_images(project)
    if kuadrant_images:
        print(f"Kuadrant images: {kuadrant_images}")
        for name, tag, _ in kuadrant_images:
            record_testsuite_property(name, tag)


@pytest.mark.skipif(not os.environ.get("COLLECTOR_ENABLE"), reason="collector was not excplicitly enabled")
def test_istio_properties(record_testsuite_property):
    """Record Istio related properties"""

    # Get Istio component versions (filter for sail-operator)
    cluster_client = settings["control_plane"]["cluster"]
    project = cluster_client.change_project("istio-system")
    istio_images = ReportPortalMetadataCollector.get_component_images(project)
    if istio_images:
        print(f"Istio images: {istio_images}")
        for name, tag, _ in istio_images:
            if "sail-operator" in name:
                record_testsuite_property(name, tag)


@pytest.mark.skipif(not os.environ.get("COLLECTOR_ENABLE"), reason="collector was not excplicitly enabled")
def test_collect(record_testsuite_property):  # pylint: disable=unused-argument
    """Main collector entrypoint"""
    # Placeholder for now, if any miscellanous collection should be happening.
    # Otherwise it will be subject for removal.
    assert True


@pytest.mark.skipif(not os.environ.get("COLLECTOR_ENABLE"), reason="collector was not excplicitly enabled")
def test_controller():
    """Collect controller/host information (uname, argv)"""
    ## probably not worth it to collect uname from the pytest controller ?
    print(f"{os.uname()=}")
    # print(f'{os.=}')
    ## probably not worth it, since it will be collecting launch arguments for collector only
    print(f"{sys.argv=}")

    assert True
