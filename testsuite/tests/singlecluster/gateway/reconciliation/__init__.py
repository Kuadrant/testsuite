"""Module containing tests for Reconciliation of MGC policies"""

from testsuite.kuadrant.policy.dns import DNSPolicy


def dns_policy(cluster, name, parent, issuer, labels: dict[str, str] = None):  # pylint: disable=unused-argument
    """DNSPolicy constructor to unify DNSPolicy and TLSPolicy signatures, so they could be parametrized"""
    return DNSPolicy.create_instance(cluster, name, parent, labels=labels)
