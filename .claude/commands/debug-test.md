---
description: Analyze test failures and suggest fixes
---

# Debug Test Failures

Analyze test failures and suggest fixes.

## Instructions

Follow these steps to analyze the test failure:

1. **Extract file path from traceback**: The error shows the failing file path (e.g., `testsuite/tests/.../test_basic.py:39`)

2. **Read test file and trace fixtures**:
   - Read the test file at the path from the traceback
   - Look at fixtures (function parameters) and imports that the test uses
   - Read `conftest.py` in same directory, then parent directories if needed
   - Understand what the test expects vs what's actually happening

3. **Categorize the failure**:
   - Identify the pattern (see `Common Failure Patterns` below)
   - Determine if this is a test/code issue or an environment/cluster state issue

4. **Identify file authors**:
   - For the failing test file and relevant conftest.py files, use this command to find recent contributors:
     ```bash
     git log --format='%an' <file> | sort | uniq -c | sort -rn | head -5
     ```
   - Include these authors in the output so users know who to contact for deeper context if needed

5. **Provide appropriate response**:
   - **If investigation needed**: Suggest kubectl commands to check policy status, conditions, events, logs, and verify resources exist and are ready
     - **IMPORTANT**: kubectl commands often require resources still in the cluster. Since tests cleanup after finishing, instruct to:
       - Set a breakpoint (outline where to set this)
       - Re-run the failing test locally
   - **If cluster/environment issue**: Provide kubectl/cleanup commands to fix cluster state
   - **If test/code issue**: Suggest code changes to fixtures or tests
   - **Mixed approach**: Combine multiple approaches as needed (e.g., investigate first, then apply fixes based on what you find)

## Common Failure Patterns

- **Policy not enforced**: Expected 302/401/429 but got 200 (policy not attached, wrong route/gateway, wrong host, or enforcement not yet propagated)
- **Policy targeting**: `is_affected_by()` returns `False` (wrong `targetRef`, `parentRef`, namespace, labels, or resource mismatch)
- **Reconciliation / propagation delay**: Async reconciliation not finished, config/policy not pushed, `observedGeneration` not catching up, race conditions
- **DNS resolution / propagation**: `NXDOMAIN`, stale records (external DNS delay or caching, record deletion not fully propagated)
- **DNS provider / credentials**: `DNSProviderError` (missing/misnamed/wrong-namespace secret, provider throttling or rate limits)
- **Dependency missing or not found**: Policy `Accepted=False`, `reason=MissingDependency`, or selector found no objects (`selected 0`)
  (required operator/backend not installed, wrong namespace, or wrong labels, e.g., Authorino, Limitador)
- **Component not ready**: Dependency installed but not `Ready` (slow rollout or readiness probe delays)
- **Connectivity / request timeouts**: Gateway or Listener not ready, LoadBalancer provisioning delay, DNS resolves but traffic does not route, client `httpx` connect/read timeouts
- **Wrong endpoint hit**: Test traffic bypasses the intended Gateway or Route (wrong URL, scheme, port, or hostname)
- **Stale state / cleanup issues**: Leftover resources from previous tests (policies, routes, DNS records, namespaces not fully deleted)
- **Invalid or rejected configuration**: Policy `Accepted=False` with reasons like `Invalid` or `TargetNotFound` (bad references, missing targets, wrong issuer/secret)
- **Status / model mismatch**: `MissingModelBranch` (testsuite expects status/conditions not present, CRD or controller output drift)

## Output Format

**Issue**: [Summary of the problem]

**Root cause**: [Summary of why it's failing, or "needs more investigation" if unclear]

**Recommended steps**: [One or more steps - can be investigation, code changes, environment fixes, or a mix]

**File authors (Contact these contributors if you need deeper context beyond Claude's analysis)**:

- `<file_path>`: Author Name (N commits), Another Author (M commits), ...

_NOTE:_ Do NOT auto-run bash/kubectl commands or web searches before providing direct analysis and recommendations.
