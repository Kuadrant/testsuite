"""Test: Destination-based credential selection — different credentials per route.

Based on https://github.com/Kuadrant/architecture/issues/148
Two HTTPRoutes (/service1, /service2) with separate AuthPolicies inject different credentials:
  - /service1 -> Authorization: Bearer <service1-key>
  - /service2 -> X-Api-Key: <service2-key>
Uses MockServer to validate each route receives the correct credential.
Credentials are fetched from Kubernetes Secrets via metadata.http.
"""

import pytest

from testsuite.gateway import CustomReference, URLRewriteFilter, RouteMatch, PathMatch, MatchType
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.policy.authorization import Credentials, Pattern, PlainResponse, ValueFrom
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kubernetes.secret import Secret

from ..conftest import EGRESS_HOSTNAME

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.egress_gateway]

SERVICE1_API_KEY = "pretty-random-api-key-to-use-for-egress-test-41894726"
SERVICE2_API_KEY = "sk-fake-service2-key-for-egress-test-9876543210"


@pytest.fixture(scope="module")
def mockserver_expectation(mockserver_client, module_label):
    """MockServer expectation: 200 if Authorization: Bearer <service1-key>, 401 otherwise"""
    template = """
    {
      "statusCode": #if($request.headers['authorization']
        && $request.headers['authorization'].contains("Bearer %s")) 200 #else 401 #end,
      "headers": { "Content-Type": ["application/json"] }
    }
    """ % SERVICE1_API_KEY
    mockserver_client.create_template_expectation(module_label, template, "VELOCITY")
    return f"/{module_label}"


@pytest.fixture(scope="module")
def service2_expectation(mockserver_client, blame):
    """MockServer expectation: 200 if X-Api-Key: <service2-key>, 401 otherwise"""
    eid = blame("svc2")
    template = """
    {
      "statusCode": #if($request.headers['x-api-key']
        && $request.headers['x-api-key'].contains("%s")) 200 #else 401 #end,
      "headers": { "Content-Type": ["application/json"] }
    }
    """ % SERVICE2_API_KEY
    mockserver_client.create_template_expectation(eid, template, "VELOCITY")
    return f"/{eid}"


@pytest.fixture(scope="module")
def service1_api_secret(request, cluster, blame, module_label):
    """Secret containing a fake API key for service 1"""
    secret = Secret.create_instance(
        cluster,
        blame("svc1-key"),
        stringData={"api_key": SERVICE1_API_KEY},
        labels={"app": module_label},
    )
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret


@pytest.fixture(scope="module")
def service2_api_secret(request, cluster, blame, module_label):
    """Secret containing a fake API key for service 2"""
    secret = Secret.create_instance(
        cluster,
        blame("svc2-key"),
        stringData={"api_key": SERVICE2_API_KEY},
        labels={"app": module_label},
    )
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret


@pytest.fixture(scope="module")
def sa_token_secret(request, system_project, blame, module_label):
    """Opaque Secret containing a token from Authorino's ServiceAccount for K8s API auth"""
    authorino_sa = system_project.get_service_account("authorino-authorino")
    token = authorino_sa.get_auth_token()
    secret = Secret.create_instance(
        system_project,
        blame("authorino-k8s-auth"),
        stringData={"token": token},
        labels={"app": module_label},
    )
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret


@pytest.fixture(scope="module")
def route(
    request, gateway, cluster, blame, hostname, module_label, service_entry, destination_rule, mockserver_expectation
):  # pylint: disable=unused-argument
    """HTTPRoute for /service1 path, rewrites to MockServer service1 expectation"""
    route = HTTPRoute.create_instance(cluster, blame("svc1-rt"), gateway, {"app": module_label})
    route.add_hostname(EGRESS_HOSTNAME)
    route.add_rule(
        CustomReference(group="networking.istio.io", kind="Hostname", name=hostname.hostname, port=443),
        RouteMatch(path=PathMatch(type=MatchType.PATH_PREFIX, value="/service1")),
        filters=[URLRewriteFilter(hostname=hostname.hostname, replace_prefix_match=mockserver_expectation)],
    )
    request.addfinalizer(route.delete)
    route.commit()
    route.wait_for_ready()
    return route


@pytest.fixture(scope="module")
def route2(
    request, gateway, cluster, blame, hostname, module_label, service_entry, destination_rule, service2_expectation
):  # pylint: disable=unused-argument
    """HTTPRoute for /service2 path, rewrites to MockServer service2 expectation"""
    route = HTTPRoute.create_instance(cluster, blame("svc2-rt"), gateway, {"app": module_label})
    route.add_hostname(EGRESS_HOSTNAME)
    route.add_rule(
        CustomReference(group="networking.istio.io", kind="Hostname", name=hostname.hostname, port=443),
        RouteMatch(path=PathMatch(type=MatchType.PATH_PREFIX, value="/service2")),
        filters=[URLRewriteFilter(hostname=hostname.hostname, replace_prefix_match=service2_expectation)],
    )
    request.addfinalizer(route.delete)
    route.commit()
    route.wait_for_ready()
    return route


@pytest.fixture(scope="module")
def authorization(cluster, route, blame, module_label, service1_api_secret, sa_token_secret):
    """AuthPolicy injecting the service 1 API key as an Authorization header"""
    auth = AuthPolicy.create_instance(cluster, blame("svc1-authz"), route, labels={"app": module_label})
    auth.identity.add_anonymous("anonymous")
    auth.metadata.add_http(
        "credential_fetch",
        f"https://kubernetes.default.svc/api/v1/namespaces/{cluster.project}/secrets/{service1_api_secret.name()}",
        "GET",
        credentials=Credentials("authorizationHeader", "Bearer"),
        shared_secret_ref={"name": sa_token_secret.name(), "key": "token"},
    )
    auth.responses.add_success_header(
        "authorization",
        PlainResponse(plain=ValueFrom("Bearer {auth.metadata.credential_fetch.data.api_key.@base64:decode}")),
        when=[Pattern("context.request.http.headers.@keys", "excl", "dont-inject")],
    )
    return auth


@pytest.fixture(scope="module")
def authorization2(cluster, route2, blame, module_label, service2_api_secret, sa_token_secret):
    """AuthPolicy injecting service 2 key as X-Api-Key header on /service2 route"""
    auth = AuthPolicy.create_instance(cluster, blame("svc2-authz"), route2, labels={"app": module_label})
    auth.identity.add_anonymous("anonymous")
    auth.metadata.add_http(
        "credential_fetch",
        f"https://kubernetes.default.svc/api/v1/namespaces/{cluster.project}/secrets/{service2_api_secret.name()}",
        "GET",
        credentials=Credentials("authorizationHeader", "Bearer"),
        shared_secret_ref={"name": sa_token_secret.name(), "key": "token"},
    )
    auth.responses.add_success_header(
        "x-api-key",
        PlainResponse(plain=ValueFrom("{auth.metadata.credential_fetch.data.api_key.@base64:decode}")),
        when=[Pattern("context.request.http.headers.@keys", "excl", "dont-inject")],
    )
    return auth


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, authorization2):
    """Commit both AuthPolicies and wait for them to be enforced"""
    for auth in [authorization, authorization2]:
        request.addfinalizer(auth.delete)
        auth.commit()
        auth.wait_for_ready()


def test_credential_injection_by_destination(client):
    """Test that /service1 and /service2 routes inject the correct credential for their respective destinations"""
    response = client.get("/service1")
    assert response.status_code == 200
    response = client.get("/service1", headers={"dont-inject": "true"})
    assert response.status_code == 401

    response = client.get("/service2")
    assert response.status_code == 200
    response = client.get("/service2", headers={"dont-inject": "true"})
    assert response.status_code == 401
