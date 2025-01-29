"""Test kubernetes SubjectAccessReview with resource attributes"""

import pytest

from testsuite.kuadrant.policy import CelExpression
from testsuite.kuadrant.policy.authorization import ValueFrom, Value, ResourceAttributes
from testsuite.kubernetes.cluster_role import ClusterRole, Rule

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization):
    """Add kubernetes subject-access-review identity with resource attributes for authpolicy resource"""
    authorization.authorization.add_kubernetes(
        "subject-access-review-host",
        ValueFrom("auth.identity.user.username"),
        ResourceAttributes(
            resource=Value("authpolicy"), group=Value("kuadrant.io"), verb=CelExpression("request.method.lowerAscii()")
        ),
    )
    return authorization


@pytest.fixture(scope="module")
def cluster_role(request, cluster, blame, module_label):
    """Creates ClusterRole with rules only for accessing authpolicy resource"""
    rules = [Rule(verbs=["get"], resources=["authpolicy"], apiGroups=["kuadrant.io"])]
    cluster_role = ClusterRole.create_instance(cluster, blame("cr"), rules, labels={"app": module_label})
    request.addfinalizer(cluster_role.delete)
    cluster_role.commit()
    return cluster_role


def test_subject_access_review_resource_attributes(client, auth, auth2):
    """Test if the client is authorized to access the api based on the service account token resource attributes"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    response = client.post("/post", auth=auth)
    assert response.status_code == 403

    response = client.get("/get", auth=auth2)
    assert response.status_code == 403
