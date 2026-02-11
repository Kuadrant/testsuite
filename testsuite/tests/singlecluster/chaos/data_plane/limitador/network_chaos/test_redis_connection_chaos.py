"""Test Limitador resilience when Redis connection is disrupted."""

import pytest
import time

pytestmark = [pytest.mark.disruptive, pytest.mark.limitador]


def test_limitador_redis_network_delay(
    cluster, limitador_network_chaos, redis_backend, rate_limit_policy
):
    """Test Limitador behavior with delayed Redis responses."""
    rate_limit_policy.commit()
    
    # Create network delay to Redis
    chaos = limitador_network_chaos(
        "redis-delay",
        action="delay",
        external_targets=["redis.kuadrant-system.svc.cluster.local"],
        delay="500ms",
        duration="60s"
    )
    chaos.commit()
    
    # Test rate limiting with delay
    start_time = time.time()
    response = rate_limit_policy.test_rate_limit()
    end_time = time.time()
    
    # Should still work but be slower
    assert response.status_code in [200, 429]  # Rate limit decision made
    assert end_time - start_time > 0.5  # Delay applied


def test_limitador_redis_network_partition(
    cluster, limitador_network_chaos, redis_backend, rate_limit_policy
):
    """Test Limitador behavior when Redis is unreachable."""
    rate_limit_policy.commit()
    
    # Create network partition to Redis
    chaos = limitador_network_chaos(
        "redis-partition",
        action="partition",
        external_targets=["redis.kuadrant-system.svc.cluster.local"],
        duration="30s"
    )
    chaos.commit()
    
    # Test rate limiting during partition
    response = rate_limit_policy.test_rate_limit()
    
    # Should fail-open or fail-closed based on configuration
    # This depends on Limitador's configuration
    assert response.status_code in [200, 500, 503]


def test_limitador_redis_intermittent_connection(
    cluster, limitador_network_chaos, redis_backend, rate_limit_policy
):
    """Test Limitador with intermittent Redis connection issues."""
    rate_limit_policy.commit()
    
    # Create intermittent network issues (30% packet loss)
    chaos = limitador_network_chaos(
        "redis-intermittent",
        action="loss",
        external_targets=["redis.kuadrant-system.svc.cluster.local"],
        loss_percent=30,
        duration="45s"
    )
    chaos.commit()
    
    # Test multiple rate limit attempts
    responses = []
    for _ in range(20):
        response = rate_limit_policy.test_rate_limit()
        responses.append(response.status_code)
        time.sleep(0.5)
    
    # Should have mixed results due to intermittent failures
    unique_responses = set(responses)
    assert len(unique_responses) > 1  # Should have different response codes
    print(f"Response distribution: {dict(zip(*zip(*[(r, responses.count(r)) for r in unique_responses])))}")


def test_limitador_redis_high_latency(
    cluster, limitador_network_chaos, redis_backend, rate_limit_policy
):
    """Test Limitador with high Redis latency."""
    rate_limit_policy.commit()
    
    # Create high latency to Redis
    chaos = limitador_network_chaos(
        "redis-high-latency",
        action="delay",
        external_targets=["redis.kuadrant-system.svc.cluster.local"],
        delay="2s",
        jitter="500ms",
        duration="60s"
    )
    chaos.commit()
    
    # Test rate limiting under high latency
    slow_responses = 0
    total_requests = 10
    
    for _ in range(total_requests):
        start_time = time.time()
        response = rate_limit_policy.test_rate_limit()
        end_time = time.time()
        
        if end_time - start_time > 1.5:  # Accounting for jitter
            slow_responses += 1
        
        # Verify response is still valid
        assert response.status_code in [200, 429, 500, 503]
    
    # Most responses should be slow due to Redis latency
    assert slow_responses >= total_requests * 0.7  # At least 70% slow


def test_limitador_redis_connection_reset(
    cluster, limitador_network_chaos, redis_backend, rate_limit_policy
):
    """Test Limitador when Redis connections are reset."""
    rate_limit_policy.commit()
    
    # Create connection resets to Redis
    chaos = limitador_network_chaos(
        "redis-reset",
        action="abort",
        external_targets=["redis.kuadrant-system.svc.cluster.local"],
        abort_percent=50,
        duration="30s"
    )
    chaos.commit()
    
    # Test rate limiting with connection resets
    error_responses = 0
    total_requests = 15
    
    for _ in range(total_requests):
        response = rate_limit_policy.test_rate_limit()
        if response.status_code >= 500:
            error_responses += 1
        time.sleep(1)
    
    # Should have some errors due to connection resets
    assert error_responses > 0
    print(f"Error rate: {error_responses}/{total_requests}")
