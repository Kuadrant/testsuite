"""Test kubernetes SubjectAccessReview non-resource attributes authorization by verifying only a
ServiceAccount bound to a ClusterRole is authorized to access a resource"""

import pytest

from testsuite.kuadrant.policy.authorization import ValueFrom
from testsuite.kubernetes.cluster_role import ClusterRole, Rule

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization):
    """Add kubernetes subject-access-review authorization with non-resource attributes (omit resource_attributes)"""
    authorization.authorization.add_kubernetes(
        "subject-access-review-username", ValueFrom("auth.identity.user.username")
    )
    return authorization


@pytest.fixture(scope="module")
def cluster_role(request, cluster, blame, module_label):
    """Creates and returns a ClusterRole"""
    rules = [Rule(verbs=["get"], nonResourceURLs=["/get"])]
    cluster_role = ClusterRole.create_instance(cluster, blame("cr"), rules, labels={"app": module_label})
    request.addfinalizer(cluster_role.delete)
    cluster_role.commit()
    return cluster_role


def test_subject_access_review_non_resource_attributes(client, auth, auth2):
    """Test Kubernetes SubjectAccessReview functionality by setting up authentication and authorization for an endpoint
    and querying it with authorized and non-authorized ServiceAccount."""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    response = client.get("/get", auth=auth2)
    assert response.status_code == 403
