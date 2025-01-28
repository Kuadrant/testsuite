"""Test kubernetes SubjectAccessReview authorization by verifying only a
 ServiceAccount bound to a ClusterRole is authorized to access a resource"""

import pytest

pytestmark = [pytest.mark.authorino]


def test_subject_access_review_non_resource_attributes(client, auth, auth2):
    """Test Kubernetes SubjectAccessReview functionality by setting up authentication and authorization for an endpoint
    and querying it with authorized and non-authorized ServiceAccount."""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    response = client.get("/get", auth=auth2)
    assert response.status_code == 403
