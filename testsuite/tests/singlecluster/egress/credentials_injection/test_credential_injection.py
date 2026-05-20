"""Test: AuthPolicy fetches credentials from Vault and injects them into egress requests.

Replicates the deployment from the user guide:
https://github.com/Kuadrant/kuadrant-operator/blob/main/doc/user-guides/egress/credential-injection.md
"""

import pytest
from dynaconf import ValidationError

from testsuite.gateway import CustomReference, URLRewriteFilter
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.policy import CelExpression, CelPredicate
from testsuite.kuadrant.policy.authorization import NamedValueOrSelector, PlainResponse, ValueOrSelector
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kubernetes.service_account import ServiceAccount
from testsuite.kubernetes.vault import Vault

from ..conftest import EGRESS_HOSTNAME

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.egress_gateway]

VAULT_API_KEY = "pretty-random-api-key-to-use-for-egress-credential-injection-test-41894726"
K8S_TOKEN_AUDIENCE = "https://kubernetes.default.svc.cluster.local"


@pytest.fixture(scope="module")
def service_account(request, cluster, blame, module_label):
    """Unique ServiceAccount per test run for Vault isolation"""
    sa = ServiceAccount.create_instance(cluster, blame("egress-sa"), labels={"app": module_label})
    request.addfinalizer(sa.delete)
    sa.commit()
    return sa


@pytest.fixture(scope="module")
def vault_role(blame):
    """Role name for Vault Kubernetes auth"""
    return blame("egress-wl")


@pytest.fixture(scope="module")
def vault(request, testconfig, cluster, blame, vault_role, service_account, skip_or_fail):
    """Vault client with per-test policy, role, and secret"""
    try:
        testconfig.validators.validate(only="vault")
    except (KeyError, ValidationError) as exc:
        skip_or_fail(f"Vault configuration is missing: {exc}")
    vault = Vault(testconfig["vault"]["url"], testconfig["vault"]["token"])

    policy_name = blame("egress-read")
    vault.create_policy(policy_name, "secret/data/egress/*")
    request.addfinalizer(lambda: vault.delete_policy(policy_name))

    vault.create_role(
        vault_role,
        sa_names=[service_account.name()],
        sa_namespaces=[cluster.project],
        policies=[policy_name],
    )
    request.addfinalizer(lambda: vault.delete_role(vault_role))

    secret_path = f"secret/egress/{cluster.project}/{service_account.name()}"
    vault.store_secret(secret_path, api_key=VAULT_API_KEY)
    request.addfinalizer(lambda: vault.delete_secret(secret_path))

    return vault


@pytest.fixture(scope="module")
def service_account2(request, second_namespace, blame, module_label):
    """ServiceAccount in a different namespace, unauthorized by the Vault role"""
    sa = ServiceAccount.create_instance(second_namespace, blame("egress-sa2"), labels={"app": module_label})
    request.addfinalizer(sa.delete)
    sa.commit()
    return sa


@pytest.fixture(scope="module")
def sa_token(service_account):
    """Service account token with Vault-compatible audience"""
    return service_account.get_auth_token(audiences=[K8S_TOKEN_AUDIENCE])


@pytest.fixture(scope="module")
def sa_token2(service_account2):
    """Token from an unauthorized namespace"""
    return service_account2.get_auth_token(audiences=[K8S_TOKEN_AUDIENCE])


@pytest.fixture(scope="module")
def mockserver_expectation(mockserver_client, module_label):
    """MockServer template: validates Authorization header and echoes it back in a response header"""
    template = """
    {
      "statusCode": #if($request.headers['authorization']
        && $request.headers['authorization'].contains("Bearer %s")) 200 #else 401 #end,
      "headers": {
        "Content-Type": ["text/plain"],
        "authorization": ["$!{request.headers['authorization'].get(0)}"]
      }
    }
    """ % VAULT_API_KEY
    mockserver_client.create_template_expectation(module_label, template, "VELOCITY")
    return f"/{module_label}"


@pytest.fixture(scope="module")
def route(request, gateway, cluster, blame, hostname, module_label, service_entry, destination_rule):
    """HTTPRoute routing egress traffic through the gateway to the backend"""
    # pylint: disable=unused-argument
    route = HTTPRoute.create_instance(cluster, blame("route"), gateway, {"app": module_label})
    route.add_hostname(EGRESS_HOSTNAME)
    route.add_rule(
        CustomReference(group="networking.istio.io", kind="Hostname", name=hostname.hostname, port=443),
        filters=[URLRewriteFilter(hostname=hostname.hostname)],
    )
    request.addfinalizer(route.delete)
    route.commit()
    route.wait_for_ready()
    return route


@pytest.fixture(scope="module")
def authorization(cluster, route, blame, module_label, vault, vault_role):
    """AuthPolicy using Vault for credential injection, replicating the credential-injection user guide"""
    auth = AuthPolicy.create_instance(cluster, blame("authz"), route, labels={"app": module_label})

    auth.identity.add_kubernetes("workload-identity", audiences=[K8S_TOKEN_AUDIENCE])

    auth.metadata.add_http(
        "vault_login",
        f"{vault.url}/v1/auth/kubernetes/login",
        "POST",
        content_type="application/json",
        body=ValueOrSelector(
            CelExpression(
                '"{\\"jwt\\": \\"" + request.headers.authorization.substring(7) + '
                f'"\\", \\"role\\": \\"{vault_role}\\"}}"'
            )
        ),  # CEL produces: '{"jwt": "<token>", "role": "<role>"}'
        priority=0,
    )
    auth.metadata.add_http(
        "vault_secret",
        method="GET",
        url_expression=(
            f'"{vault.url}/v1/secret/data/egress/"'
            " + auth.metadata.vault_login.auth.metadata.service_account_namespace"
            ' + "/" + auth.metadata.vault_login.auth.metadata.service_account_name'
        ),
        headers=[
            NamedValueOrSelector(CelExpression("auth.metadata.vault_login.auth.client_token"), name="X-Vault-Token")
        ],
        priority=1,
    )

    auth.authorization.add_auth_rules(
        "vault_credential_check",
        [CelPredicate("has(auth.metadata.vault_secret.data)")],
    )

    auth.responses.add_success_header(
        "authorization",
        PlainResponse(plain=CelExpression('"Bearer " + auth.metadata.vault_secret.data.data.api_key')),
    )
    return auth


def test_egress_credential_injection_via_vault(client, sa_token, mockserver_expectation):
    """Test that Vault credential is injected and the overwritten header reaches the backend"""
    response = client.get(mockserver_expectation, headers={"Authorization": f"Bearer {sa_token}"})
    assert response.status_code == 200
    assert response.headers["authorization"] == f"Bearer {VAULT_API_KEY}"


def test_egress_unauthorized_namespace_rejected(client, sa_token2, mockserver_expectation):
    """Test that a valid SA token from an unauthorized namespace is rejected by Vault"""
    response = client.get(mockserver_expectation, headers={"Authorization": f"Bearer {sa_token2}"})
    assert response.status_code == 403


def test_egress_invalid_token_rejected(client, mockserver_expectation):
    """Test that requests with an invalid SA token are rejected"""
    response = client.get(mockserver_expectation, headers={"Authorization": "Bearer xyz"})
    assert response.status_code == 401


def test_egress_no_token_rejected(client, mockserver_expectation):
    """Test that requests without a valid SA token are rejected"""
    response = client.get(mockserver_expectation)
    assert response.status_code == 401
