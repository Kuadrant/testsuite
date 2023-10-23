"""AuthConfig CR object"""
from typing import Literal, Iterable, TYPE_CHECKING

from testsuite.objects import (
    asdict,
    Rule,
    Cache,
    ABCValue,
    Selector,
    Credentials,
    ValueFrom,
)
from testsuite.openshift.objects import modify

if TYPE_CHECKING:
    from testsuite.openshift.objects.auth_config import AuthConfig


def add_common_features(
    value: dict,
    *,
    priority: int = None,
    when: Iterable[Rule] = None,
    metrics: bool = None,
    cache: Cache = None,
) -> None:
    """Add common features to value dict."""

    if when:
        value["when"] = [asdict(x) for x in when]
    if metrics:
        value["metrics"] = metrics
    if cache:
        value["cache"] = asdict(cache)
    if priority:
        value["priority"] = priority


class Section:
    """Common class for all Sections"""

    def __init__(self, obj: "AuthConfig", section_name) -> None:
        super().__init__()
        self.obj = obj
        self.section_name = section_name

    def modify_and_apply(self, modifier_func, retries=2, cmd_args=None):
        """Reimplementation of modify_and_apply from OpenshiftObject"""

        def _new_modifier(obj):
            modifier_func(self.__class__(obj, self.section_name))

        return self.obj.modify_and_apply(_new_modifier, retries, cmd_args)

    @property
    def committed(self):
        """Reimplementation of commit from OpenshiftObject"""
        return self.obj.committed

    @property
    def section(self):
        """The actual dict section which will be edited"""
        return self.obj.auth_section.setdefault(self.section_name, {})

    def add_item(self, name: str, value: dict, **common_features):
        """Adds item to the section"""
        add_common_features(value, **common_features)
        self.section.update({name: value})

    @modify
    def clear_all(self):
        """Clears content of a Section"""
        self.section.clear()


class IdentitySection(Section):
    """Section which contains identity configuration"""

    def add_item(
        self,
        name,
        value,
        *,
        defaults_properties: dict[str, ABCValue] = None,
        overrides_properties: dict[str, ABCValue] = None,
        **common_features,
    ):
        """
        Adds "defaults" and "overrides" properties for values in AuthJson.
        Properties of "defaults" type are used as default value when none is defined.
        Properties of "overrides" type are overriding any existing value.
        """
        if defaults_properties:
            for key, val in defaults_properties.items():
                value.setdefault("defaults", {}).update({key: asdict(val)})

        if overrides_properties:
            for key, val in overrides_properties.items():
                value.setdefault("overrides", {}).update({key: asdict(val)})

        super().add_item(name, value, **common_features)

    @modify
    def add_mtls(self, name: str, selector: Selector, **common_features):
        """Adds mTLS identity
        Args:
            :param name: name of the identity
            :param selector: selector to match
        """
        self.add_item(name, {"x509": {"selector": asdict(selector)}, **common_features})

    @modify
    def add_kubernetes(self, name: str, audiences: list[str], **common_features):
        """Adds Kubernetes identity
        Args:
            :param name: name of the identity
            :param audiences: token audiences
        """
        self.add_item(name, {"kubernetesTokenReview": {"audiences": audiences}}, **common_features)

    @modify
    def add_oidc(self, name, endpoint, *, credentials: Credentials = None, **common_features):
        """Adds OIDC identity"""
        if credentials is None:
            credentials = Credentials("authorizationHeader", "Bearer")
        self.add_item(name, {"jwt": {"issuerUrl": endpoint}, "credentials": asdict(credentials)}, **common_features)

    @modify
    def add_api_key(
        self,
        name,
        selector: Selector,
        *,
        all_namespaces: bool = False,
        credentials: Credentials = None,
        **common_features,
    ):
        """
        Adds API Key identity
        Args:
            :param name: the name of API key identity
            :param all_namespaces: a location of the API keys can be in another namespace (only works for cluster-wide)
            :param selector: Selector object for API Keys
            :param credentials: locations where credentials are passed
        """
        if credentials is None:
            credentials = Credentials("authorizationHeader", "APIKEY")
        self.add_item(
            name,
            {
                "apiKey": {"selector": asdict(selector), "allNamespaces": all_namespaces},
                "credentials": asdict(credentials),
            },
            **common_features,
        )

    @modify
    def add_anonymous(self, name, **common_features):
        """Adds anonymous identity"""
        self.add_item(name, {"anonymous": {}}, **common_features)

    @modify
    def add_plain(self, name, auth_json, **common_features):
        """Adds plain identity"""
        self.add_item(name, {"plain": asdict(ValueFrom(auth_json))}, **common_features)


class MetadataSection(Section):
    """Section which contains metadata configuration"""

    @modify
    def add_http(self, name, endpoint, method: Literal["GET", "POST"], **common_features):
        """Set metadata http external auth feature"""
        self.add_item(
            name,
            {
                "http": {
                    "url": endpoint,
                    "method": method,
                    "headers": {"Accept": {"value": "application/json"}},
                }
            },
            **common_features,
        )

    @modify
    def add_user_info(self, name, identity_source, **common_features):
        """Set metadata OIDC user info"""
        self.add_item(name, {"userInfo": {"identitySource": identity_source}}, **common_features)

    @modify
    def add_uma(self, name, endpoint, credentials_secret, **common_features):
        """Set metadata feature for resource-level authorization with User-Managed Access (UMA) resource registry"""
        self.add_item(
            name, {"uma": {"endpoint": endpoint, "credentialsRef": {"name": credentials_secret}}}, **common_features
        )


class ResponseSection(Section):
    """Section which contains response configuration. todo envoyDynamicMetadata"""

    @property
    def success_headers(self):
        """Nested dict for most of the section."""
        return self.section.setdefault("success", {}).setdefault("headers", {})

    @modify
    def clear_success_headers(self):
        """Clears content of a success headers"""
        self.success_headers.clear()

    def _add(
        self,
        name: str,
        value: dict,
        **common_features,
    ):
        """Add response to AuthConfig"""
        add_common_features(value, **common_features)
        self.success_headers.update({name: value})

    def add_simple(self, auth_json: str, name="simple", key="data", **common_features):
        """
        Add simple response to AuthConfig, used for configuring response for debugging purposes,
        which can be easily read back using extract_response
        """
        self.add_json(name, {key: ValueFrom(auth_json)}, **common_features)

    @modify
    def add_json(self, name: str, properties: dict[str, ABCValue], **common_features):
        """Adds json response to AuthConfig"""
        asdict_properties = {}
        for key, value in properties.items():
            asdict_properties[key] = asdict(value)
        self._add(name, {"json": {"properties": asdict_properties}}, **common_features)

    @modify
    def add_plain(self, name: str, value: ABCValue, **common_features):
        """Adds plain response to AuthConfig"""
        self._add(name, {"plain": asdict(value)}, **common_features)

    @modify
    def add_wristband(self, name: str, issuer: str, secret_name: str, algorithm: str = "RS256", **common_features):
        """Adds wristband response to AuthConfig"""
        self._add(
            name,
            {
                "wristband": {
                    "issuer": issuer,
                    "signingKeyRefs": [
                        {
                            "name": secret_name,
                            "algorithm": algorithm,
                        }
                    ],
                },
            },
            **common_features,
        )

    @modify
    def set_deny_with(
        self,
        category: Literal["unauthenticated", "unauthorized"],
        code: int = None,
        message: ABCValue = None,
        headers: dict[str, ABCValue] = None,
        body: ABCValue = None,
    ):
        """Set default deny code, message, headers, and body for 'unauthenticated' and 'unauthorized' error."""
        asdict_message = asdict(message) if message else None
        asdict_body = asdict(body) if body else None
        asdict_headers = None
        if headers:
            asdict_headers = {}
            for key, value in headers.items():
                asdict_headers[key] = asdict(value)
        self.add_item(
            category,
            {
                "code": code,
                "message": asdict_message,
                "headers": asdict_headers,
                "body": asdict_body,
            },
        )


class AuthorizationSection(Section):
    """Section which contains authorization configuration"""

    @modify
    def add_auth_rules(self, name, rules: list[Rule], **common_features):
        """Adds JSON pattern-matching authorization rule (authorization.json)"""
        self.add_item(name, {"patternMatching": {"patterns": [asdict(rule) for rule in rules]}}, **common_features)

    def add_role_rule(self, name: str, role: str, path: str, **common_features):
        """
        Adds a rule, which allows access to 'path' only to users with 'role'
        Args:
            :param name: name of rule
            :param role: name of role
            :param path: path to apply this rule to
        """
        rule = Rule("auth.identity.realm_access.roles", "incl", role)
        when = Rule("context.request.http.path", "matches", path)
        common_features.setdefault("when", [])
        common_features["when"].append(when)
        self.add_auth_rules(name, [rule], **common_features)

    @modify
    def add_opa_policy(self, name, inline_rego, **common_features):
        """Adds Opa (https://www.openpolicyagent.org/docs/latest/) policy to the AuthConfig"""
        self.add_item(name, {"opa": {"rego": inline_rego}}, **common_features)

    @modify
    def add_external_opa_policy(self, name, endpoint, ttl=0, **common_features):
        """
        Adds OPA policy that is declared as an HTTP endpoint
        """
        self.add_item(name, {"opa": {"externalPolicy": {"url": endpoint, "ttl": ttl}}}, **common_features)

    @modify
    def add_kubernetes(self, name: str, user: ABCValue, resource_attributes: dict, **common_features):
        """Adds Kubernetes authorization

        :param name: name of kubernetes authorization
        :param user: user in kubernetes authorization
        :param resource_attributes: resource attributes in kubernetes authorization
        """

        self.add_item(
            name,
            {
                "kubernetesSubjectAccessReview": {"user": asdict(user), "resourceAttributes": resource_attributes},
            },
            **common_features,
        )
