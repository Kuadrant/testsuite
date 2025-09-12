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
def commit(request, authorization, token_rate_limit):
    """Commits policies"""
    components = [c for c in [authorization, token_rate_limit] if c is not None]
    for component in components:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()
