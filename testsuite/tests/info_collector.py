"""
This module is not TRUE test. please do not rename to test_

It should only be executed in special mode defined by environment variable COLLECTOR_ENABLE=true
No xdist, only sequential. Supposed to be run before actual testsuite, isolated, to capture the values.

example:
COLLECTOR_ENABLE=true pytest --junit-xml="${RESULTS_PATH}/junit_00_info_collector.xml" -o junit_logging=all testsuite/tests/info_collector.py 
"""


import pytest
import os
import sys

import random

import subprocess


import logging
LOG = logging.getLogger(__name__)

KUBECTL_ENABLE=True

def kubectl(*args):
    cmd = ['kubectl']
    cmd.extend(args)
    result = None
    try:
        result = subprocess.check_output(cmd, text=True)
    except Exception as e:
        print(f'Failed with {e}')
    return result

def kube_image_version_parser(kubectl_output) -> list[tuple]:
    result = []
    lines = kubectl_output.replace("'", "").split(sep=' ')
    for line in lines:
        print(f'{line}')
        key, value = line.split(':')
        key = key.split('/')[-1]
        print(f'{key}:{value}')
        result.append((key,value))
    return result

@pytest.fixture(scope="session")
def properties_collector(record_testsuite_property):
    """ Main property collector
    
    Any property added here, will be promoted to Launch level
    
    """
    # record_testsuite_property("os", random.choice(["ocp-4.20", 'ocp-4.19', 'ocp-4.18']))
    # record_testsuite_property("platform", random.choice(['onprem', 'aws', 'rosa', 'aro', 'aws-osd', 'gcp-osd', 'gcp']))
    # record_testsuite_property("version", random.choice(['1.3.0', '1.3.0-rc1', '1.2.0', '1.1.0', '1.0.0']))
    # record_testsuite_property("build", random.choice(['kuadrant', 'rhcl']))
    # record_testsuite_property("level", 'release')

    if KUBECTL_ENABLE:
        kube_context = kubectl('config', 'current-context')
        print(f'{kube_context=}')
        if kube_context:
            record_testsuite_property('kube_context', kube_context.strip())
        kuadrant_version = kubectl('get', '-n', 'kuadrant-system', 'pods', "-o=jsonpath='{.items[*].spec.containers[*].image}'")
        if kuadrant_version:
            print(f'{kuadrant_version}')
            kuadrant_version_result = kube_image_version_parser(kuadrant_version)
            for k, v in kuadrant_version_result:
                record_testsuite_property(k, v)

        istio_version = kubectl('get', '-n', 'istio-system', 'pods', "-o=jsonpath='{.items[*].spec.containers[*].image}'")
        if istio_version:
            print(f'{istio_version}')
            istio_version_result = kube_image_version_parser(istio_version)
            for k,v in istio_version_result:
                if 'sail-operator' not in k:
                    continue
                record_testsuite_property(k,v)
            


@pytest.fixture(scope="session")
def secondary_properties(record_testsuite_property):
    """ Can be defined multiple times """
    record_testsuite_property('extra', 'secondary_properties')

@pytest.fixture(scope="session")
def last_properties(record_testsuite_property):
    """ Can be even done as teardown """
    yield
    record_testsuite_property('last', 'property')




@pytest.fixture(scope="session")
def rp_suite_description(record_testsuite_property):
    """ Ability to add something to suite description """
    suite_description="""
    # Not sure what to describe in test suite, but we can
    """
    record_testsuite_property("__rp_suite_description", suite_description)

@pytest.fixture(scope="session")
def rp_launch_description(record_testsuite_property):
    """ Direct modification of RP Lauch description via promoted attribute

    description provided via commandline will be per-pended to this
    """


    launch_description = """
    # Test Launch Description

    This is a sample description from the test pipeline

**Cluster Information (2 clusters):**
- https://console.cluster1.example.com (cluster1)
  - OCP: `4.18`
  - Kuadrant: `quay.io/kuadrant/kuadrant-operator:v1.3.1`
- https://console.cluster2.example.com (cluster2)
  - OCP: `4.20`
  - Kuadrant: `quay.io/kuadrant/kuadrant-operator:nightly-latest`
    """
    record_testsuite_property("__rp_launch_description", launch_description)

@pytest.mark.skipif(not os.environ.get('COLLECTOR_ENABLE'), reason="collector was not excplicitly enabled")
def test_collect(caplog, record_testsuite_property, properties_collector, secondary_properties, rp_launch_description, rp_suite_description):
    '''Main collector entrypoint'''

    record_testsuite_property('collector', 'true')
    # record_testsuite_property('__rp_dummy', 'this_should_not_be_there')

    LOG.info(f'Info message')
    LOG.debug(f'Log Debug')
    LOG.warning(f'warning message')
    LOG.error(f'error message')
    LOG.fatal(f'Fatal mesage')

    assert True

@pytest.mark.skipif(not os.environ.get('COLLECTOR_ENABLE'), reason="collector was not excplicitly enabled")
def test_kubectl():
    print


@pytest.mark.skipif(not os.environ.get('COLLECTOR_ENABLE'), reason="collector was not excplicitly enabled")
def test_controller():

    ## probably not worth it to collect uname from the pytest controller ?
    print(f'{os.uname()=}')
    # print(f'{os.=}')
    ## probably not worth it, since it will be collecting launch arguments for collector only
    print(f'{sys.argv=}')

    assert True