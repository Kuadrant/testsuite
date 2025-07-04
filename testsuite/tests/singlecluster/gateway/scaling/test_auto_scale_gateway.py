"""
This module contains tests for auto-scaling the gateway deployment with an HPA watching the cpu usage
"""

import time

import pytest

from testsuite.kuadrant.policy import CelPredicate
from testsuite.kuadrant.policy.authorization import JsonResponse, ValueFrom
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit
from testsuite.kubernetes import Selector
from testsuite.kubernetes.deployment import Deployment
from testsuite.kubernetes.horizontal_pod_autoscaler import HorizontalPodAutoscaler

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, rate_limit, dns_policy, tls_policy):
    """Commits all important stuff before tests"""
    for component in [dns_policy, tls_policy, authorization, rate_limit]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()


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
def hpa(request, cluster, blame, gateway):
    """Add hpa to the gateway deployment"""
    hpa = HorizontalPodAutoscaler.create_instance(
        cluster,
        blame("hpa"),
        gateway.deployment,
        [
            {
                "type": "Resource",
                "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": 50}},
            }
        ],
    )
    request.addfinalizer(hpa.delete)
    hpa.commit()
    return hpa


@pytest.fixture(scope="module")
def load_generator(request, cluster, blame, api_key, client):
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
            "-c",
            "5",
            "-t",
            "5m",
            f"{client.base_url.scheme}://{client.base_url.host}",
        ],
    )

    request.addfinalizer(load_generator.delete)
    load_generator.commit()
    return load_generator


@pytest.fixture(scope="module")
def rate_limit(blame, gateway, module_label, cluster):
    """Add limit to the policy"""
    policy = RateLimitPolicy.create_instance(cluster, blame("rlp"), gateway, labels={"app": module_label})
    policy.add_limit("basic", [Limit(5, "5s")], when=[CelPredicate("auth.identity.userid != 'load-generator'")])
    return policy


def test_auto_scale_gateway(gateway, client, auth, hpa, load_generator):  # pylint: disable=unused-argument
    """This test asserts that the policies are working as expected and this behavior does not change after scaling"""
    anon_auth_resp = client.get("/get")
    assert anon_auth_resp is not None
    assert anon_auth_resp.status_code == 401

    responses = client.get_many("/get", 5, auth=auth)
    responses.assert_all(status_code=200)

    assert client.get("/get", auth=auth).status_code == 429

    time.sleep(5)  # sleep in order to reset the rate limit policy time limit.

    assert gateway.deployment.replicas > 1

    anon_auth_resp = client.get("/get")
    assert anon_auth_resp is not None
    assert anon_auth_resp.status_code == 401

    responses = client.get_many("/get", 5, auth=auth)
    responses.assert_all(status_code=200)

    assert client.get("/get", auth=auth).status_code == 429
