"""
Tests identity verification & authentication with API keys.
Using K8 notation for API key Secret label selector - selector.matchExpressions
https://pkg.go.dev/k8s.io/apimachinery@v0.23.0/pkg/apis/meta/v1#LabelSelector
"""

import pytest

from testsuite.openshift import Selector, MatchExpression


@pytest.fixture(scope="module")
def valid_label_selectors(module_label):
    """Accepted labels for selector.matchExpressions in AuthConfig"""
    return ["test-a", "test-b", module_label, "test-c"]


@pytest.fixture(scope="module")
def authorization(authorization, valid_label_selectors):
    """Creates AuthConfig with API key identity"""
    selector = Selector(matchExpressions=[MatchExpression("In", valid_label_selectors)])
    authorization.identity.add_api_key("api_key", selector=selector)
    return authorization


def test_correct_auth(client, auth):
    """Test request with accepted API key"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200


def test_invalid_api_key(client, invalid_auth):
    """Test request with API key that is not included in selector.matchExpressions"""
    response = client.get("/get", auth=invalid_auth)
    assert response.status_code == 401


def test_no_auth(client):
    """Test request without any authorization header"""
    response = client.get("/get")
    assert response.status_code == 401


def test_not_existing_api_key(client):
    """Test request with API key that is not defined in any Secret"""
    response = client.get("/get", headers={"Authorization": "APIKEY not_existing_key"})
    assert response.status_code == 401
