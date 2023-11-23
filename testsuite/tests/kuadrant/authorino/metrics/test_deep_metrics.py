"""Tests for the functionality of the deep-evaluator metric samples"""
import pytest

from testsuite.policy.authorization import Value, JsonResponse


@pytest.fixture(scope="module")
def mockserver_expectation(request, mockserver, module_label):
    """Creates Mockserver Expectation which returns non-empty response on hit"""
    request.addfinalizer(lambda: mockserver.clear_expectation(module_label))
    return mockserver.create_expectation(module_label, "response")


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
def deep_metrics(authorino, prometheus):
    """Return all evaluator(deep) metrics"""
    prometheus.wait_for_scrape(authorino.metrics_service.name(), "/server-metrics")

    return prometheus.get_metrics("auth_server_evaluator_total", labels={"service": authorino.metrics_service.name()})


@pytest.mark.parametrize(
    "metric_name, metric_type",
    [
        ("opa", "AUTHORIZATION_OPA"),
        ("anonymous", "IDENTITY_NOOP"),
        ("http", "METADATA_GENERIC_HTTP"),
        ("json", "RESPONSE_JSON"),
    ],
)
def test_deep_metrics(metric_name, metric_type, deep_metrics):
    """Test if each set evaluator metric is collected and correctly responds to the request sent"""
    metrics = deep_metrics.filter(
        lambda x: x["metric"]["evaluator_name"] == metric_name and x["metric"]["evaluator_type"] == metric_type
    )

    assert metrics
    assert metrics.values[0] == 1
