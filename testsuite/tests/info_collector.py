"""
This module is not TRUE test. please do not rename to test_

It should only be executed in special mode defined by environment variable COLLECTOR_ENABLE=true
No xdist, only sequential. Supposed to be run before actual testsuite, isolated, to capture the values.

example:
COLLECTOR_ENABLE=true pytest --junit-xml="${RESULTS_PATH}/junit_00_info_collector.xml" -o junit_logging=all testsuite/tests/info_collector.py
"""

import pytest
import os
import sys
import re
import json

import openshift_client as oc

from testsuite.component_metadata import ReportPortalMetadataCollector
from dynaconf import ValidationError

import logging

logger = logging.getLogger(__name__)


def get_component_images(namespace) -> list[tuple]:
    """Get container images from pods in a namespace using openshift_client"""
    images = []
    try:
        # Change to the target namespace
        result = oc.invoke("get", ["pods", "-n", namespace, "-o", "json"])
        pods_data = json.loads(result.out())

        # Extract container images from all pods
        for pod in pods_data.get("items", []):
            for container in pod.get("spec", {}).get("containers", []):
                image = container.get("image", "")
                print(f"{image=}")
                if "@sha256" in image:
                    # Skip SHAs, as we want version only if they are tagged
                    # SHAs are not useful for versions attributes
                    continue
                if image:
                    # Parse image name and tag
                    # Format: registry/name:tag or name:tag
                    image_name = image.split("/")[-1]  # Get last part (name:tag)
                    if ":" in image_name:
                        name, tag = image_name.rsplit(":", 1)
                    else:
                        name, tag = image_name, "latest"
                    images.append((name, tag))
                    print(f"{name}:{tag}")
    except (IndexError, ValueError, oc.OpenShiftPythonException) as e:
        logger.error(f"Failed to get images from {namespace}: {e}")

    return images


def get_current_context() -> str | None:
    """Get current Kubernetes context using openshift_client"""
    try:
        result = oc.invoke("config", ["current-context"])
        return result.out().strip()
    except oc.OpenShiftPythonException as e:
        logger.error(f"Failed to get current context: {e}")
        return None


def get_kubernetes_version() -> str | None:
    """Run oc version and get the kubernetes version"""
    result = None
    try:
        version_result = oc.invoke("version", ["-o", "json"])
        version_info = version_result.out()

        version_data = json.loads(version_info)
        print(f"{version_data=}")

        kubernetes_version = version_data.get("serverVersion", {}).get("gitVersion", None)
        if kubernetes_version:
            match = re.match(r"v([0-9]+\.[0-9]+)(\.[0-9]+)?", kubernetes_version)
            if match:
                # extract only major.minor
                result = match.groups()[0]
    except oc.OpenShiftPythonException as e:
        logger.exception(e)
    return result


def get_openshift_version() -> str | None:
    """Get 'clusterversion' object and parse openshift version"""
    result = None
    try:

        version_result = oc.selector("clusterversion").objects()
        if version_result:
            ocp_version = version_result[0].model.status.history[0].version
            print(f"Server version: {ocp_version}")  # e.g., "4.20.1"
            # extract just major.minor
            match = re.match(r"([0-9]+\.[0-9]+)(\.[0-9]+)?", ocp_version)
            if match:
                short_version = match.groups()[0]
                result = short_version

    except oc.OpenShiftPythonException as e:
        logger.exception(e)
    return result


def gather_cluster_versions() -> dict:
    """gather all particular versions into a dictionary"""
    return {
        "kubernetes": get_kubernetes_version(),
        "openshift": get_openshift_version(),
    }


@pytest.fixture(scope="session")
def properties_collector(record_testsuite_property):
    """Main property collector - properties added here will be promoted to Launch level"""
    # Placeholder for any additional properties that need to be collected at session level
    # Properties can be added here if needed in the future
    pass


@pytest.fixture(scope="session")
def rp_suite_description(record_testsuite_property):
    """Ability to add something to suite description"""
    suite_description = """ This is an example how to set Suite description """
    record_testsuite_property("__rp_suite_description", suite_description)


def get_cluster_information() -> str:
    """Cluster information collector"""
    cluster_info = ""
    try:
        collector = ReportPortalMetadataCollector()
        collector.collect_all_clusters()
        cluster_info = collector.format_cluster_info()
    except (oc.OpenShiftPythonException, AttributeError, KeyError, ValidationError) as e:
        logger.error(f"Component metadata collection failed: {e}")

    return cluster_info


@pytest.mark.skipif(not os.environ.get("COLLECTOR_ENABLE"), reason="collector was not excplicitly enabled")
def test_launch_description(record_testsuite_property):
    """Direct modification of RP Lauch description via promoted attribute

    description provided via commandline will be per-pended to this
    """
    launch_description = get_cluster_information()

    record_testsuite_property("__rp_launch_description", launch_description)


@pytest.mark.skipif(not os.environ.get("COLLECTOR_ENABLE"), reason="collector was not excplicitly enabled")
def test_cluster_properties(record_testsuite_property, properties_collector):
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

    # Get current Kubernetes context
    kube_context = get_current_context()
    print(f"{kube_context=}")
    if kube_context:
        record_testsuite_property("kube_context", kube_context)


@pytest.mark.skipif(not os.environ.get("COLLECTOR_ENABLE"), reason="collector was not excplicitly enabled")
def test_kuadrant_properties(record_testsuite_property):
    """Record kuadrant related properties"""
    # Get Kuadrant component versions
    kuadrant_images = get_component_images("kuadrant-system")
    if kuadrant_images:
        print(f"Kuadrant images: {kuadrant_images}")
        for name, tag in kuadrant_images:
            record_testsuite_property(name, tag)


@pytest.mark.skipif(not os.environ.get("COLLECTOR_ENABLE"), reason="collector was not excplicitly enabled")
def test_istio_properties(record_testsuite_property):
    """Record Istio related properties"""

    # Get Istio component versions (filter for sail-operator)
    istio_images = get_component_images("istio-system")
    if istio_images:
        print(f"Istio images: {istio_images}")
        for name, tag in istio_images:
            if "sail-operator" in name:
                record_testsuite_property(name, tag)


@pytest.mark.skipif(not os.environ.get("COLLECTOR_ENABLE"), reason="collector was not excplicitly enabled")
def test_collect(record_testsuite_property):
    """Main collector entrypoint"""
    # Placeholder for now, if any miscellanous collection should be happening.
    # Otherwise it will be subject for removal.
    assert True


@pytest.mark.skipif(not os.environ.get("COLLECTOR_ENABLE"), reason="collector was not excplicitly enabled")
def test_controller():

    ## probably not worth it to collect uname from the pytest controller ?
    print(f"{os.uname()=}")
    # print(f'{os.=}')
    ## probably not worth it, since it will be collecting launch arguments for collector only
    print(f"{sys.argv=}")

    assert True
