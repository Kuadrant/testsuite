"""Module containing classes for working with TLS certificates"""
import dataclasses
import json
import shutil
import subprocess
from functools import cached_property
from importlib import resources
from typing import Optional, List, Dict, Any, Tuple, Collection, Union


class CFSSLException(Exception):
    """Common exception for CFSSL errors"""


@dataclasses.dataclass
class CertInfo:
    """Certificate configuration details"""
    hosts: Optional[Union[Collection[str], str]] = None
    ca: bool = False
    children: Optional[Dict[str, Optional["CertInfo"]]] = None
    names: Optional[List[Dict[str, str]]] = None


@dataclasses.dataclass
class Certificate:
    """Object representing Signed certificate"""
    key: str
    certificate: str
    chain: str


@dataclasses.dataclass
class UnsignedKey:
    """Object representing generated key waiting to be signed"""
    key: str
    csr: str


def build_cert_request_json(common_name: str,
                            names: Optional[List[Dict[str, str]]] = None,
                            hosts: Optional[Collection[str]] = None) -> dict:
    """
    Build certificate request for the CFSSL client
    :param common_name: certificate identifier
    :param names: certificate attributes
    :param hosts: certificate hosts
    :return: certificate request dictionary
    """
    return {
        "CN": common_name,
        "names": names,
        "hosts": hosts,
        "key": {
            "algo": "rsa",
            "size": 4096
        },
    }


class CFSSLClient:
    """Client for working with CFSSL library"""
    DEFAULT_NAMES = [
        {
            "O": "Red Hat Inc.",
            "OU": "IT",
            "L": "San Francisco",
            "ST": "California",
            "C": "US",
        }
    ]

    def __init__(self, binary) -> None:
        super().__init__()
        self.binary = binary

    def _execute_command(self,
                         command: str,
                         *args: str,
                         stdin: Optional[str] = None,
                         env: Optional[Dict[str, str]] = None):
        args = (self.binary, command, *args)
        try:
            response = subprocess.run(args,
                                      stderr=subprocess.PIPE,
                                      stdout=subprocess.PIPE,
                                      input=stdin,
                                      universal_newlines=bool(stdin),
                                      check=False,
                                      env=env)
            if response.returncode != 0:
                raise CFSSLException(f"CFSSL command {args} returned non-zero response code, error {response.stderr}")
            return json.loads(response.stdout)
        except Exception as exception:
            # If some error occurs, first check if the binary exists to throw better error
            if not self.exists:
                raise AttributeError("CFSSL binary does not exist") from exception
            raise exception

    @cached_property
    def exists(self):
        """Returns true if the binary exists and is correctly set up"""
        return shutil.which(self.binary)

    def generate_key(self, common_name: str, names: Optional[List[Dict[str, str]]] = None,
                     hosts: Optional[Collection[str]] = None) -> UnsignedKey:
        """Generates unsigned key"""
        data = build_cert_request_json(common_name, names, hosts)

        result = self._execute_command("genkey", "-", stdin=json.dumps(data))
        return UnsignedKey(key=result["key"], csr=result["csr"])

    def sign_intermediate_authority(self, key: UnsignedKey, certificate_authority: Certificate) -> Certificate:
        """Signs intermediate ca"""
        args = [
            "-ca=env:CA",
            "-ca-key=env:KEY",
            f"-config={resources.files('testsuite.resources.tls').joinpath('intermediate_config.json')}"
        ]
        result = self._execute_command("sign", *args, "-", stdin=key.csr, env={
            "CA": certificate_authority.certificate,
            "KEY": certificate_authority.key})
        return Certificate(key=key.key, certificate=result["cert"], chain=result["cert"])

    def sign(self, key: UnsignedKey, certificate_authority: Certificate) -> Certificate:
        """Signs unsigned key"""
        result = self._execute_command("sign", "-ca=env:CA", "-ca-key=env:KEY", "-", stdin=key.csr, env={
            "CA": certificate_authority.certificate,
            "KEY": certificate_authority.key})
        chain = result["cert"] + certificate_authority.chain
        return Certificate(key=key.key, certificate=result["cert"], chain=chain)

    def self_sign(self, common_name: str,
                  names: Optional[List[Dict[str, str]]] = None,
                  hosts: Optional[Collection[str]] = None) -> Certificate:
        """Creates self-signed certificate"""
        data = build_cert_request_json(common_name, names, hosts)

        result = self._execute_command("selfsign", common_name, "-", stdin=json.dumps(data))
        return Certificate(key=result["key"], certificate=result["cert"], chain=result["cert"])

    def create_authority(self,
                         common_name: str,
                         hosts: Collection[str],
                         names: Optional[List[Dict[str, str]]] = None,
                         certificate_authority: Optional[Certificate] = None) -> Certificate:
        """Generates self-signed root or intermediate CA certificate and private key
        Args:
            :param common_name: identifier to the certificate and key.
            :param hosts: list of hosts
            :param names: dict of all names
            :param certificate_authority: Optional Authority to sign this new authority, making it intermediate
        """
        names = names or self.DEFAULT_NAMES
        data = build_cert_request_json(common_name, names, hosts)

        result = self._execute_command("genkey", "-initca", "-", stdin=json.dumps(data))
        key = UnsignedKey(key=result["key"], csr=result["csr"])
        certificate = Certificate(key=result["key"], certificate=result["cert"], chain=result["cert"])
        if certificate_authority:
            certificate = self.sign_intermediate_authority(key, certificate_authority)
        return certificate

    def create(self,
               common_name: str,
               hosts: Collection[str],
               certificate_authority: Optional[Certificate] = None,
               names: Optional[List[Dict[str, str]]] = None) -> Certificate:
        """Create a new certificate.
        Args:
            :param common_name: Exact DNS match for which this certificate is valid
            :param hosts: Hosts field in the csr
            :param names: Names field in the csr
            :param certificate_authority: Certificate Authority to be used for signing
        """
        names = names or self.DEFAULT_NAMES
        if certificate_authority is None:
            certificate = self.self_sign(common_name, names, hosts)
        else:
            key = self.generate_key(common_name, names, hosts)
            certificate = self.sign(key, certificate_authority=certificate_authority)
        return certificate
