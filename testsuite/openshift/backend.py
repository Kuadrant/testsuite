"""Backend for Openshift"""

from testsuite.lifecycle import LifecycleObject
from testsuite.gateway import Referencable


class Backend(LifecycleObject, Referencable):
    """Backend for Openshift"""
