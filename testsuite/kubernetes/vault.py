"""HashiCorp Vault client for managing per-test credentials via hvac."""

import hvac


class Vault:
    """Manages Vault resources (secrets, policies, roles) for credential injection testing"""

    def __init__(self, url: str, token: str):
        self.url = url
        self._client = hvac.Client(url=url, token=token)

    def create_policy(self, name: str, path: str):
        """Create a read-only Vault policy for the given path"""
        self._client.sys.create_or_update_policy(name, f'path "{path}" {{ capabilities = ["read"] }}')

    def delete_policy(self, name: str):
        """Delete a Vault policy"""
        self._client.sys.delete_policy(name)

    def create_role(self, name: str, sa_names: list[str], sa_namespaces: list[str], policies: list[str]):
        """Create a Kubernetes auth role binding service accounts to policies"""
        self._client.auth.kubernetes.create_role(
            name,
            bound_service_account_names=sa_names,
            bound_service_account_namespaces=sa_namespaces,
            policies=policies,
            ttl="1h",
        )

    def delete_role(self, name: str):
        """Delete a Kubernetes auth role"""
        self._client.auth.kubernetes.delete_role(name)

    def store_secret(self, path: str, **data: str):
        """Store a KV v2 secret at the given path"""
        mount, _, secret_path = path.partition("/")
        self._client.secrets.kv.v2.create_or_update_secret(secret_path, secret=data, mount_point=mount)

    def delete_secret(self, path: str):
        """Delete a KV v2 secret and all its versions"""
        mount, _, secret_path = path.partition("/")
        self._client.secrets.kv.v2.delete_metadata_and_all_versions(secret_path, mount_point=mount)
