"""cert-manager Certificate object"""

from testsuite.kubernetes import CustomResource


class Certificate(CustomResource):
    """cert-manager Certificate resource"""

    @classmethod
    def create_instance(cls, cluster, name, secret_name, issuer_ref, dns_names):
        """Creates new Certificate instance"""
        model = {
            "apiVersion": "cert-manager.io/v1",
            "kind": "Certificate",
            "metadata": {"name": name, "namespace": cluster.project},
            "spec": {
                "secretName": secret_name,
                "issuerRef": {"name": issuer_ref.name, "kind": issuer_ref.kind},
                "dnsNames": dns_names,
            },
        }
        return cls(model, context=cluster.context)
