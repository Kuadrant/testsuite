"""OpenShift APIServer CR for reading/modifying cluster TLS security profile"""

from testsuite.kubernetes import KubernetesObject, modify


class APIServerCR(KubernetesObject):
    """Represents the OpenShift APIServer CR (config.openshift.io/v1, singleton named 'cluster')"""

    @property
    def tls_profile_type(self):
        """Returns the TLS security profile type or None if unset (defaults to Intermediate)"""
        if profile := self.model.spec.get("tlsSecurityProfile"):
            return profile.get("type")
        return None

    @modify
    def set_tls_profile(self, profile_type: str, min_version: str = None, ciphers: list = None):
        """Sets the TLS security profile type (Intermediate, Modern, Old, Custom)"""
        if profile_type != "Custom" and (min_version or ciphers):
            raise ValueError(f"min_version and ciphers are only supported with Custom profile, got {profile_type}")

        if profile_type is None:
            self.model.spec["tlsSecurityProfile"] = None
            return

        tls_security_profile = {"type": profile_type, profile_type.lower(): {}}
        if profile_type == "Custom":
            tls_security_profile["custom"] = {"minTLSVersion": min_version, "ciphers": ciphers}
        self.model.spec["tlsSecurityProfile"] = tls_security_profile
