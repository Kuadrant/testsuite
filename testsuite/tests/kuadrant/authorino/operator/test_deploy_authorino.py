"""Tests that when you deploy Authorino through operator, when the Authorino CR reports ready, the deployment is too"""


def test_authorino_ready(authorino):
    """Test authorino deploy readiness"""
    status = authorino.deployment.model.status
    assert all(x.status == "True" for x in authorino.model.status.conditions)
    assert "readyReplicas" in status, f"Deployment is not ready: {status}"
