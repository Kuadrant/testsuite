"""Test kubernetes SubjectAccessReview authorization by verifying only a
 ServiceAccount bound to a ClusterRole is authorized to access a resource"""

import pytest

from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kuadrant.policy.authorization import ValueFrom

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization):
    """Add kubernetes token-review and subject-access-review identity"""
    authorization.identity.add_kubernetes("token-review-host")
    user = ValueFrom("auth.identity.user.username")
    authorization.authorization.add_kubernetes("subject-access-review-host", user, None)
    return authorization


@pytest.fixture(scope="module")
def audience(hostname):
    """Return hostname as only audience for the service account bound token"""
    return [hostname.hostname]


@pytest.fixture(scope="module")
def service_account_token(create_service_account, audience):
    """Create a non-authorized service account and request its bound token with the hostname as audience"""
    service_account = create_service_account("tkn-non-auth")
    return service_account.get_auth_token(audience)


@pytest.fixture(scope="module")
def auth2(service_account_token):
    """Create request auth with service account token as API key"""
    return HeaderApiKeyAuth(service_account_token, "Bearer")


def test_host_audience(client, auth, auth2):
    """Test Kubernetes SubjectAccessReview functionality by setting up authentication and authorization for an endpoint
    and querying it with non-authorized and authorized ServiceAccount."""
    response = client.get("/anything/get", auth=auth2)
    assert response.status_code == 403

    response = client.get("/get", auth=auth)
    assert response.status_code == 200
