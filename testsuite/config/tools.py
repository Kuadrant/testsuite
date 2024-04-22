"""Dynaconf loader for fetching data from tools namespace"""

import logging

from openshift_client import selector

from testsuite.openshift.service import Service

logger = logging.getLogger(__name__)


def fetch_route(name, force_http=False, service_port=None):
    """Fetches the URL of a route with specific name"""

    def _fetcher(settings, _):
        try:
            openshift = settings["tools"]
            route = openshift.get_route(name)
            if not force_http and "tls" in route.model.spec:
                return "https://" + route.model.spec.host
            return "http://" + route.model.spec.host
        # pylint: disable=broad-except
        except Exception:
            logger.warning("Unable to fetch route %s from tools", name)
            return None

    return _fetcher


def fetch_service(name, protocol: str = None, port: int = None):
    """Fetches the local URL of existing service with specific name"""

    def _fetcher(settings, _):
        openshift = settings["tools"]
        try:
            if not openshift.service_exists(name):
                logger.warning("Unable to fetch service %s from tools, service does not exists", name)
                return None
        except AttributeError:
            logger.warning("Unable to fetch service %s from tools, tools project might be missing", name)
            return None

        service_url = f"{name}.{openshift.project}.svc.cluster.local"

        if protocol:
            service_url = f"{protocol}://{service_url}"
        if port:
            service_url = f"{service_url}:{port}"

        return service_url

    return _fetcher


def fetch_service_ip(name, port, force_http=False):
    """Fetched load balanced ip for LoadBalancer service"""

    def _fetcher(settings, _):
        try:
            openshift = settings["tools"]
            with openshift.context:
                ip = selector(f"service/{name}").object(cls=Service).external_ip
                return f"http://{ip}:{port}" if force_http else f"https://{ip}:{port}"
        except Exception:
            logger.warning("Unable to fetch route %s from tools", name)
            return None

    return _fetcher


def fetch_secret(name, key):
    """Fetches the key out of a secret with specific name"""

    def _fetcher(settings, _):
        try:
            openshift = settings["tools"]
            return openshift.get_secret(name)[key]
        # pylint: disable=broad-except
        except Exception:
            logger.warning("Unable to fetch secret %s[%s] from tools", name, key)
            return None

    return _fetcher
