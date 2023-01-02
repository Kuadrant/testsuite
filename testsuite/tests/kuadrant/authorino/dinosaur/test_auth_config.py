"""
Test for complex AuthConfig
"""

import pytest

ERROR_MESSAGE = {'kind': 'Error', 'id': '403', 'href': '/api/dinosaurs_mgmt/v1/errors/403',
                 'code': 'DINOSAURS-MGMT-403',
                 'reason': 'Forbidden'}


def test_deny_email(client, user_with_invalid_email):
    """
    Test:
        - send request using user with invalid email
        - assert that response status code is 403
    """
    response = client.get("/anything/dinosaurs_mgmt/v1/dinosaurs", auth=user_with_invalid_email)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE


def test_allow_org_id(client, user_with_valid_org_id):
    """
    Test:
        - send request using user with valid middle name
        - assert that response status code is 200
    """
    response = client.get("/anything/dinosaurs_mgmt/v1/dinosaurs", auth=user_with_valid_org_id)
    assert response.status_code == 200


def test_deny_invalid_org_id(client, user_with_invalid_org_id):
    """
    Test:
        - send request using user with invalid middle name
        - assert that response status code is 200
    """
    response = client.get("/anything/dinosaurs_mgmt/v1/dinosaurs", auth=user_with_invalid_org_id)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE


@pytest.mark.parametrize("user", ["user_with_full_role", "user_with_read_role",
                                  "user_with_write_role"])
def test_admin_sso_get(client, user_with_valid_org_id, user, request):
    """
    Test:
        - send request using user without role
        - assert that response status code is 403
        - send request using user with specific role
        - assert that response status code is 200
    """
    auth = request.getfixturevalue(user)
    response = client.get("/anything/dinosaurs_mgmt/v1/admin", auth=user_with_valid_org_id)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE

    response = client.get("/anything/dinosaurs_mgmt/v1/admin", auth=auth)
    assert response.status_code == 200


@pytest.mark.parametrize("user", ["user_with_full_role", "user_with_write_role"])
def test_admin_sso_patch(client, user_with_valid_org_id, user, request):
    """
    Test:
        - send request using user without role
        - assert that response status code is 403
        - send request using user with specific role
        - assert that response status code is 200
    """
    auth = request.getfixturevalue(user)
    response = client.patch("/anything/dinosaurs_mgmt/v1/admin", auth=user_with_valid_org_id)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE

    response = client.patch("/anything/dinosaurs_mgmt/v1/admin", auth=auth)
    assert response.status_code == 200


def test_admin_sso_patch_deny(client, user_with_read_role):
    """
    Test:
        - send request using user with unsupported role
        - assert that response status code is 403
    """
    response = client.patch("/anything/dinosaurs_mgmt/v1/admin", auth=user_with_read_role)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE


def test_admin_sso_delete(client, user_with_valid_org_id, user_with_full_role):
    """
    Test:
        - send request using user without role
        - assert that response status code is 403
        - send request using user with specific role
        - assert that response status code is 200
    """
    response = client.delete("/anything/dinosaurs_mgmt/v1/admin", auth=user_with_valid_org_id)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE

    response = client.delete("/anything/dinosaurs_mgmt/v1/admin", auth=user_with_full_role)
    assert response.status_code == 200


@pytest.mark.parametrize("user", ["user_with_read_role", "user_with_write_role"])
def test_admin_sso_delete_deny(client, user, request):
    """
    Test:
        - send request using user with unsupported role
        - assert that response status code is 403
    """
    auth = request.getfixturevalue(user)
    response = client.delete("/anything/dinosaurs_mgmt/v1/admin", auth=auth)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE


def test_authz(client, user_with_valid_org_id):
    """
    Test:
        - send request to internal authz-metadata endpoint
        - assert that response status code is 403
    """
    response = client.get("/anything/dinosaurs_mgmt/v1/authz-metadata", auth=user_with_valid_org_id)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE


def test_create(client, user_with_valid_org_id, terms_and_conditions):
    """
    Test:
        - send request to dinosaurs endpoint that doesn't request terms and conditions
        - assert that response status code is 200
        - send request to dinosaurs endpoint that does request terms and conditions
        - assert that response status code is 403
    """
    terms_and_conditions("false")
    response = client.post("/anything/dinosaurs_mgmt/v1/dinosaurs", auth=user_with_valid_org_id)
    assert response.status_code == 200

    terms_and_conditions("true")
    response = client.post("/anything/dinosaurs_mgmt/v1/dinosaurs", auth=user_with_valid_org_id)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE


def test_metrics_federate(client, user_with_valid_org_id, user_with_invalid_org_id):
    """
    Test:
        - send request to metrics endpoint using user with valid middle name
        - assert that response status code is 200
        - send request to metrics endpoint using user with invalid middle name
        - assert that response status code is 403
    """
    response = client.get("/anything/dinosaurs_mgmt/v1/dinosaurs/metrics/federate", auth=user_with_valid_org_id)
    assert response.status_code == 200

    response = client.get("/anything/dinosaurs_mgmt/v1/dinosaurs/metrics/federate", auth=user_with_invalid_org_id)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE


def test_service_accounts(client, user_with_valid_org_id, user_with_invalid_org_id):
    """
    Test:
        - send request to service accounts endpoint using user with valid middle name
        - assert that response status code is 200
        - send request to service accounts endpoint using user with invalid middle name
        - assert that response status code is 403
    """
    response = client.get("/anything/dinosaurs_mgmt/v1/service_accounts", auth=user_with_valid_org_id)
    assert response.status_code == 200

    response = client.get("/anything/dinosaurs_mgmt/v1/service_accounts", auth=user_with_invalid_org_id)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE


def test_instance_types(client, user_with_valid_org_id, user_with_invalid_org_id):
    """
    Test:
        - send request to instance types endpoint using user with valid middle name
        - assert that response status code is 200
        - send request to instance types endpoint using user with invalid middle name
        - assert that response status code is 403
    """
    response = client.get("/anything/dinosaurs_mgmt/v1/instance_types", auth=user_with_valid_org_id)
    assert response.status_code == 200

    response = client.get("/anything/dinosaurs_mgmt/v1/instance_types", auth=user_with_invalid_org_id)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE


def test_agent_clusters(client, user_with_valid_org_id, rhsso, cluster_info):
    """
    Test:
        - send request to agent clusters endpoint with valid cluster info
        - assert that response status code is 200
        - send request to agent clusters endpoint with invalid cluster info
        - assert that response status code is 403
    """
    cluster_info(rhsso.client_name)
    response = client.get("/anything/dinosaurs_mgmt/v1/agent-clusters", auth=user_with_valid_org_id)
    assert response.status_code == 200

    cluster_info("invalid")
    response = client.get("/anything/dinosaurs_mgmt/v1/agent-clusters", auth=user_with_valid_org_id)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE


def test_resource_is_owner(client, user_with_valid_org_id, resource_info, rhsso):
    """
    Test:
        - set resource info to valid middle name
        - send requests (GET, DELETE and POST) to dinosaur resource using user with valid midlle name
        - assert that response status code is 200
    """
    resource_info("123", rhsso.client_name)

    response = client.get("/anything/dinosaurs_mgmt/v1/dinosaurs/123", auth=user_with_valid_org_id)
    assert response.status_code == 200

    response = client.delete("/anything/dinosaurs_mgmt/v1/dinosaurs/123", auth=user_with_valid_org_id)
    assert response.status_code == 200

    response = client.patch("/anything/dinosaurs_mgmt/v1/dinosaurs/123", auth=user_with_valid_org_id)
    assert response.status_code == 200


def test_resource_is_not_owner_client_denied(client, user_with_invalid_email, resource_info, rhsso):
    """
    Test:
        - set resource info to valid middle name
        - send requests (GET, DELETE and POST) to dinosaur resource using user with invalid midlle name
        - assert that response status code is 403
    """
    resource_info("123", rhsso.client_name)

    response = client.get("/anything/dinosaurs_mgmt/v1/dinosaurs/123", auth=user_with_invalid_email)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE

    response = client.delete("/anything/dinosaurs_mgmt/v1/dinosaurs/123", auth=user_with_invalid_email)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE

    response = client.patch("/anything/dinosaurs_mgmt/v1/dinosaurs/123", auth=user_with_invalid_email)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE


def test_resource_is_not_owner_resource_denied(client, user_with_valid_org_id, resource_info, rhsso):
    """
    Test:
        - set resource info to invalid middle name
        - send requests (GET, DELETE and POST) to dinosaur resource using user with valid midlle name
        - assert that response status code is 403
    """
    resource_info("321", rhsso.client_name)

    response = client.get("/anything/dinosaurs_mgmt/v1/dinosaurs/123", auth=user_with_valid_org_id)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE

    response = client.delete("/anything/dinosaurs_mgmt/v1/dinosaurs/123", auth=user_with_valid_org_id)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE

    response = client.patch("/anything/dinosaurs_mgmt/v1/dinosaurs/123", auth=user_with_valid_org_id)
    assert response.status_code == 403
    assert response.json() == ERROR_MESSAGE
