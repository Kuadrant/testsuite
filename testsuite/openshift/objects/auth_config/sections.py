"""AuthConfig CR object"""
from dataclasses import asdict
from typing import Dict, Literal

from testsuite.objects import Identities, Metadata, Responses, MatchExpression, Authorizations, Rule
from testsuite.openshift.objects import OpenShiftObject, modify


class Section:
    """Common class for all Sections"""
    def __init__(self, obj: OpenShiftObject, section_name) -> None:
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
        return self.obj.model.spec.setdefault(self.section_name, [])

    def add_item(self, name, value):
        """Adds item to the section"""
        self.section.append({"name": name, **value})


class IdentitySection(Section, Identities):
    """Section which contains identity configuration"""

    @modify
    def mtls(self, name: str, selector_key: str, selector_value: str):
        """Adds mTLS identity
        Args:
            :param name: name of the identity
            :param selector_key: selector key to match
            :param selector_value: selector value to match
        """
        self.add_item(name, {
            "mtls": {
                "selector": {
                    "matchLabels": {
                        selector_key: selector_value
                    }
                }
            }
        })

    @modify
    def oidc(self, name, endpoint, credentials="authorization_header", selector="Bearer"):
        """Adds OIDC identity"""
        self.add_item(name, {
            "oidc": {
                "endpoint": endpoint
            },
            "credentials": {
                "in": credentials,
                "keySelector": selector
            }
        })

    @modify
    def api_key(self, name, all_namespaces: bool = False,
                match_label=None, match_expression: MatchExpression = None,
                credentials="authorization_header", selector="APIKEY"):
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
            matcher.update({
                "matchLabels": {
                    "group": match_label
                }
            })

        if match_expression:
            matcher.update({
                "matchExpressions": [asdict(match_expression)]
            })

        self.add_item(name, {
            "apiKey": {
                "selector": matcher,
                "allNamespaces": all_namespaces
            },
            "credentials": {
                "in": credentials,
                "keySelector": selector
            }
        })

    @modify
    def anonymous(self, name):
        """Adds anonymous identity"""
        self.add_item(name, {"anonymous": {}})

    @modify
    def remove_all(self):
        """Removes all identities from AuthConfig"""
        self.section.clear()


class MetadataSection(Section, Metadata):
    """Section which contains metadata configuration"""
    @modify
    def http_metadata(self, name, endpoint, method: Literal["GET", "POST"]):
        self.add_item(name, {
            "http": {
                "endpoint": endpoint,
                "method": method,
                "headers": [{"name": "Accept", "value": "application/json"}]
            }
        })

    @modify
    def user_info_metadata(self, name, identity_source):
        self.add_item(name, {
            "userInfo": {
                "identitySource": identity_source
            }
        })


class ResponsesSection(Section, Responses):
    """Section which contains response configuration"""

    @modify
    def add(self, response):
        """Adds response section to AuthConfig."""
        self.add_item(response.pop("name"), response)


class AuthorizationsSection(Section, Authorizations):
    """Section which contains authorization configuration"""

    @modify
    def auth_rule(self, name, rule: Rule, when: Rule = None, metrics=False, priority=0):
        """Adds JSON pattern-matching authorization rule (authorization.json)"""
        section = {
            "metrics": metrics,
            "priority": priority,
            "json": {
                "rules": [asdict(rule)]
            }
        }
        if when:
            section["when"] = [asdict(when)]
        self.add_item(name, section)

    def role_rule(self, name: str, role: str, path: str, metrics=False, priority=0):
        """
        Adds a rule, which allows access to 'path' only to users with 'role'
        Args:
            :param name: name of rule
            :param role: name of role
            :param path: path to apply this rule to
            :param metrics: bool, allows metrics
            :param priority: priority of rule
        """
        rule = Rule("auth.identity.realm_access.roles", "incl", role)
        when = Rule("context.request.http.path", "matches", path)
        self.auth_rule(name, rule, when, metrics, priority)

    @modify
    def opa_policy(self, name, rego_policy):
        """Adds Opa (https://www.openpolicyagent.org/docs/latest/) policy to the AuthConfig"""
        self.add_item(name, {
            "opa": {
                "inlineRego": rego_policy
            }
        })

    @modify
    def external_opa_policy(self, name, endpoint, ttl=0):
        """
        Adds OPA policy that is declared as an HTTP endpoint
        """
        self.add_item(name, {
            "opa": {
                "externalRegistry": {
                    "endpoint": endpoint,
                    "ttl": ttl
                }
            }
        })
