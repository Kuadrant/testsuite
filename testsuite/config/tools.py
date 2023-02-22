"""Dynaconf loader for fetching data from tools namespace"""
import logging

logger = logging.getLogger(__name__)


def fetch_route(name, force_http=False):
    """Fetches the URL of a route with specific name"""

    def _fetcher(settings, _):
        try:
            openshift = settings["tools"]
            route = openshift.routes[name]
            if not force_http and "tls" in route.model.spec:
                return "https://" + route.model.spec.host
            return "http://" + route.model.spec.host
        # pylint: disable=broad-except
        except Exception:
            logger.warning("Unable to fetch route %s from tools", name)
            return None

    return _fetcher


def fetch_secret(name, key):
    """Fetches the key out of a secret with specific name"""

    def _fetcher(settings, _):
        try:
            openshift = settings["tools"]
            return openshift.secrets[name][key]
        # pylint: disable=broad-except
        except Exception:
            logger.warning("Unable to fetch secret %s[%s] from tools", name, key)
            return None

    return _fetcher
