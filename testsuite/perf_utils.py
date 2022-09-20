"""
This file contains methods that are used in performance testing
"""
import os
from urllib.parse import urlparse, ParseResult
from importlib import resources

import yaml
from hyperfoil.factories import HyperfoilFactory, Benchmark


def _load_benchmark(filename):
    """Loads benchmark"""
    with open(filename, encoding="utf8") as file:
        benchmark = Benchmark(yaml.load(file, Loader=yaml.Loader))
    return benchmark


def authority(url: str):
    """Returns hyperfoil authority format of URL <hostname>:<port> from given URL."""
    parsed_url = urlparse(url)
    return f"{parsed_url.hostname}:{parsed_url.port}"


def prepare_url(url: ParseResult) -> ParseResult:
    """ Adds port number to url if it is not set"""
    if not url.port:
        url_port = 80 if url.scheme == 'http' else 443
        url = url._replace(netloc=url.hostname + f':{url_port}')
    return url


class HyperfoilUtils:
    """
        Setup class for hyperfoil test and wrapper of Hyperfoil-python-client.
    """
    message_1kb = resources.files('testsuite.resources.performance.files').joinpath('message_1kb.txt')

    def __init__(self, hyperfoil_client, template_filename):
        self.hyperfoil_client = hyperfoil_client
        self.factory = HyperfoilFactory(hyperfoil_client)
        self.benchmark = _load_benchmark(template_filename)

    def create_benchmark(self):
        """Creates benchmark"""
        benchmark = self.benchmark.create()
        return self.factory.benchmark(benchmark).create()

    def update_benchmark(self, benchmark):
        """Updates benchmark"""
        self.benchmark.update(benchmark=benchmark)

    def add_shared_template(self, shared_template):
        """Updates benchmark with shared template"""
        self.benchmark.update(shared_template)

    def finalizer(self):
        """Hyperfoil factory opens a lot of file streams, we need to ensure that they are closed."""
        self.factory.close()

    def add_host(self, url: str, shared_connections: int, **kwargs):
        """Adds specific url host to the benchmark"""
        self.benchmark.add_host(url, shared_connections, **kwargs)

    def add_file(self, path):
        """Adds file to the benchmark"""
        filename = os.path.basename(path)
        self.factory.file(filename, open(path, 'r', encoding="utf8"))

    def generate_random_file(self, filename: str, size: int):
        """Generates and adds file with such filename and size to the benchmark"""
        self.factory.generate_random_file(filename, size)

    def generate_random_files(self, files: dict):
        """Generates and adds files to the benchmark"""
        for filename, size in files.items():
            self.factory.generate_random_file(filename, size)

    def add_user_key_auth(self, rhsso, url, filename):
        """
        TODO: add method for user key authentication
        """
        pass

    def add_rhsso_auth_token(self, rhsso, client_url, filename):
        """
        Adds csv file with data for access token creation. Each row consits of following columns:
        [authority url, rhsso url, rhsso path, body for token creation]
        :param rhsso_service_info: rhsso service info fixture
        :param applications: list of 3scale applications
        :param filename: name of csv file
        """
        rows = []
        token_url_obj = urlparse(rhsso.well_known['token_endpoint'])
        token_port = 80 if token_url_obj.scheme == 'http' else 443
        rows.append([client_url, f"{token_url_obj.hostname}:{token_port}", token_url_obj.path,
                     rhsso.token_body_creation()])
        self.factory.csv_data(filename, rows)
