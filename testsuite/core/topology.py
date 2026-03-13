"""Gateway API Topology Registry for tracking resources and their relationships"""

import inspect
from functools import wraps
from typing import Optional, List, Dict, Set, Callable, Union

from testsuite.gateway import Gateway
from testsuite.gateway.gateway_api import GatewayAPIKind, PolicyKind

# Global singleton instance
_global_topology_registry: Optional['TopologyRegistry'] = None


class TopologyNode:
    """Represents a node in the Gateway API topology graph"""

    def __init__(self, kind: Union[GatewayAPIKind, PolicyKind], resource, name: str):
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
        from testsuite.core.topology import get_topology

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

    def _get_or_create_node(self, kind: Union[GatewayAPIKind, PolicyKind], resource, name: str) -> TopologyNode:
        """Get existing node or create new one"""
        if name not in self.nodes:
            self.nodes[name] = TopologyNode(kind, resource, name)
        return self.nodes[name]

    def register_gateway(self, gateway):
        """Register a Gateway"""
        name = gateway.name()
        node = self._get_or_create_node(GatewayAPIKind.GATEWAY, gateway, name)
        return node

    def register_route(self, route, gateway_name: Optional[str] = None):
        """
        Register an HTTPRoute

        Args:
            route: The HTTPRoute object
            gateway_name: Optional explicit gateway name. If not provided, will try route.gateway.name()
        """
        name = route.name()
        node = self._get_or_create_node(GatewayAPIKind.HTTPROUTE, route, name)

        # Determine gateway
        if not gateway_name and hasattr(route, "gateway"):
            gateway_name = route.gateway.name()

        if gateway_name:
            # Create relationship
            node.parent = gateway_name
            gateway_node = self._get_or_create_node(GatewayAPIKind.GATEWAY, None, gateway_name)
            gateway_node.children.add(name)

        return node

    def register_policy(self, policy):
        """
        Register a policy (AuthPolicy, RateLimitPolicy, etc.)

        Automatically determines the kind and target relationship
        """
        # Access model directly (works even if not committed)
        name = policy.model.metadata.name
        kind = PolicyKind(policy.model.kind)

        node = self._get_or_create_node(kind, policy, name)

        # Determine target (use model directly to avoid property access)
        if hasattr(policy.model.spec, "targetRef"):
            target_ref = policy.model.spec.targetRef
            target_name = target_ref.name
            target_kind = target_ref.kind

            # Create relationship
            node.targets.add(target_name)

            # Create or update target node
            if target_kind == GatewayAPIKind.GATEWAY:
                target_node = self._get_or_create_node(GatewayAPIKind.GATEWAY, None, target_name)
            elif target_kind == GatewayAPIKind.HTTPROUTE:
                target_node = self._get_or_create_node(GatewayAPIKind.HTTPROUTE, None, target_name)
            else:
                # Unknown target kind, create generic node
                target_node = self.nodes.setdefault(target_name, TopologyNode(None, None, target_name))

            target_node.targeted_by.add(name)

        return node

    def get_node(self, name: str) -> Optional[TopologyNode]:
        """Get a node by name"""
        return self.nodes.get(name)

    def get_gateway(self, name: str):
        """Get a Gateway resource by name"""
        node = self.get_node(name)
        return node.resource if node and node.kind == GatewayAPIKind.GATEWAY else None

    def get_route(self, name: str):
        """Get an HTTPRoute resource by name"""
        node = self.get_node(name)
        return node.resource if node and node.kind == GatewayAPIKind.HTTPROUTE else None

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

        if target_kind == GatewayAPIKind.GATEWAY:
            # Direct gateway target
            return self.get_gateway(target_name)
        elif target_kind == GatewayAPIKind.HTTPROUTE:
            # Route target - get parent gateway
            route_node = self.get_node(target_name)
            if route_node and route_node.parent:
                return self.get_gateway(route_node.parent)

        return None

    def get_policies_for_gateway(self, gateway_name: str, policy_kind: Optional[GatewayAPIKind] = None) -> List:
        """
        Get all policies targeting a gateway (directly or via routes).

        Args:
            gateway_name: Gateway name
            policy_kind: Optional filter by policy kind (e.g., GatewayAPIKind.AUTH_POLICY)
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
            if child_node and child_node.kind == GatewayAPIKind.HTTPROUTE:
                for policy_name in child_node.targeted_by:
                    policy_node = self.get_node(policy_name)
                    if policy_node and policy_node.resource:
                        if not policy_kind or policy_node.kind == policy_kind:
                            policies.append(policy_node.resource)

        return policies

    def get_policies_for_route(self, route_name: str, policy_kind: Optional[GatewayAPIKind] = None) -> List:
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

    def has_existing_policies_for_target(self, target_ref, exclude_policy_name=None):
        """
        Check if there are existing committed policies targeting the given targetRef.

        Args:
            target_ref: The targetRef object with .name and .kind attributes
            exclude_policy_name: Optional policy name to exclude from the check

        Returns:
            bool: True if other committed policies exist for this target
        """
        target_kind = target_ref.kind
        target_name = target_ref.name

        # Get policies for this target
        if target_kind == GatewayAPIKind.HTTPROUTE:
            existing_policies = self.get_policies_for_route(target_name)
        elif target_kind == GatewayAPIKind.GATEWAY:
            existing_policies = self.get_policies_for_gateway(target_name)
        else:
            return False

        # Filter out excluded policy and uncommitted policies
        existing_policies = [
            p for p in existing_policies
            if (not exclude_policy_name or p.name() != exclude_policy_name)
            and p.committed
        ]

        return len(existing_policies) > 0

    def should_expect_wasm_metric_increase(self, target_ref, gateway_name, exclude_policy_name=None):
        """
        Determine if committing a policy should cause the kuadrant_configs metric to increase.

        The metric increases when WasmPlugin PluginConfig is regenerated by the operator.
        This happens when:
        1. First policy on a gateway (WasmPlugin created)
        2. Topology changes (route creation/deletion) trigger config regeneration

        In controlled test environments (gateway + routes created before policies):
        - First policy creates WasmPlugin → flag set, metric increases
        - Subsequent policies don't change topology → config unchanged, metric constant

        The per-gateway flag tracks whether WasmPlugin exists, which is the right granularity
        since topology changes cause full config regeneration anyway.

        Args:
            target_ref: The targetRef object with .name and .kind attributes
            gateway_name: Gateway name
            exclude_policy_name: Optional policy name to exclude from checks

        Returns:
            bool: True if metric should increase, False otherwise
        """
        # Check if other policies exist for this target
        has_existing_policies = self.has_existing_policies_for_target(target_ref, exclude_policy_name)

        # Check if WasmPlugin was ever created for this gateway
        gateway_node = self.get_node(gateway_name)
        wasm_config_created = gateway_node and gateway_node.metadata.get('wasm_config_created', False)

        # Expect increase only if both checks say "no existing config"
        return not has_existing_policies and not wasm_config_created

    def mark_wasm_config_created(self, gateway_name):
        """
        Mark that a WasmPlugin config has been created for this gateway.

        Args:
            gateway_name: Gateway name
        """
        gateway_node = self.get_node(gateway_name)
        if gateway_node:
            gateway_node.metadata['wasm_config_created'] = True

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

    # Import here to avoid circular imports
    from testsuite.gateway import GatewayRoute
    from testsuite.gateway.gateway_api.gateway import KuadrantGateway
    from testsuite.gateway.gateway_api.route import HTTPRoute
    from testsuite.kuadrant.policy import Policy

    # Check if it's a Gateway
    if isinstance(obj, (KuadrantGateway, Gateway)):
        topology_registry.register_gateway(obj)
        return

    # Check if it's an HTTPRoute
    if isinstance(obj, (HTTPRoute, GatewayRoute)):
        gateway_name = None
        if hasattr(obj, 'gateway') and obj.gateway:
            gateway_name = obj.gateway.name()
        topology_registry.register_route(obj, gateway_name=gateway_name)
        return

    # Check if it's a Policy
    if isinstance(obj, Policy):
        topology_registry.register_policy(obj)
        return


