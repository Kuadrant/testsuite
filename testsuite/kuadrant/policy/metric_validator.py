"""WasmPlugin metric validation for policy commits."""


class WasmMetricValidator:
    """
    Validates kuadrant_configs metric changes after policy commits.

    The kuadrant_configs metric tracks WasmPlugin configurations loaded in the WASM shim.
    It increases (by 4 per gateway) when WasmPlugin PluginConfig is regenerated, which happens:
    1. First policy on a gateway (WasmPlugin created)
    2. Topology changes (route creation/deletion) trigger config regeneration

    In controlled test environments where gateway + routes exist before policies:
    - First policy creates WasmPlugin → metric increases
    - Subsequent policies (parametrized tests) don't change topology → metric stays constant

    This validator uses per-gateway flags and topology analysis to predict metric behavior.
    """

    @staticmethod
    def prepare_validation(policy, topology):
        """
        Prepare metric validation by capturing initial state and determining expectations.

        This should be called before commit() to set up validation that runs in wait_for_ready().

        Args:
            policy: The policy being committed
            topology: The TopologyRegistry instance
        """
        if not topology or not hasattr(policy.model.spec, 'targetRef'):
            return

        target_ref = policy.model.spec.targetRef
        gateway = topology.get_gateway_for_target_ref(target_ref)

        if not gateway or not hasattr(gateway, 'metrics'):
            return

        # Capture current metric value
        try:
            initial_metric = gateway.metrics.get_kuadrant_configs()
        except (AttributeError, OSError):
            # AttributeError: metrics service/route not ready or model structure unexpected
            # OSError: httpx base exception (includes ConnectError, TimeoutException, etc.)
            initial_metric = 0

        # Determine if this policy will cause WasmPlugin creation (metric increase)
        expect_metric_increase = topology.should_expect_wasm_metric_increase(
            target_ref,
            gateway.name(),
            exclude_policy_name=policy.name()
        )

        # Mark gateway if WasmPlugin will be created
        if expect_metric_increase:
            topology.mark_wasm_config_created(gateway.name())

        # Store metadata for validation in wait_for_ready()
        topology.set_policy_metadata(policy, 'initial_kuadrant_configs', initial_metric)
        topology.set_policy_metadata(policy, 'expect_metric_increase', expect_metric_increase)
        topology.set_policy_metadata(policy, 'gateway_name', gateway.name())

    @staticmethod
    def validate_metrics(policy, topology):
        """
        Validate that the kuadrant_configs metric changed as expected after policy commit.

        This should be called in wait_for_ready() after the policy is enforced.

        Args:
            policy: The policy that was committed
            topology: The TopologyRegistry instance

        Raises:
            AssertionError: If metric validation fails
        """
        if not topology:
            return

        initial_metric = topology.get_policy_metadata(policy, 'initial_kuadrant_configs')
        gateway_name = topology.get_policy_metadata(policy, 'gateway_name')
        expect_metric_increase = topology.get_policy_metadata(policy, 'expect_metric_increase')

        if initial_metric is None or gateway_name is None:
            return

        gateway = topology.get_gateway(gateway_name)
        if not gateway or not hasattr(gateway, 'metrics'):
            return

        # Wait for metric to reach expected state
        if expect_metric_increase:
            # First policy for this target - metric should increase
            gateway.metrics.wait_for_kuadrant_config_increase(initial_metric)
        else:
            # Policy updates existing WasmPlugin - metric should stay same
            # Just verify it didn't decrease
            current_metric = gateway.metrics.get_kuadrant_configs()
            if current_metric < initial_metric:
                raise AssertionError(
                    f"kuadrant_configs metric decreased unexpectedly for policy {policy.name()}. "
                    f"Initial: {initial_metric}, Current: {current_metric}"
                )