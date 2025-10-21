"""Conftest for TokenRateLimitPolicy tests"""

import pytest

from testsuite.backend.llm_sim import LlmSim


@pytest.fixture(scope="module")
def backend(request, cluster, blame, label, testconfig):
    """Deploys LlmSim backend"""
    image = testconfig["llm_sim"]["image"]
    llmsim = LlmSim(cluster, blame("llm-sim"), "meta-llama/Llama-3.1-8B-Instruct", label, image)
    request.addfinalizer(llmsim.delete)
    llmsim.commit()
    return llmsim


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, authorization, token_rate_limit):
    """Commits policies"""
    # Ensure route is ready first
    if hasattr(route, "wait_for_ready"):
        route.wait_for_ready()

    components = [authorization, token_rate_limit]
    for component in components:
        if component:
            request.addfinalizer(component.delete)
            component.commit()
            component.wait_for_ready()
