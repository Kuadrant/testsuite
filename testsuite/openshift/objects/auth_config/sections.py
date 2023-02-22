"""AuthConfig CR object"""
from dataclasses import asdict
from typing import Dict, Literal, Iterable, TYPE_CHECKING

from testsuite.objects import Identities, Metadata, Responses, MatchExpression, Authorizations, Rule, Cache, Value
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
            item["cache"] = cache.to_dict()
        if priority:
            item["priority"] = priority
        self.section.append(item)


class IdentitySection(Section, Identities):
    """Section which contains identity configuration"""

    @modify
    def mtls(self, name: str, selector_key: str, selector_value: str, **common_features):
        """Adds mTLS identity
        Args:
            :param name: name of the identity
            :param selector_key: selector key to match
            :param selector_value: selector value to match
        """
        self.add_item(name, {"mtls": {"selector": {"matchLabels": {selector_key: selector_value}}}}, **common_features)

    @modify
    def oidc(self, name, endpoint, credentials="authorization_header", selector="Bearer", **common_features):
        """Adds OIDC identity"""
        self.add_item(
            name,
            {"oidc": {"endpoint": endpoint}, "credentials": {"in": credentials, "keySelector": selector}},
            **common_features
        )

    @modify
    def api_key(
        self,
        name,
        all_namespaces: bool = False,
        match_label=None,
        match_expression: MatchExpression = None,
        credentials="authorization_header",
        selector="APIKEY",
        **common_features
    ):
        """
        Adds API Key identity
        Args:
            :param name: the name of API key identity
            :param all_namespaces: a location of the API keys can be in another namespace (only works for cluster-wide)
            :param match_label: labels that are accepted by AuthConfig
            :param match_expression: instance of the MatchExpression
            :param credentials: locations where credentials are passed
            :param selector: selector for credentials
        """
        if not (match_label is None) ^ (match_expression is None):
            raise AttributeError("`match_label` xor `match_expression` argument must be used")

        matcher: Dict = {}
        if match_label:
            matcher.update({"matchLabels": {"group": match_label}})

        if match_expression:
            matcher.update({"matchExpressions": [asdict(match_expression)]})

        self.add_item(
            name,
            {
                "apiKey": {"selector": matcher, "allNamespaces": all_namespaces},
                "credentials": {"in": credentials, "keySelector": selector},
            },
            **common_features
        )

    @modify
    def anonymous(self, name, **common_features):
        """Adds anonymous identity"""
        self.add_item(name, {"anonymous": {}}, **common_features)

    @modify
    def kubernetes(self, name, auth_json, **common_features):
        """Adds kubernetes identity"""
        self.add_item(name, {"plain": {"authJSON": auth_json}, **common_features})

    @modify
    def remove_all(self):
        """Removes all identities from AuthConfig"""
        self.section.clear()


class MetadataSection(Section, Metadata):
    """Section which contains metadata configuration"""

    @modify
    def http_metadata(self, name, endpoint, method: Literal["GET", "POST"], **common_features):
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
    def user_info_metadata(self, name, identity_source, **common_features):
        """Set metadata OIDC user info"""
        self.add_item(name, {"userInfo": {"identitySource": identity_source}}, **common_features)

    @modify
    def uma_metadata(self, name, endpoint, credentials, **common_features):
        """Set metadata feature for resource-level authorization with User-Managed Access (UMA) resource registry"""
        self.add_item(name, {"uma": {"endpoint": endpoint, "credentialsRef": {"name": credentials}}}, **common_features)


class ResponsesSection(Section, Responses):
    """Section which contains response configuration"""

    @modify
    def add(self, response, **common_features):
        """Adds response section to AuthConfig."""
        self.add_item(response.pop("name"), response, **common_features)


class AuthorizationsSection(Section, Authorizations):
    """Section which contains authorization configuration"""

    @modify
    def auth_rule(self, name, rule: Rule, **common_features):
        """Adds JSON pattern-matching authorization rule (authorization.json)"""
        section = {"json": {"rules": [asdict(rule)]}}
        self.add_item(name, section, **common_features)

    def role_rule(self, name: str, role: str, path: str, **common_features):
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
        self.auth_rule(name, rule, **common_features)

    @modify
    def opa_policy(self, name, rego_policy, **common_features):
        """Adds Opa (https://www.openpolicyagent.org/docs/latest/) policy to the AuthConfig"""
        self.add_item(name, {"opa": {"inlineRego": rego_policy}}, **common_features)

    @modify
    def external_opa_policy(self, name, endpoint, ttl=0, **common_features):
        """
        Adds OPA policy that is declared as an HTTP endpoint
        """
        self.add_item(name, {"opa": {"externalRegistry": {"endpoint": endpoint, "ttl": ttl}}}, **common_features)

    @modify
    def kubernetes(self, name: str, user: Value, kube_attrs: dict, **common_features):
        """Adds Kubernetes authorization

        :param name: name of kubernetes authorization
        :param user: user in kubernetes authorization
        :param kube_attrs: resource attributes in kubernetes authorization
        """

        self.add_item(
            name,
            {
                "kubernetes": {"user": user.to_dict(), "resourceAttributes": kube_attrs},
            },
            **common_features
        )
