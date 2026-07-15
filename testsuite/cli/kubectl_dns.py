"""Wrapper around kubectl-dns binary"""

import os
import subprocess


class KubectlDNS:
    """Wrapper on top of kubectl-dns binary"""

    def __init__(self, binary) -> None:
        super().__init__()
        self.binary = binary

    def run(self, *args, **kwargs):
        """Passes arguments to subprocess.run()"""
        args = (self.binary, *args)
        kwargs.setdefault("capture_output", True)
        kwargs.setdefault("text", True)

        if "env" in kwargs:
            env = os.environ.copy()
            env.update(kwargs["env"])
            kwargs["env"] = env

        return subprocess.run(args, **kwargs)  # pylint: disable= subprocess-run-check

    def add_active_group(self, cluster, group, domain, provider_ref):
        """Adds a group to the active groups TXT record"""
        return self.run(
            "add-active-group",
            group,
            "-y",
            "--domain",
            domain,
            "--providerRef",
            provider_ref,
            env={"KUBECONFIG": cluster.kubeconfig_path},
        )

    def remove_active_group(self, cluster, group, domain, provider_ref):
        """Removes a group from the active groups TXT record"""
        return self.run(
            "remove-active-group",
            group,
            "-y",
            "--domain",
            domain,
            "--providerRef",
            provider_ref,
            env={"KUBECONFIG": cluster.kubeconfig_path},
        )

    def add_cluster_secret(self, name, context, namespace, service_account, kubeconfig):
        """Generates a kubeconfig secret for a remote cluster"""
        return self.run(
            "add-cluster-secret",
            "--name",
            name,
            "--context",
            context,
            "--namespace",
            namespace,
            "--service-account",
            service_account,
            env={"KUBECONFIG": kubeconfig},
        )
