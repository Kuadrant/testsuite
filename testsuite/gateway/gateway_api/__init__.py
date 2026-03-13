"""Gateway API implementation"""

from enum import Enum


class GatewayAPIKind(str, Enum):
    """Gateway API resource kinds."""

    GATEWAY = "Gateway"
    HTTPROUTE = "HTTPRoute"
    GRPCROUTE = "GRPCRoute"


class PolicyKind(str, Enum):
    """Kuadrant policy kinds (core + extensions)."""

    # Core policies
    AUTH_POLICY = "AuthPolicy"
    RATE_LIMIT_POLICY = "RateLimitPolicy"
    DNS_POLICY = "DNSPolicy"
    TLS_POLICY = "TLSPolicy"

    # Extension policies
    OIDC_POLICY = "OIDCPolicy"
    PLAN_POLICY = "PlanPolicy"
    TELEMETRY_POLICY = "TelemetryPolicy"
