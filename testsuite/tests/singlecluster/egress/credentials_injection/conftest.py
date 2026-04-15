"""Shared fixtures for egress credential injection tests.

Provides MockServer backend, Authorino SA token for K8s API auth,
and common credential injection fixtures (service1 secret, mockserver backend, mockserver expectation, authorization).
"""

import pytest

from testsuite.backend.mockserver import MockserverBackend
from testsuite.httpx import KuadrantClient
from testsuite.kuadrant.policy.authorization import Credentials, Pattern, PlainResponse, ValueFrom
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kubernetes.secret import Secret
from testsuite.mockserver import Mockserver

SERVICE1_API_KEY = "pretty-random-api-key-to-use-for-egress-test-41894726"


@pytest.fixture(scope="module", autouse=True)
def cluster_ca_trust(kuadrant, skip_or_fail):
    """Skip tests if Authorino doesn't trust the cluster CA"""
    volumes = kuadrant.authorino.model.spec.get("volumes", {}).get("items", [])
    if not any(v.get("name") == "cluster-trust-bundle" for v in volumes):
        skip_or_fail("Authorino does not trust cluster CA (missing 'cluster-trust-bundle' volume)")


@pytest.fixture(scope="module")
def backend(request, cluster, blame, label):
    """Deploy MockServer as the backend to validate injected credentials"""
    mockserver = MockserverBackend(cluster, blame("mocksrv"), label)
    request.addfinalizer(mockserver.delete)
    mockserver.commit()
    mockserver.wait_for_ready()
    return mockserver


@pytest.fixture(scope="module")
def mockserver_client(backend):
    """Mockserver client for creating expectations and direct requests"""
    return Mockserver(KuadrantClient(base_url=f"http://{backend.service.refresh().external_ip}:8080"))


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
def sa_token_secret(request, testconfig, cluster, blame, module_label):
    """Opaque Secret containing a token from Authorino's ServiceAccount for K8s API auth"""
    system_project = cluster.change_project(testconfig["service_protection"]["system_project"])
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
def authorization(cluster, route, blame, module_label, service1_api_secret, sa_token_secret):
    """AuthPolicy injecting the service 1 API key as an Authorization header"""
    auth = AuthPolicy.create_instance(cluster, blame("authz"), route, labels={"app": module_label})
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
def rate_limit():
    """No rate limiting needed for credential injection tests"""
    return None
