"""AuthConfig CR object"""
from dataclasses import dataclass, asdict
from typing import Dict, Literal, List

from testsuite.objects import Authorization
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject, modify


@dataclass
class MatchExpression:
    """
    Data class intended for defining K8 Label Selector expressions.
    Used by selector.matchExpressions API key identity.
    """

    operator: Literal["In", "NotIn", "Exists", "DoesNotExist"]
    values: List[str]
    key: str = "group"


class AuthConfig(OpenShiftObject, Authorization):
    """Represents AuthConfig CR from Authorino"""

    @classmethod
    def create_instance(cls, openshift: OpenShiftClient, name, host, labels: Dict[str, str] = None):
        """Creates base instance"""
        model: Dict = {
            "apiVersion": "authorino.kuadrant.io/v1beta1",
            "kind": "AuthConfig",
            "metadata": {
                "name": name,
                "namespace": openshift.project
            },
            "spec": {
                "hosts": [host]
            }
        }

        if labels is not None:
            model["metadata"]["labels"] = labels

        return cls(model, context=openshift.context)

    @modify
    def add_host(self, hostname):
        self.model.spec.hosts.append(hostname)

    @modify
    def remove_host(self, hostname):
        self.model.spec.hosts.remove(hostname)

    @modify
    def remove_all_hosts(self):
        self.model.spec.hosts = []

    @modify
    def add_oidc_identity(self, name, endpoint):
        """Adds OIDC identity"""
        identities = self.model.spec.setdefault("identity", [])
        identities.append({
            "name": name,
            "oidc": {
                "endpoint": endpoint
            }
        })

    @modify
    def add_api_key_identity(self, name, all_namespaces: bool = False,
                             match_label=None, match_expression: MatchExpression = None):
        """
        Adds API Key identity
        Args:
            :param name: the name of API key identity
            :param all_namespaces: a location of the API keys can be in another namespace (only works for cluster-wide)
            :param match_label: labels that are accepted by AuthConfig
            :param match_expression: instance of the MatchExpression
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

        identities = self.model.spec.setdefault("identity", [])
        identities.append({
            "name": name,
            "apiKey": {
                "selector": matcher,
                "allNamespaces": all_namespaces
            },
            "credentials": {
                "in": "authorization_header",
                "keySelector": "APIKEY"
            }
        })

    @modify
    def add_anonymous_identity(self, name):
        """Adds anonymous identity"""
        identities = self.model.spec.setdefault("identity", [])
        identities.append({"name": name, "anonymous": {}})

    @modify
    def add_role_rule(self, name: str, role: str, path: str, metrics=False, priority=0):
        """
        Adds a rule, which allows access to 'path' only to users with 'role'
        :param name: name of rule
        :param role: name of role
        :param path: path to apply this rule to
        :param metrics: bool, allows metrics
        :param priority: priority of rule
        """
        authorization = self.model.spec.setdefault("authorization", [])
        authorization.append({
            "name": name,
            "metrics": metrics,
            "priority": priority,
            "json": {
                "rules": [{
                    "operator": "incl",
                    "selector": "auth.identity.realm_access.roles",
                    "value": role
                }]
            },
            "when": [{
                "operator": "matches",
                "selector": "context.request.http.path",
                "value": path
            }]
        })

    @modify
    def remove_all_identities(self):
        """Removes all identities from AuthConfig"""
        identities = self.model.spec.setdefault("identity", [])
        identities.clear()

    @modify
    def add_opa_policy(self, name, rego_policy):
        """Adds Opa (https://www.openpolicyagent.org/docs/latest/) policy to the AuthConfig"""
        policy = self.model.spec.setdefault("authorization", [])
        policy.append({
            "name": name,
            "opa": {
                "inlineRego": rego_policy
            }
        })

    @modify
    def add_response(self, response):
        """Adds response section to authconfig."""
        responses = self.model.spec.setdefault("response", [])
        responses.append(response)
