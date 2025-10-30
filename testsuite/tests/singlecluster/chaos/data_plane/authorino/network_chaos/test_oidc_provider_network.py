"""Test Authorino resilience when OIDC provider network is disrupted."""

import pytest
import time

pytestmark = [pytest.mark.disruptive, pytest.mark.authorino]


def test_authorino_oidc_network_delay(
    cluster, authorino_network_chaos, oidc_provider, auth_policy_with_oidc
):
    """Test Authorino behavior with delayed OIDC provider responses."""
    # Apply auth policy that uses OIDC
    auth_policy_with_oidc.commit()
    
    # Create network delay to OIDC provider
    chaos = authorino_network_chaos(
        "oidc-delay",
        action="delay",
        external_targets=[oidc_provider.issuer_url],
        delay="3s",
        duration="60s"
    )
    chaos.commit()
    
    # Test authentication with delay
    start_time = time.time()
    response = auth_policy_with_oidc.test_authentication()
    end_time = time.time()
    
    # Should still work but be slower
    assert response.status_code in [200, 401]  # Auth decision made
    assert end_time - start_time > 3.0  # Delay applied
    
    # Verify Authorino handles timeout gracefully
    assert "timeout" not in response.headers.get("x-ext-auth-reason", "").lower()


def test_authorino_oidc_network_partition(
    cluster, authorino_network_chaos, oidc_provider, auth_policy_with_oidc
):
    """Test Authorino behavior when OIDC provider is unreachable."""
    auth_policy_with_oidc.commit()
    
    # Create network partition to OIDC provider
    chaos = authorino_network_chaos(
        "oidc-partition",
        action="partition",
        external_targets=[oidc_provider.issuer_url],
        duration="30s"
    )
    chaos.commit()
    
    # Test authentication during partition
    response = auth_policy_with_oidc.test_authentication()
    
    # Should fail gracefully (not hang indefinitely)
    assert response.status_code == 401
    assert "connection" in response.headers.get("x-ext-auth-reason", "").lower()


def test_authorino_oidc_intermittent_failures(
    cluster, authorino_network_chaos, oidc_provider, auth_policy_with_oidc
):
    """Test Authorino with intermittent OIDC provider failures."""
    auth_policy_with_oidc.commit()
    
    # Create intermittent network issues (50% packet loss)
    chaos = authorino_network_chaos(
        "oidc-intermittent",
        action="loss",
        external_targets=[oidc_provider.issuer_url],
        loss_percent=50,
        duration="45s"
    )
    chaos.commit()
    
    # Test multiple authentication attempts
    success_count = 0
    total_attempts = 10
    
    for _ in range(total_attempts):
        response = auth_policy_with_oidc.test_authentication()
        if response.status_code == 200:
            success_count += 1
        time.sleep(1)
    
    # Some should succeed, some should fail
    assert 0 < success_count < total_attempts
    print(f"Success rate: {success_count}/{total_attempts}")


def test_authorino_oidc_discovery_chaos(
    cluster, authorino_network_chaos, oidc_provider, auth_policy_with_oidc
):
    """Test Authorino when OIDC discovery endpoint is disrupted."""
    # Target specifically the .well-known/openid-configuration endpoint
    discovery_url = f"{oidc_provider.issuer_url}/.well-known/openid-configuration"
    
    chaos = authorino_network_chaos(
        "oidc-discovery-chaos",
        action="delay",
        external_targets=[discovery_url],
        delay="10s",
        duration="30s"
    )
    chaos.commit()
    
    # Apply policy (this should trigger discovery)
    auth_policy_with_oidc.commit()
    
    # Verify policy eventually becomes ready despite discovery delays
    assert auth_policy_with_oidc.wait_for_ready(timeout=60)
