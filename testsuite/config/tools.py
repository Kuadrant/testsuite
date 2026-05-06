"""Dynaconf loader for fetching data from tools namespace"""

import logging

import yaml
from openshift_client import selector, OpenShiftPythonException

from testsuite.kubernetes.config_map import ConfigMap
from testsuite.kubernetes.service import Service

logger = logging.getLogger(__name__)


def fetch_route(name, force_http=False):
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
        cluster = settings["tools"]
        try:
            if not cluster.service_exists(name):
                logger.warning("Unable to fetch service %s from tools, service does not exists", name)
                return None
        except AttributeError:
            logger.warning("Unable to fetch service %s from tools, tools project might be missing", name)
            return None

        service_url = f"{name}.{cluster.project}.svc.cluster.local"

        if protocol:
            service_url = f"{protocol}://{service_url}"
        if port:
            service_url = f"{service_url}:{port}"

        return service_url

    return _fetcher


def fetch_service_ip(name, port: int, protocol: str = "http"):
    """Fetched load balanced ip for LoadBalancer service"""

    def _fetcher(settings, _):
        try:
            cluster = settings["tools"]
            with cluster.context:
                ip = selector(f"service/{name}").object(cls=Service).external_ip
                return f"{protocol}://{ip}:{port}"
        # pylint: disable=broad-except
        except Exception:
            logger.warning("Unable to fetch route %s from tools", name)
            return None

    return _fetcher


def fetch_prometheus_url():
    """Auto-discovers Prometheus URL from the configured monitoring namespace"""

    def _fetcher(settings, _):
        prometheus = settings.get("prometheus")
        if prometheus is None:
            return None

        project = prometheus["project"]
        service_name = prometheus["service"]

        try:
            cluster = settings["control_plane"]["cluster"].change_project(project)
        except (KeyError, AttributeError) as exc:
            logger.warning("Cluster configuration missing for Prometheus discovery: %s", exc)
            return None

        # Try OpenShift route with user workload monitoring check
        try:
            with cluster.context:
                cm = selector("cm/cluster-monitoring-config").object(cls=ConfigMap)
                if not yaml.safe_load(cm["config.yaml"]).get("enableUserWorkload"):
                        logger.warning("User workload monitoring is not enabled in cluster-monitoring-config")
                        return None
                routes = cluster.get_routes_for_service(service_name)
                if routes:
                    route = routes[0]
                    protocol = "https" if "tls" in route.model.spec else "http"
                    return f"{protocol}://{route.model.spec.host}"
                logger.warning("No routes found for service '%s' in '%s'", service_name, project)
        except OpenShiftPythonException as exc:
                logger.info("OpenShift route discovery not available: %s", exc)
        except (KeyError, yaml.YAMLError) as exc:
                logger.warning("Failed to parse cluster-monitoring-config: %s", exc)

        # Try LoadBalancer service (Kind / non-OpenShift)
        try:
            with cluster.context:
                svc = selector(f"service/{service_name}").object(cls=Service)
                ip = svc.external_ip
                if ip:
                    port = svc.model.spec.ports[0].port
                    return f"http://{ip}:{port}"
        except OpenShiftPythonException:
            logger.info("Service '%s' not found in '%s', trying OpenShift route", service_name, project)
        except (AttributeError, IndexError) as exc:
            logger.warning("Service '%s' in '%s' has no external IP or ports: %s", service_name, project, exc)

        logger.warning("Unable to auto-discover Prometheus URL in '%s'", project)
        return None

    return _fetcher


def fetch_secret(name, key):
    """Fetches the key out of a secret with specific name"""

    def _fetcher(settings, _):
        try:
            cluster = settings["tools"]
            return cluster.get_secret(name)[key]
        # pylint: disable=broad-except
        except Exception:
            logger.warning("Unable to fetch secret %s[%s] from tools", name, key)
            return None

    return _fetcher
