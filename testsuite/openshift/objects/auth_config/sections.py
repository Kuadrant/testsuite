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
    Property,
)
from testsuite.openshift.objects import modify

if TYPE_CHECKING:
    from testsuite.openshift.objects.auth_config import AuthConfig


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
        return self.obj.auth_section.setdefault(self.section_name, [])

    def add_item(
        self, name, value, priority: int = None, when: Iterable[Rule] = None, metrics: bool = None, cache: Cache = None
    ):
        """Adds item to the section"""
        item = {"name": name, **value}
        if when:
            item["when"] = [asdict(x) for x in when]
        if metrics:
            item["metrics"] = metrics
        if cache:
            item["cache"] = asdict(cache)
        if priority:
            item["priority"] = priority
        self.section.append(item)

    @modify
    def clear_all(self):
        """Removes all identities from AuthConfig"""
        self.section.clear()


class IdentitySection(Section):
    """Section which contains identity configuration"""

    @modify
    def add_mtls(self, name: str, selector: Selector, **common_features):
        """Adds mTLS identity
        Args:
            :param name: name of the identity
            :param selector: selector to match
        """
        self.add_item(name, {"mtls": {"selector": asdict(selector)}, **common_features})

    @modify
    def add_kubernetes(self, name: str, audiences: list[str], **common_features):
        """Adds Kubernetes identity
        Args:
            :param name: name of the identity
            :param audiences: token audiences
        """
        self.add_item(name, {"kubernetes": {"audiences": audiences}}, **common_features)

    @modify
    def add_oidc(self, name, endpoint, *, credentials: Credentials = None, **common_features):
        """Adds OIDC identity"""
        if credentials is None:
            credentials = Credentials("authorization_header", "Bearer")
        self.add_item(name, {"oidc": {"endpoint": endpoint}, "credentials": asdict(credentials)}, **common_features)

    @modify
    def add_api_key(
        self,
        name,
        *,
        all_namespaces: bool = False,
        selector: Selector = None,
        credentials: Credentials = None,
        **common_features
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
            credentials = Credentials("authorization_header", "APIKEY")
        self.add_item(
            name,
            {
                "apiKey": {"selector": asdict(selector), "allNamespaces": all_namespaces},
                "credentials": asdict(credentials),
            },
            **common_features
        )

    @modify
    def add_anonymous(self, name, **common_features):
        """Adds anonymous identity"""
        self.add_item(name, {"anonymous": {}}, **common_features)

    @modify
    def add_plain(self, name, auth_json, **common_features):
        """Adds plain identity"""
        self.add_item(name, {"plain": {"authJSON": auth_json}, **common_features})


class MetadataSection(Section):
    """Section which contains metadata configuration"""

    @modify
    def add_http(self, name, endpoint, method: Literal["GET", "POST"], **common_features):
        """Set metadata http external auth feature"""
        self.add_item(
            name,
            {
                "http": {
                    "endpoint": endpoint,
                    "method": method,
                    "headers": [{"name": "Accept", "value": "application/json"}],
                }
            },
            **common_features
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
    """Section which contains response configuration"""

    def _add(
        self,
        name: str,
        value: dict,
        wrapper_key: str = None,
        wrapper: Literal["httpHeader", "envoyDynamicMetadata"] = None,
        **common_features
    ):
        """Add response to AuthConfig"""
        if wrapper:
            value["wrapper"] = wrapper
        if wrapper_key:
            value["wrapperKey"] = wrapper_key

        self.add_item(name, value, **common_features)

    def add_simple(self, auth_json: str, name="simple", key="data", **common_features):
        """
        Add simple response to AuthConfig, used for configuring response for debugging purposes,
        which can be easily read back using extract_response
        """
        self.add_json(name, [Property(key, ValueFrom(auth_json))], **common_features)

    @modify
    def add_json(self, name: str, properties: list[Property], **common_features):
        """Adds json response to AuthConfig"""
        asdict_properties = [asdict(p) for p in properties]
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
                "name": name,
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
            **common_features
        )


class AuthorizationSection(Section):
    """Section which contains authorization configuration"""

    @modify
    def add_auth_rules(self, name, rules: list[Rule], **common_features):
        """Adds JSON pattern-matching authorization rule (authorization.json)"""
        self.add_item(name, {"json": {"rules": [asdict(rule) for rule in rules]}}, **common_features)

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
        self.add_item(name, {"opa": {"inlineRego": inline_rego}}, **common_features)

    @modify
    def add_external_opa_policy(self, name, endpoint, ttl=0, **common_features):
        """
        Adds OPA policy that is declared as an HTTP endpoint
        """
        self.add_item(name, {"opa": {"externalRegistry": {"endpoint": endpoint, "ttl": ttl}}}, **common_features)

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
                "kubernetes": {"user": asdict(user), "resourceAttributes": resource_attributes},
            },
            **common_features
        )
