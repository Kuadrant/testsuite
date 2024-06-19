"""Monkeypatching land"""

import os

from openshift_client import context

# Default to kubectl instead of oc binary
context.default_oc_path = os.getenv("OPENSHIFT_CLIENT_PYTHON_DEFAULT_OC_PATH", "kubectl")
