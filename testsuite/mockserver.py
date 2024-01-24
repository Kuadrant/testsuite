"""Module for Mockserver integration"""

from typing import Union

from apyproxy import ApyProxy

from testsuite.utils import ContentType
from testsuite.httpx import KuadrantClient
from testsuite.openshift import Selector
from testsuite.openshift.backend import Backend
from testsuite.openshift.service import Service, ServicePort
from testsuite.openshift.deployment import Deployment, ContainerResources
from testsuite.openshift.client import OpenShiftClient


class Mockserver:
    """
    Mockserver deployed in Openshift (located in Tools or self-managed)
    """

    def __init__(self, url, client: KuadrantClient = None):
        self.client = ApyProxy(url, session=client or KuadrantClient(verify=False))

    def _expectation(self, expectation_id, json_data):
        """
        Creates an Expectation from given expectation json.
        Returns the absolute URL of the expectation
        """
        json_data["id"] = expectation_id
        json_data.setdefault("httpRequest", {})["path"] = f"/{expectation_id}"

        self.client.mockserver.expectation.put(json=json_data)
        # pylint: disable=protected-access
        return f"{self.client._url}/{expectation_id}"

    def create_request_expectation(
        self,
        expectation_id,
        headers: dict[str, list[str]],
    ):
        """Creates an Expectation - request with given headers"""
        json_data = {
            "httpRequest": {
                "headers": headers,
            },
            "httpResponse": {
                "body": "",
            },
        }
        return self._expectation(expectation_id, json_data)

    def create_expectation(
        self,
        expectation_id,
        body,
        content_type: Union[ContentType, str] = ContentType.PLAIN_TEXT,
    ):
        """Creates an Expectation - response with given body"""
        json_data = {"httpResponse": {"headers": {"Content-Type": [str(content_type)]}, "body": body}}
        return self._expectation(expectation_id, json_data)

    def create_template_expectation(self, expectation_id, template):
        """
        Creates template expectation in Mustache format.
        https://www.mock-server.com/mock_server/response_templates.html
        """
        json_data = {"httpResponseTemplate": {"templateType": "MUSTACHE", "template": template}}
        return self._expectation(expectation_id, json_data)

    def clear_expectation(self, expectation_id):
        """Clears Expectation with specific ID"""
        return self.client.mockserver.clear.put(json={"id": expectation_id})

    def retrieve_requests(self, expectation_id):
        """Verify a request has been received a specific number of times"""
        return self.client.mockserver.retrieve.put(
            params={"type": "REQUESTS", "format": "JSON"},
            json={"path": "/" + expectation_id},
        ).json()


class MockserverBackend(Backend):
    """Mockserver deployed as backend in Openshift"""

    PORT = 8080

    def __init__(self, openshift: OpenShiftClient, name: str, label: str):
        self.openshift = openshift
        self.name = name
        self.label = label

        self.deployment = None
        self.service = None

    @property
    def reference(self):
        return {
            "group": "",
            "kind": "Service",
            "port": self.PORT,
            "name": self.name,
            "namespace": self.openshift.project,
        }

    def commit(self):
        match_labels = {"app": self.label, "deployment": self.name}
        self.deployment = Deployment.create_instance(
            self.openshift,
            self.name,
            container_name="mockserver",
            image="quay.io/mganisin/mockserver:latest",
            ports={"api": 1080},
            selector=Selector(matchLabels=match_labels),
            labels={"app": self.label},
            resources=ContainerResources(limits_memory="2G"),
            lifecycle={"postStart": {"exec": {"command": ["/bin/sh", "init-mockserver"]}}},
        )
        self.deployment.commit()
        self.deployment.wait_for_ready()

        self.service = Service.create_instance(
            self.openshift,
            self.name,
            selector=match_labels,
            ports=[ServicePort(name="1080-tcp", port=self.PORT, targetPort="api")],
            labels={"app": self.label},
        )
        self.service.commit()

    def delete(self):
        with self.openshift.context:
            if self.service:
                self.service.delete()
                self.service = None
            if self.deployment:
                self.deployment.delete()
                self.deployment = None
