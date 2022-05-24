"""Objects for RHSSO"""
import backoff
from keycloak import KeycloakGetError, KeycloakOpenID

from testsuite.rhsso.objects import RHSSO, Realm, Client


class RHSSOServiceConfiguration:
    """
    Wrapper for all information that tests need to know about RHSSO
    """

    # pylint: disable=too-many-arguments
    def __init__(self, rhsso: RHSSO, realm: Realm, client: Client, user, username, password) -> None:
        self.rhsso = rhsso
        self.realm = realm
        self.user = user
        self.client = client
        self.username = username
        self.password = password
        self._oidc_client = None

    @property
    def oidc_client(self) -> KeycloakOpenID:
        """OIDCClient for the created client"""
        if not self._oidc_client:
            self._oidc_client = self.client.oidc_client
        return self._oidc_client

    def issuer_url(self) -> str:
        """
        Returns issuer url for 3scale in format
        http(s)://<HOST>:<PORT>/auth/realms/<REALM_NAME>
        :return: url
        """
        return self.oidc_client.well_know()["issuer"]

    def jwks_uri(self):
        """
        Returns jwks uri for 3scale in format
        http(s)://<HOST>:<PORT>o/auth/realms/<REALM_NAME>/protocol/openid-connect/certs
        :return: url
        """
        return self.oidc_client.well_know()["jwks_uri"]

    def authorization_url(self) -> str:
        """
        Returns authorization url for 3scale in format
        http(s)://<CLIENT_ID>:<CLIENT_SECRET>@<HOST>:<PORT>/auth/realms/<REALM_NAME>
        :return: url
        """
        url = self.issuer_url()
        client_id = self.oidc_client.client_id
        secret = self.oidc_client.client_secret_key
        return url.replace("://", f"://{client_id}:{secret}@", 1)

    @backoff.on_exception(backoff.fibo, KeycloakGetError, max_tries=8, jitter=None)
    def password_authorize(self, client_id=None, secret=None, username=None, password=None):
        """Returns token retrieved by password authentication"""
        username = username or self.username
        password = password or self.password
        client_id = client_id or self.oidc_client.client_id
        secret = secret or self.oidc_client.client_secret_key
        return self.realm.oidc_client(client_id, secret).token(username, password)

    def token_url(self) -> str:
        """
        Returns token endpoint url
        http(s)://<HOST>:<PORT>/auth/realms/<REALM_NAME>/protocol/openid-connect/token
        :return: url
        """
        return self.oidc_client.well_know()["token_endpoint"]

    def body_for_token_creation(self, app, use_service_accounts=False) -> str:
        """
        Returns body for creation of token
        :return: body
        """
        app_key = app.keys.list()["keys"][0]["key"]["value"]
        app_id = app["client_id"]
        grant_type = "client_credentials" if use_service_accounts else "password"
        user_credentials = "" if use_service_accounts else f"&username={self.username}&password={self.password}"
        return f"grant_type={grant_type}&client_id={app_id}&client_secret={app_key}{user_credentials}"

    def __getstate__(self):
        """
        Custom serializer for pickle module
        more info here: https://docs.python.org/3/library/pickle.html#object.__getstate__
        """
        return {"client": self.client.client_id,
                "realm": self.realm.name,
                "rhsso": {"url": self.rhsso.server_url,
                          "username": self.rhsso.master.username,
                          "password": self.rhsso.master.password},
                "user": self.user,
                "username": self.username,
                "password": self.password}

    def __setstate__(self, state):
        """
        Custom deserializer for pickle module
        more info here: https://docs.python.org/3/library/pickle.html#object.__setstate__
        """
        self.rhsso = RHSSO(server_url=state["rhsso"]["url"],
                           username=state["rhsso"]["username"],
                           password=state["rhsso"]["password"])
        self.realm = Realm(self.rhsso.master, state["realm"])
        self.user = state["user"]
        self.client = Client(self.realm, state["client"])
        self.username = state["username"]
        self.password = state["password"]
        self._oidc_client = self.client.oidc_client
