"""Basic tests for extended properties"""

import pytest

from testsuite.policy.authorization import Value, ValueFrom
from testsuite.utils import extract_response

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization, rhsso):
    """
    Add new identity with list of extended properties. This list contains:
        - Static `value` and dynamic `jsonPath` properties
        - Dynamic chaining properties which point to another extended property location before its created
    Add simple response to inspect 'auth.identity' part of authJson where the properties will be created.
    """
    authorization.identity.add_oidc(
        "rhsso",
        rhsso.well_known["issuer"],
        defaults_properties={
            "property_static": Value("static"),
            "property_dynamic": ValueFrom("context.request.http.path"),
            "property_chain_static": ValueFrom("auth.identity.property_static"),
            "property_chain_dynamic": ValueFrom("auth.identity.property_dynamic"),
        },
        overrides_properties={
            "property_chain_self": ValueFrom("auth.identity.property_chain_self"),
        },
    )
    authorization.responses.add_simple("auth.identity")
    return authorization


def test_basic(client, auth):
    """
    This test checks if static and dynamic extended properties are created and have the right value.
    """
    response = client.get("/anything/abc", auth=auth)
    assert extract_response(response)["property_static"] % "MISSING" == "static"
    assert extract_response(response)["property_dynamic"] % "MISSING" == "/anything/abc"


def test_chain(client, auth):
    """
    This test checks if chaining extended properties have value None as chaining is not supported.
    This behavior is undocumented but confirmed to be correct with dev team.
    """
    response = client.get("/anything/abc", auth=auth)
    assert extract_response(response)["property_chain_static"] % "MISSING" is None
    assert extract_response(response)["property_chain_dynamic"] % "MISSING" is None
    assert extract_response(response)["property_chain_self"] % "MISSING" is None
