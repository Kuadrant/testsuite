"""
Test for JWT TTL (time to live), see
https://github.com/Kuadrant/authorino/blob/main/docs/features.md#jwt-verification-authenticationjwt
"""

from time import sleep

import pytest

pytestmark = [pytest.mark.authorino]


def test_jwt_ttl(client, auth, keycloak, create_jwt_auth, jwt_ttl):
    """
    Note that similar test exists also in test_dinosaur.py. If modifying this test update the test there too.

    Test:
        - send request using user with valid middle name
        - assert that response status code is 200
        - delete the signing RS256 key from JWKS - the one associated with the JWT for user with valid middle name
        - assert that response status code is still 200 due to deleted key being cached by Authorino
        - sleep to allow for Authorino to update the cache as part of OIDC discovery
        - assert that response status is 401 after cache update
        - create a new signing RS256 key in JWKS to be used for generating new JWTs
        - generate a new JWT
        - assert that response status code is 200 if using new JWT
        - assert that response status is still 401 for old JWT - ie old JWT does not work with new signing RS256 key

    """
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    # delete the current signing RS256 JWKS key
    keycloak.delete_signing_rs256_jwks_key()

    # 200 OK expected since Authorino should have the deleted JWKS key still cached.
    # Potentially unstable if Authorino triggers OIDC discovery in between the JWKS key deletion just above
    # and the client.get call just below.
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    # Sleeping for jwt_ttl seconds to ensure Authorino triggers the OIDC discovery during the sleep.
    # OIDC discovery detects that the signing RS256 JWKS key has been removed and updates the Authorino cache.
    sleep(jwt_ttl)

    # 401 Unauthorized expected now since JWT is associated with the deleted JWKS key and Authorino cache is up-to-date.
    response = client.get("/get", auth=auth)
    assert response.status_code == 401

    # Create a new signing RS256 JWKS key and add it into JWKS
    keycloak.create_signing_rs256_jwks_key()

    # Generate a new JWT and create an Auth object. This needs to be done only after a new signing JWKS key is added
    # into JWKS hence the Auth object cannot be created via fixture mechanism before the test as usual.
    new_token_auth = create_jwt_auth()

    # 200 OK expected since new JWT (associated with new signing RS256 JWKS key) is used.
    # There is no need to sleep for jwt_ttl seconds because JWKS keys are refreshed regardless the .jwt.ttl value,
    # see https://github.com/Kuadrant/authorino/issues/463
    response = client.get("/get", auth=new_token_auth)
    assert response.status_code == 200

    # Check that old JWT is not re-validated
    # ie that new signing RS256 JWKS key did not make the old JWT work again
    response = client.get("/get", auth=auth)
    assert response.status_code == 401
