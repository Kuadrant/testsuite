"""
This module contains tests for auto-scaling the gateway deployment with an HPA watching the cpu usage
"""

import time

import pytest


from testsuite.kubernetes.horizontal_pod_autoscaler import HorizontalPodAutoscaler
from testsuite.tests.singlecluster.gateway.scaling.conftest import LIMIT

pytestmark = [pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]

METRIC_NAME = "mocked_metric"


@pytest.fixture(scope="module")
def hpa(request, cluster, gateway, blame, backend, module_label):
    """Add hpa to the gateway deployment"""
    hpa = HorizontalPodAutoscaler.create_instance(
        cluster,
        blame("hpa"),
        gateway.deployment,
        [
            # Set the metric to scale on
            {
                "type": "Object",
                "object": {
                    "metric": {"name": METRIC_NAME},
                    "describedObject": {
                        "apiVersion": "v1",
                        "kind": "Service",
                        "name": backend.service.name(),
                    },
                    "target": {
                        "type": "Value",
                        "value": f"{LIMIT.limit - 1}",  # set the value to the limit - 1 to trigger the scaling
                    },
                },
            }
        ],
        labels={"app": module_label},
        min_replicas=1,
        max_replicas=5,
    )

    # Add finalizer to delete the HPA
    request.addfinalizer(hpa.delete)
    hpa.commit()

    return hpa


def test_auto_scale_gateway(
    gateway, hpa, backend, client, auth, custom_metrics_apiserver, cluster
):  # pylint: disable=unused-argument
    """This test asserts that the policies are working as expected and this behavior does not change after scaling"""
    anon_auth_resp = client.get("/anything/auth")
    assert anon_auth_resp is not None
    assert anon_auth_resp.status_code == 401

    auth_resp = client.get("/anything/auth", auth=auth)
    assert auth_resp is not None
    assert auth_resp.status_code == 200

    responses = client.get_many("/anything/limit", LIMIT.limit, auth=auth)
    responses.assert_all(status_code=200)

    assert client.get("/anything/limit", auth=auth).status_code == 429

    time.sleep(5)  # sleep in order to reset the rate limit policy time limit.

    # Write the metric to the custom metrics apiserver and trigger the scaling
    assert (
        custom_metrics_apiserver.write_metric(
            cluster.project, "service", backend.service.name(), METRIC_NAME, LIMIT.limit
        )
        == 200
    )
    gateway.deployment.wait_for_replicas(2)

    anon_auth_resp = client.get("/anything/auth")
    assert anon_auth_resp is not None
    assert anon_auth_resp.status_code == 401

    auth_resp = client.get("/anything/auth", auth=auth)
    assert auth_resp is not None
    assert auth_resp.status_code == 200

    responses = client.get_many("/anything/limit", LIMIT.limit, auth=auth)
    responses.assert_all(status_code=200)

    assert client.get("/anything/limit", auth=auth).status_code == 429
