"""Dynaconf loader for fetching data from tools namespace"""
import logging

logger = logging.getLogger(__name__)


def fetch_route(name):
    """Fetches the URL of a route with specific name"""
    def _fetcher(settings):
        try:
            openshift = settings["tools"]
            route = openshift.routes[name]
            if "tls" in route.model.spec:
                return "https://" + route.model.spec.host
            return "http://" + route.model.spec.host
        # pylint: disable=broad-except
        except Exception:
            logger.warning("Unable to fetch route %s from tools", name)
            return None
    return _fetcher


def fetch_from_secret(name, key):
    """Fetches the key out of a secret with specific name"""
    def _fetcher(settings):
        try:
            openshift = settings["tools"]
            return openshift.secrets[name][key]
        # pylint: disable=broad-except
        except Exception:
            logger.warning("Unable to fetch secret %s[%s] from tools", name, key)
            return None
    return _fetcher


def lazy_merge(settings, defaults, current_section=None):
    """Lazily merges defaults values to the settings if they don't exist yet"""
    current_section = current_section or settings
    for key, value in defaults.items():
        if isinstance(value, dict):
            lazy_merge(settings, value, current_section=settings.setdefault(key, {}))
            continue
        if key not in current_section:
            computed_val = value(settings)
            # Technically None is a value and will pass must_exist Validator
            if computed_val is not None:
                current_section[key] = computed_val


# pylint: disable=unused-argument
def load(obj, env=None, silent=True, key=None, filename=None):
    """Loads data from OpenShift lazily"""
    defaults = {
        "rhsso": {
            "url": fetch_route("no-ssl-sso"),
            "password": fetch_from_secret("credential-sso", "ADMIN_PASSWORD")
        }
    }
    lazy_merge(obj, defaults)
