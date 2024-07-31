"""Tests for the functionality of the deep-evaluator metric samples"""

import pytest

from testsuite.kuadrant.policy.authorization import Value, JsonResponse

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def mockserver_expectation(request, mockserver, module_label):
    """Creates Mockserver Expectation which returns non-empty response on hit"""
    request.addfinalizer(lambda: mockserver.clear_expectation(module_label))
    return mockserver.create_response_expectation(module_label, "response")


@pytest.fixture(scope="module")
def authorization(authorization, mockserver_expectation):
    """
    Create AuthConfig with one of each type of evaluators. Allow metrics collection in every section.

    Add to the AuthConfig:
        - anonymous identity
        - always allowed opa policy authorization
        - http metadata from the mockserver
        - non-empty response
    """
    authorization.identity.add_anonymous("anonymous", metrics=True)
    authorization.authorization.add_opa_policy("opa", "allow { true }", metrics=True)
    authorization.metadata.add_http("http", mockserver_expectation, "GET", metrics=True)
    authorization.responses.add_success_header("json", JsonResponse({"auth": Value("response")}), metrics=True)

    return authorization


@pytest.fixture(scope="module")
def deep_metrics(authorino, service_monitor, prometheus, client, auth):
    """Send a simple get request so that a few metrics can appear and return all scraped evaluator(deep) metrics"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    prometheus.wait_for_scrape(service_monitor, "/server-metrics")

    return prometheus.get_metrics("auth_server_evaluator_total", labels={"service": authorino.metrics_service.name()})


@pytest.mark.parametrize(
    "metric_name, metric_type",
    [
        pytest.param("opa", "AUTHORIZATION_OPA", id="authorization"),
        pytest.param("anonymous", "IDENTITY_NOOP", id="identity"),
        pytest.param("http", "METADATA_GENERIC_HTTP", id="metadata"),
        pytest.param("json", "RESPONSE_JSON", id="response"),
    ],
)
def test_deep_metrics(metric_name, metric_type, deep_metrics, authorization):
    """Test if each set evaluator metric is collected and correctly responds to the request sent"""
    metrics = deep_metrics.filter(
        lambda x: x["metric"]["evaluator_name"] == metric_name
        and x["metric"]["evaluator_type"] == metric_type
        and x["metric"]["authconfig"].endswith(authorization.name())
    )

    assert len(metrics.metrics) == 1
    assert metrics.values[0] == 1
