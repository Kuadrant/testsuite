"""OpenShift common objects"""
import functools
from dataclasses import dataclass, field
from typing import Optional, Literal

from openshift import APIObject, timeout

from testsuite.lifecycle import LifecycleObject


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
