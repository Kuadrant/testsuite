"""AuthConfig CR object"""
from dataclasses import asdict
from typing import Dict, Literal

from testsuite.objects import Authorization, Rule, MatchExpression
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject, modify


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
    def add_oidc_identity(self, name, endpoint, credentials="authorization_header", selector="Bearer"):
        """Adds OIDC identity"""
        identities = self.model.spec.setdefault("identity", [])
        identities.append({
            "name": name,
            "oidc": {
                "endpoint": endpoint
            },
            "credentials": {
                "in": credentials,
                "keySelector": selector
            }
        })

    @modify
    def add_api_key_identity(self, name, all_namespaces: bool = False,
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

        identities = self.model.spec.setdefault("identity", [])
        identities.append({
            "name": name,
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
    def add_anonymous_identity(self, name):
        """Adds anonymous identity"""
        identities = self.model.spec.setdefault("identity", [])
        identities.append({"name": name, "anonymous": {}})

    @modify
    def add_auth_rule(self, name, rule: Rule, when: Rule = None, metrics=False, priority=0):
        """Adds JSON pattern-matching authorization rule (authorization.json)"""
        authorization = self.model.spec.setdefault("authorization", [])
        authorization.append({
            "name": name,
            "metrics": metrics,
            "priority": priority,
            "json": {
                "rules": [asdict(rule)]
            }
        })
        if when:
            authorization[0].update({"when": [asdict(when)]})

    def add_role_rule(self, name: str, role: str, path: str, metrics=False, priority=0):
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
        self.add_auth_rule(name, rule, when, metrics, priority)

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
    def add_external_opa_policy(self, name, endpoint, ttl=0):
        """
        Adds OPA policy that is declared as an HTTP endpoint
        """
        policy = self.model.spec.setdefault("authorization", [])
        policy.append({
            "name": name,
            "opa": {
                "externalRegistry": {
                    "endpoint": endpoint,
                    "ttl": ttl
                }
            }
        })

    @modify
    def add_response(self, response):
        """Adds response section to AuthConfig."""
        responses = self.model.spec.setdefault("response", [])
        responses.append(response)

    @modify
    def set_deny_with(self, code, value):
        """Set denyWith to authconfig"""
        self.model.spec["denyWith"] = {
            "unauthenticated": {"code": code, "headers": [{"name": "Location", "valueFrom": {"authJSON": value}}]}}

    @modify
    def add_http_metadata(self, name, endpoint, method: Literal["GET", "POST"]):
        """"Set metadata http external auth feature"""
        metadata = self.model.spec.setdefault("metadata", [])
        metadata.append({
            "name": name,
            "http": {
                "endpoint": endpoint,
                "method": method,
                "headers": [{"name": "Accept", "value": "application/json"}]
            }
        })

    @modify
    def add_user_info_metadata(self, name, identity_source):
        """Set metadata OIDC user info"""
        metadata = self.model.spec.setdefault("metadata", [])
        metadata.append({
            "name": name,
            "userInfo": {
                "identitySource": identity_source
            }
        })
