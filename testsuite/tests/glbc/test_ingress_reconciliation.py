"""Basic tests for ingress reconciliation"""
import backoff
import httpx
import pytest

from testsuite.openshift.objects.ingress import Ingress

pytestmark = [pytest.mark.glbc]


@pytest.fixture(scope="module")
def backend_ingress(request, backend, blame):
    """Returns created ingress for given backend"""
    service = backend.service
    service_name = service.name()
    port = backend.port

    name = blame("backend-ingress")

    ingress = Ingress.create_service_ingress(backend.openshift, name, service_name, port)
    request.addfinalizer(ingress.delete)
    ingress.commit()

    return ingress


@backoff.on_exception(backoff.fibo, exception=httpx.ConnectError, max_time=600)
def test_ingress_host_add(backend_ingress):
    """Creates ingress for a backend and checks for host field filled by glbc, checks host points to backend"""
    backend_ingress.wait_for_ready()
    host = backend_ingress.host

    assert host

    # # needed because of negative dns caching
    # # once https://github.com/kcp-dev/kcp-glbc/issues/354 is implemented this can be removed and reimplemented
    # time.sleep(20)  # wait until dns record is propagated

    response = httpx.get(f"http://{host}", follow_redirects=True)

    assert response.status_code == 200
