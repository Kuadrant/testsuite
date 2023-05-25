"""Test for evaluators dependencies resolving according to their priorities"""
import pytest

from testsuite.utils import extract_from_response


@pytest.fixture(scope="module")
def mockserver_expectation(request, mockserver, module_label):
    """Creates Mockserver Expectation which returns request UUID and sent query parameter with previous request UUID"""
    mustache_template = (
        "{ statusCode: 200, body: { 'uuid': '{{ uuid }}', "
        "'prev_uuid': '{{ request.queryStringParameters.prev_uuid.0 }}' } };"
    )
    request.addfinalizer(lambda: mockserver.clear_expectation(module_label))
    return mockserver.create_template_expectation(module_label, mustache_template)


@pytest.fixture(scope="module")
def authorization(authorization, mockserver_expectation):
    """Add to the AuthConfig 2 metadata evaluators with different priorities: latter is dependent on the former"""
    authorization.metadata.http_metadata("first", mockserver_expectation, "GET", priority=0)
    expectation_path_with_prev_uuid_param = mockserver_expectation + "?prev_uuid={auth.metadata.first.uuid}"
    authorization.metadata.http_metadata("second", expectation_path_with_prev_uuid_param, "GET", priority=1)

    return authorization


def test_dependency(client, auth):
    """Test metadata dependency resolving according to it's priority"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200
    metadata = extract_from_response(response)["metadata"]

    first_uuid = metadata["first"]["uuid"]
    second_uuid = metadata["second"]["uuid"]
    prev_uuid = metadata["second"]["prev_uuid"]

    assert first_uuid != second_uuid
    assert first_uuid == prev_uuid
