"""Gateway API Topology Registry for tracking resources and their relationships"""

from typing import Optional, List, Dict, Set, Callable
from enum import Enum
from functools import wraps
import pytest

from testsuite.gateway import Gateway

# Global singleton instance
_global_topology_registry: Optional['TopologyRegistry'] = None


class ResourceKind(Enum):
    """Gateway API resource kinds"""
    GATEWAY = "Gateway"
    HTTPROUTE = "HTTPRoute"
    AUTH_POLICY = "AuthPolicy"
    RATE_LIMIT_POLICY = "RateLimitPolicy"
    DNS_POLICY = "DNSPolicy"
    TLS_POLICY = "TLSPolicy"


class TopologyNode:
    """Represents a node in the Gateway API topology graph"""

    def __init__(self, kind: ResourceKind, resource, name: str):
        self.kind = kind
        self.resource = resource  # The actual Gateway/Route/Policy object
        self.name = name
        self.targets: Set[str] = set()  # Resources this node targets
        self.targeted_by: Set[str] = set()  # Resources targeting this node
        self.children: Set[str] = set()  # Child resources (e.g., routes for a gateway)
        self.parent: Optional[str] = None  # Parent resource
        self.metadata: Dict = {}  # Arbitrary metadata storage

    def __repr__(self):
        return f"TopologyNode({self.kind.value}, {self.name})"


def get_topology() -> Optional['TopologyRegistry']:
    """
    Get the global topology registry instance.

    Returns:
        The global TopologyRegistry instance, or None if not initialized

    Usage:
        from testsuite.gateway.topology import get_topology

        topology = get_topology()
        if topology:
            gateway = topology.get_gateway_for_policy(policy)
    """
    return _global_topology_registry


def set_topology(registry: 'TopologyRegistry') -> None:
    """
    Set the global topology registry instance.

    This is typically called once by the session-scoped topology fixture.

    Args:
        registry: The TopologyRegistry instance to use globally
    """
    global _global_topology_registry
    _global_topology_registry = registry


def clear_topology() -> None:
    """Clear the global topology registry"""
    global _global_topology_registry
    if _global_topology_registry:
        _global_topology_registry.clear()
    _global_topology_registry = None


class TopologyRegistry:
    """
    Central registry for Gateway API topology and policies.

    Tracks resources and their relationships:
    - Gateway -> HTTPRoutes (children)
    - HTTPRoute -> Gateway (parent)
    - Policy -> Gateway/HTTPRoute (targets)
    - Gateway/HTTPRoute -> Policies (targeted_by)

    Usage:
        topology = TopologyRegistry()

        # Register resources
        topology.register_gateway(gateway)
        topology.register_route(route, gateway_name="my-gateway")
        topology.register_policy(auth_policy)

        # Query relationships
        gateway = topology.get_gateway_for_policy(policy)
        routes = topology.get_routes_for_gateway("my-gateway")
        policies = topology.get_policies_for_gateway("my-gateway")

        # Traverse
        topology.print_topology()
    """

    def __init__(self):
        self.nodes: Dict[str, TopologyNode] = {}  # name -> TopologyNode

    def _get_or_create_node(self, kind: ResourceKind, resource, name: str) -> TopologyNode:
        """Get existing node or create new one"""
        if name not in self.nodes:
            self.nodes[name] = TopologyNode(kind, resource, name)
        else:
            # Update resource reference if it exists (but don't overwrite with None)
            if resource is not None:
                self.nodes[name].resource = resource
            if kind is not None:
                self.nodes[name].kind = kind
        return self.nodes[name]

    def register_gateway(self, gateway):
        """Register a Gateway"""
        name = gateway.name()
        node = self._get_or_create_node(ResourceKind.GATEWAY, gateway, name)
        return node

    def register_route(self, route, gateway_name: Optional[str] = None):
        """
        Register an HTTPRoute

        Args:
            route: The HTTPRoute object
            gateway_name: Optional explicit gateway name. If not provided, will try route.gateway.name()
        """
        name = route.name()
        node = self._get_or_create_node(ResourceKind.HTTPROUTE, route, name)

        # Determine gateway
        if not gateway_name and hasattr(route, "gateway"):
            gateway_name = route.gateway.name()

        if gateway_name:
            # Create relationship
            node.parent = gateway_name
            gateway_node = self._get_or_create_node(ResourceKind.GATEWAY, None, gateway_name)
            gateway_node.children.add(name)

        return node

    def register_policy(self, policy):
        """
        Register a policy (AuthPolicy, RateLimitPolicy, etc.)

        Automatically determines the kind and target relationship
        """
        try:
            # Get policy name (works even if not committed)
            name = policy.name()
        except Exception:  # pylint: disable=broad-except
            # If name() fails, try to get it from the model
            name = policy.model.metadata.name

        kind_map = {
            "AuthPolicy": ResourceKind.AUTH_POLICY,
            "RateLimitPolicy": ResourceKind.RATE_LIMIT_POLICY,
            "DNSPolicy": ResourceKind.DNS_POLICY,
            "TLSPolicy": ResourceKind.TLS_POLICY,
        }

        try:
            policy_kind_str = policy.kind(lowercase=False)
        except Exception:  # pylint: disable=broad-except
            policy_kind_str = policy.model.kind

        kind = kind_map.get(policy_kind_str, ResourceKind.AUTH_POLICY)

        node = self._get_or_create_node(kind, policy, name)

        # Determine target (use model directly to avoid property access)
        if hasattr(policy.model.spec, "targetRef"):
            target_ref = policy.model.spec.targetRef
            target_name = target_ref.name
            target_kind = target_ref.kind

            # Create relationship
            node.targets.add(target_name)

            # Create or update target node
            if target_kind == "Gateway":
                target_node = self._get_or_create_node(ResourceKind.GATEWAY, None, target_name)
            elif target_kind == "HTTPRoute":
                target_node = self._get_or_create_node(ResourceKind.HTTPROUTE, None, target_name)
            else:
                # Unknown target kind, create generic node
                target_node = self.nodes.setdefault(target_name, TopologyNode(None, None, target_name))

            target_node.targeted_by.add(name)

        return node

    def get_node(self, name: str) -> Optional[TopologyNode]:
        """Get a node by name"""
        return self.nodes.get(name)

    def get_resource(self, name: str):
        """Get the actual resource object by name"""
        node = self.get_node(name)
        return node.resource if node else None

    def get_gateway(self, name: str):
        """Get a Gateway resource by name"""
        node = self.get_node(name)
        return node.resource if node and node.kind == ResourceKind.GATEWAY else None

    def get_route(self, name: str):
        """Get an HTTPRoute resource by name"""
        node = self.get_node(name)
        return node.resource if node and node.kind == ResourceKind.HTTPROUTE else None

    def get_gateway_for_policy(self, policy) -> Gateway:
        """
        Get the Gateway associated with a policy.

        If policy targets HTTPRoute, returns the route's parent gateway.
        If policy targets Gateway, returns that gateway.
        """
        policy_name = policy.name()
        policy_node = self.get_node(policy_name)

        if not policy_node or not policy_node.targets:
            return None

        # Get first target (policies typically have one target)
        target_name = next(iter(policy_node.targets))
        target_node = self.get_node(target_name)

        if not target_node:
            return None

        if target_node.kind == ResourceKind.GATEWAY:
            return target_node.resource
        elif target_node.kind == ResourceKind.HTTPROUTE:
            # Get parent gateway
            if target_node.parent:
                gateway_node = self.get_node(target_node.parent)
                return gateway_node.resource if gateway_node else None

        return None

    def get_gateway_for_target_ref(self, target_ref):
        """
        Get the Gateway for a given targetRef (before policy is registered).

        Args:
            target_ref: The targetRef object with .name and .kind attributes

        Returns:
            Gateway resource, or None if not found
        """
        target_name = target_ref.name
        target_kind = target_ref.kind

        if target_kind == "Gateway":
            # Direct gateway target
            return self.get_gateway(target_name)
        elif target_kind == "HTTPRoute":
            # Route target - get parent gateway
            route_node = self.get_node(target_name)
            if route_node and route_node.parent:
                return self.get_gateway(route_node.parent)

        return None

    def get_routes_for_gateway(self, gateway_name: str) -> List:
        """Get all HTTPRoutes attached to a gateway"""
        gateway_node = self.get_node(gateway_name)
        if not gateway_node:
            return []

        routes = []
        for child_name in gateway_node.children:
            child_node = self.get_node(child_name)
            if child_node and child_node.kind == ResourceKind.HTTPROUTE and child_node.resource:
                routes.append(child_node.resource)
        return routes

    def get_policies_for_gateway(self, gateway_name: str, policy_kind: Optional[ResourceKind] = None) -> List:
        """
        Get all policies targeting a gateway (directly or via routes).

        Args:
            gateway_name: Gateway name
            policy_kind: Optional filter by policy kind (e.g., ResourceKind.AUTH_POLICY)
        """
        gateway_node = self.get_node(gateway_name)
        if not gateway_node:
            return []

        policies = []

        # Direct policies on gateway
        for policy_name in gateway_node.targeted_by:
            policy_node = self.get_node(policy_name)
            if policy_node and policy_node.resource:
                if not policy_kind or policy_node.kind == policy_kind:
                    policies.append(policy_node.resource)

        # Policies on child routes
        for child_name in gateway_node.children:
            child_node = self.get_node(child_name)
            if child_node and child_node.kind == ResourceKind.HTTPROUTE:
                for policy_name in child_node.targeted_by:
                    policy_node = self.get_node(policy_name)
                    if policy_node and policy_node.resource:
                        if not policy_kind or policy_node.kind == policy_kind:
                            policies.append(policy_node.resource)

        return policies

    def get_policies_for_route(self, route_name: str, policy_kind: Optional[ResourceKind] = None) -> List:
        """Get all policies targeting a specific route"""
        route_node = self.get_node(route_name)
        if not route_node:
            return []

        policies = []
        for policy_name in route_node.targeted_by:
            policy_node = self.get_node(policy_name)
            if policy_node and policy_node.resource:
                if not policy_kind or policy_node.kind == policy_kind:
                    policies.append(policy_node.resource)
        return policies

    def get_all_gateways(self) -> List:
        """Get all registered gateways"""
        return [node.resource for node in self.nodes.values()
                if node.kind == ResourceKind.GATEWAY and node.resource]

    def get_all_routes(self) -> List:
        """Get all registered routes"""
        return [node.resource for node in self.nodes.values()
                if node.kind == ResourceKind.HTTPROUTE and node.resource]

    def get_all_policies(self, policy_kind: Optional[ResourceKind] = None) -> List:
        """Get all registered policies, optionally filtered by kind"""
        policy_kinds = {ResourceKind.AUTH_POLICY, ResourceKind.RATE_LIMIT_POLICY,
                       ResourceKind.DNS_POLICY, ResourceKind.TLS_POLICY}

        return [node.resource for node in self.nodes.values()
                if node.kind in policy_kinds and node.resource and
                (not policy_kind or node.kind == policy_kind)]

    def print_topology(self, indent=0):
        """Print a human-readable topology tree"""
        # Start with gateways (top-level)
        gateways = [node for node in self.nodes.values() if node.kind == ResourceKind.GATEWAY]

        for gw_node in gateways:
            print("  " * indent + f"🌐 Gateway: {gw_node.name}")

            # Show policies targeting gateway
            for policy_name in gw_node.targeted_by:
                policy_node = self.get_node(policy_name)
                if policy_node:
                    print("  " * (indent + 1) + f"📋 {policy_node.kind.value}: {policy_node.name}")

            # Show child routes
            for route_name in gw_node.children:
                route_node = self.get_node(route_name)
                if route_node:
                    print("  " * (indent + 1) + f"🛤️  HTTPRoute: {route_node.name}")

                    # Show policies targeting route
                    for policy_name in route_node.targeted_by:
                        policy_node = self.get_node(policy_name)
                        if policy_node:
                            print("  " * (indent + 2) + f"📋 {policy_node.kind.value}: {policy_node.name}")

        # Show orphaned routes (no parent gateway)
        orphan_routes = [node for node in self.nodes.values()
                        if node.kind == ResourceKind.HTTPROUTE and not node.parent]
        if orphan_routes:
            print("  " * indent + "⚠️  Orphaned Routes:")
            for route_node in orphan_routes:
                print("  " * (indent + 1) + f"🛤️  {route_node.name}")

        # Show orphaned policies (no target)
        orphan_policies = [node for node in self.nodes.values()
                          if node.kind in {ResourceKind.AUTH_POLICY, ResourceKind.RATE_LIMIT_POLICY,
                                          ResourceKind.DNS_POLICY, ResourceKind.TLS_POLICY}
                          and not node.targets]
        if orphan_policies:
            print("  " * indent + "⚠️  Orphaned Policies:")
            for policy_node in orphan_policies:
                print("  " * (indent + 1) + f"📋 {policy_node.kind.value}: {policy_node.name}")

    def set_policy_metadata(self, policy, key: str, value):
        """
        Store metadata for a policy.

        Args:
            policy: The policy object
            key: Metadata key
            value: Metadata value
        """
        policy_name = policy.name()
        policy_node = self.get_node(policy_name)
        if policy_node:
            policy_node.metadata[key] = value

    def get_policy_metadata(self, policy, key: str, default=None):
        """
        Retrieve metadata for a policy.

        Args:
            policy: The policy object
            key: Metadata key
            default: Default value if key not found

        Returns:
            The metadata value, or default if not found
        """
        policy_name = policy.name()
        policy_node = self.get_node(policy_name)
        if policy_node:
            return policy_node.metadata.get(key, default)
        return default

    def set_gateway_metric(self, gateway_name: str, metric_value: float, key: str = 'kuadrant_configs_metric'):
        """
        Store a metric value in a gateway's metadata.

        Args:
            gateway_name: Gateway name
            metric_value: The metric value to store
            key: Metadata key (default: 'kuadrant_configs_metric')
        """
        gateway_node = self.get_node(gateway_name)
        if gateway_node and gateway_node.kind == ResourceKind.GATEWAY:
            gateway_node.metadata[key] = metric_value

    def get_gateway_metric(self, gateway_name: str, key: str = 'kuadrant_configs_metric', default=None):
        """
        Retrieve a metric value from a gateway's metadata.

        Args:
            gateway_name: Gateway name
            key: Metadata key (default: 'kuadrant_configs_metric')
            default: Default value if not found

        Returns:
            The stored metric value, or default if not found
        """
        gateway_node = self.get_node(gateway_name)
        if gateway_node and gateway_node.kind == ResourceKind.GATEWAY:
            return gateway_node.metadata.get(key, default)
        return default

    def capture_gateway_metric(self, gateway):
        """
        Query and store the current kuadrant_configs metric for a gateway.

        Args:
            gateway: The gateway object (must have .metrics.get_kuadrant_configs())

        Returns:
            The captured metric value, or None if unavailable
        """
        if not hasattr(gateway, 'metrics'):
            return None

        try:
            metric_value = gateway.metrics.get_kuadrant_configs()
            self.set_gateway_metric(gateway.name(), metric_value)
            return metric_value
        except Exception:  # pylint: disable=broad-except
            return None

    def debug_dump(self):
        """Debug: dump all registered nodes"""
        print(f"\n=== Topology Debug Dump ({len(self.nodes)} nodes) ===")
        for name, node in self.nodes.items():
            print(f"\n{node.kind.value if node.kind else 'Unknown'}: {name}")
            print(f"  resource: {node.resource.__class__.__name__ if node.resource else 'None'}")
            print(f"  targets: {node.targets}")
            print(f"  targeted_by: {node.targeted_by}")
            print(f"  children: {node.children}")
            print(f"  parent: {node.parent}")
            if node.metadata:
                print(f"  metadata: {node.metadata}")

    def clear(self):
        """Clear all registered resources"""
        self.nodes.clear()


# ============================================================================
# Decorator-based automatic registration
# ============================================================================

def topology(func: Callable) -> Callable:
    """
    Decorator for pytest fixtures that automatically registers the returned object
    in the global topology registry.

    Auto-detects the object type and registers it appropriately:
    - Gateway objects → register_gateway()
    - HTTPRoute objects → register_route()
    - Policy objects (AuthPolicy, RateLimitPolicy, etc.) → register_policy()

    Usage:
        @pytest.fixture(scope="module")
        @topology
        def gateway(cluster, blame):
            gw = KuadrantGateway.create_instance(...)
            return gw  # or yield gw

    Uses the global topology registry - no need to inject topology fixture!
    """
    import inspect

    # Check if the function is a generator function (uses yield)
    if inspect.isgeneratorfunction(func):
        # It's a generator function (uses yield)
        @wraps(func)
        def wrapper(*args, **kwargs):
            generator = func(*args, **kwargs)
            topology_registry = get_topology()

            # Get the yielded object
            obj = next(generator)

            # Register it
            if topology_registry:
                _register_object(topology_registry, obj)

            # Yield it to the test
            yield obj

            # Continue with cleanup
            try:
                next(generator)
            except StopIteration:
                pass

        return wrapper
    else:
        # It's a regular function (uses return)
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            topology_registry = get_topology()

            # Register the returned object
            if topology_registry:
                _register_object(topology_registry, result)

            return result

        return wrapper


def _register_object(topology_registry: TopologyRegistry, obj):
    """Helper to detect object type and register it"""
    if obj is None:
        return

    # Detect object type by class name
    class_name = obj.__class__.__name__

    # Import here to avoid circular imports
    from testsuite.gateway.gateway_api.gateway import KuadrantGateway
    from testsuite.gateway import Gateway

    # Check if it's a Gateway
    if isinstance(obj, (KuadrantGateway, Gateway)) or 'Gateway' in class_name:
        topology_registry.register_gateway(obj)
        # print(f"[TOPOLOGY] Registered gateway: {obj.name() if hasattr(obj, 'name') else 'unknown'}")
        return

    # Check if it's an HTTPRoute
    if 'HTTPRoute' in class_name or 'Route' in class_name:
        # Try to get gateway from the route object
        gateway_name = None
        if hasattr(obj, 'gateway') and obj.gateway:
            gateway_name = obj.gateway.name()

        topology_registry.register_route(obj, gateway_name=gateway_name)
        # print(f"[TOPOLOGY] Registered route: {obj.name() if hasattr(obj, 'name') else 'unknown'} -> gateway: {gateway_name}")
        return

    # Check if it's a Policy
    policy_keywords = ['Policy', 'AuthPolicy', 'RateLimitPolicy', 'DNSPolicy', 'TLSPolicy']
    if any(keyword in class_name for keyword in policy_keywords):
        topology_registry.register_policy(obj)
        # print(f"[TOPOLOGY] Registered policy: {class_name} - {obj.model.metadata.name if hasattr(obj, 'model') else 'unknown'}")
        return


def register_as(resource_type: str):
    """
    Decorator factory for explicitly specifying the resource type to register.

    Useful when auto-detection might be ambiguous or you want to be explicit.

    Args:
        resource_type: One of "gateway", "route", "policy"

    Usage:
        @register_as("gateway")
        @pytest.fixture(scope="module")
        def gateway(cluster, blame):
            ...

        @register_as("route")
        @pytest.fixture(scope="module")
        def route(gateway, blame):
            ...

        @register_as("policy")
        @pytest.fixture(scope="module")
        def authorization(cluster, route):
            ...
    """
    def decorator(fixture_func: Callable) -> Callable:
        import inspect
        sig = inspect.signature(fixture_func)
        params = sig.parameters

        @wraps(fixture_func)
        def wrapper(*args, **kwargs):
            topology_registry = kwargs.get('topology')
            result = fixture_func(*args, **kwargs)

            if inspect.isgenerator(result):
                obj = next(result)

                if topology_registry:
                    _register_by_type(topology_registry, obj, resource_type)

                yield obj

                try:
                    next(result)
                except StopIteration:
                    pass
            else:
                if topology_registry:
                    _register_by_type(topology_registry, result, resource_type)
                return result

        # Add 'topology' to signature if not present
        if 'topology' not in params:
            new_params = list(params.values())
            new_params.append(inspect.Parameter('topology', inspect.Parameter.POSITIONAL_OR_KEYWORD))
            wrapper.__signature__ = sig.replace(parameters=new_params)

        return wrapper

    return decorator


def _register_by_type(topology_registry: TopologyRegistry, obj, resource_type: str):
    """Helper to register object by explicit type"""
    if obj is None:
        return

    resource_type = resource_type.lower()

    if resource_type == "gateway":
        topology_registry.register_gateway(obj)
    elif resource_type in ("route", "httproute"):
        gateway_name = None
        if hasattr(obj, 'gateway') and obj.gateway:
            gateway_name = obj.gateway.name()
        topology_registry.register_route(obj, gateway_name=gateway_name)
    elif resource_type == "policy":
        topology_registry.register_policy(obj)
    else:
        raise ValueError(f"Unknown resource_type: {resource_type}. Use 'gateway', 'route', or 'policy'.")
