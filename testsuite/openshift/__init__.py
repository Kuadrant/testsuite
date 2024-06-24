"""OpenShift common objects"""

import dataclasses
import functools
from dataclasses import dataclass, field
from typing import Optional, Literal

from openshift_client import APIObject, timeout, OpenShiftPythonException

from testsuite.lifecycle import LifecycleObject
from testsuite.utils import asdict


class OpenShiftObject(APIObject, LifecycleObject):
    """Custom APIObjects which tracks if the object was already committed to the server or not"""

    def __init__(self, dict_to_model=None, string_to_model=None, context=None):
        super().__init__(dict_to_model, string_to_model, context)
        self.committed = False

    def commit(self):
        """
        Creates object on the server and returns created entity.
        It will be the same class but attributes might differ, due to server adding/rejecting some of them.
        """
        self.create(["--save-config=true"])
        self.committed = True
        return self.refresh()

    def delete(self, ignore_not_found=True, cmd_args=None):
        """Deletes the resource, by default ignored not found"""
        with timeout(30):
            deleted = super().delete(ignore_not_found, cmd_args)
            self.committed = False
            return deleted

    def wait_until(self, test_function, timelimit=60):
        """Waits until the test function succeeds for this object"""
        try:
            with timeout(timelimit):
                success, _, _ = self.self_selector().until_all(
                    success_func=lambda obj: test_function(self.__class__(obj.model))
                )
                return success
        except OpenShiftPythonException as e:
            if "Timeout" in e.msg:
                return False
            raise e


class CustomResource(OpenShiftObject):
    """Custom APIObjects that implements methods that improves manipulation with CR objects"""

    def safe_apply(self):
        """
        Modifies the model of the apiobj and asserts if a change was applied to a resource.
        Uses modify_and_apply method from OpenshiftObject.
        """
        result, status = self.modify_and_apply(lambda _: True, retries=2)
        assert status, f"Unable to apply changes for APIObject with result: {result}"
        self.refresh()
        return result

    def wait_for_ready(self):
        """Waits until CR reports ready status"""
        success = self.wait_until(
            lambda obj: len(obj.model.status.conditions) > 0
            and all(x.status == "True" for x in obj.model.status.conditions)
        )
        assert success, f"{self.kind()} did got get ready in time"

    def __getitem__(self, name):
        return self.model.spec[name]

    def __setitem__(self, name, value):
        if dataclasses.is_dataclass(value):
            self.model.spec[name] = asdict(value)
        else:
            self.model.spec[name] = value


def modify(func):
    """Wraps method of a subclass of OpenShiftObject to use modify_and_apply when the object
    is already committed to the server, or run it normally if it isn't.
    All methods modifying the target object in any way should be decorated by this"""

    def _custom_partial(func, *args, **kwargs):
        """Custom partial function which makes sure that self is always assigned correctly"""

        def _func(self):
            func(self, *args, **kwargs)

        return _func

    @functools.wraps(func)
    def _wrap(self, *args, **kwargs):
        if self.committed:
            result, _ = self.modify_and_apply(_custom_partial(func, *args, **kwargs))
            assert result.status
        else:
            func(self, *args, **kwargs)

    return _wrap


@dataclass
class MatchExpression:
    """
    Data class intended for defining K8 Label Selector expressions.
    Used by selector.matchExpressions API key identity.
    """

    operator: Literal["In", "NotIn", "Exists", "DoesNotExist"]
    values: list[str]
    key: str = "group"


@dataclass
class Selector:
    """Dataclass for specifying selectors based on either expression or labels"""

    # pylint: disable=invalid-name
    matchExpressions: Optional[list[MatchExpression]] = field(default=None, kw_only=True)
    matchLabels: Optional[dict[str, str]] = field(default=None, kw_only=True)

    def __post_init__(self):
        if not (self.matchLabels is None) ^ (self.matchExpressions is None):
            raise AttributeError("`matchLabels` xor `matchExpressions` argument must be used")
