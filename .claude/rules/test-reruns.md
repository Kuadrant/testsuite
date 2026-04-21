# Test Reruns (`@pytest.mark.flaky`)

The testsuite uses `pytest-rerunfailures` to automatically retry failed tests (default: `--reruns 3` in the Makefile). The `@pytest.mark.flaky` marker controls rerun behavior per test.

**Disable reruns** for tests that cannot recover from a failure, because they delete or modify module-scoped fixtures during the test. Since `pytest-rerunfailures` only reruns the test function (not module-scoped fixtures), the deleted/modified resource will not be recreated:

```python
@pytest.mark.flaky(reruns=0)
def test_policy_deletion(policy):
    """This test deletes a module-scoped fixture, so rerunning would fail"""
    policy.delete()
    assert not policy.exists()
```

**Add a delay** for rate limit tests that exhaust a counter and assert `429`. On rerun, the counter from the previous attempt may still be active. Set `reruns_delay` to the rate limit window + 5 seconds:

```python
@pytest.mark.flaky(reruns=3, reruns_delay=15)  # Limit window is 10s, wait 15s
def test_rate_limit(client):
    responses = client.get_many("/get", 5)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429
```

**When to use which:**

| Situation | Marker |
|-----------|--------|
| Test deletes or modifies a module-scoped fixture | `@pytest.mark.flaky(reruns=0)` |
| Test creates and deletes resources within the test body (e.g., UI tests) | `@pytest.mark.flaky(reruns=0)` |
| Rate limit test with 5s window | `@pytest.mark.flaky(reruns=3, reruns_delay=10)` |
| Rate limit test with 10s window | `@pytest.mark.flaky(reruns=3, reruns_delay=15)` |
| Rate limit test with 60s window | `@pytest.mark.flaky(reruns=3, reruns_delay=65)` |
| Normal test (no side effects) | No marker needed (uses global `--reruns 3`) |