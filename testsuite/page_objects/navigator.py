"""Navigator for console plugin page objects"""

import abc
import inspect
from dataclasses import dataclass
from typing import Type, Callable

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

NAV_META = "nav_meta"
NAV_KWARGS = "nav_kwargs"
step_tree = {}


def step(cls, **kwargs):
    """Decorator that marks a method as a navigation step to a target page object"""

    def decorator(method):
        setattr(method, NAV_META, cls)
        setattr(method, NAV_KWARGS, kwargs)
        return method

    return decorator


class Navigable:
    """Base class for page objects that can be navigated to automatically"""

    def __init__(self, page):
        self.page = page

    def __init_subclass__(cls, **kwargs):
        """Registers navigation steps when a subclass is defined"""
        super().__init_subclass__(**kwargs)
        step_tree.update(
            {
                getattr(method, NAV_META): StepMetadata(cls, method)
                for _, method in inspect.getmembers(cls, inspect.isfunction)
                if method.__qualname__.split(".")[0] == cls.__name__ and hasattr(method, NAV_META)
            }
        )

    @abc.abstractmethod
    def is_displayed(self):
        """Returns locator(s) indicating whether this page is currently displayed"""


@dataclass
class StepMetadata:
    """Metadata linking a navigation method to its source and destination pages"""

    cls: Type[Navigable]
    method: Callable


class Navigator:
    """Automatically navigates between page objects using registered navigation steps"""

    def __init__(self, page: Page):
        self.page = page
        self.path: list[Callable] = []

    @staticmethod
    def _is_displayed(page):
        """Checks if a page object is currently displayed"""
        try:
            elements = page.is_displayed()
            if not isinstance(elements, tuple):
                elements = (elements,)

            is_displayed = True

            for element in elements:
                if not element.is_visible():
                    is_displayed = False
                    break
            return is_displayed
        except (PlaywrightTimeoutError, PlaywrightError) as e:
            raise AssertionError(f"{type(page).__name__} page not displayed: {e}") from e

    def _construct_path(self, destination: Type[Navigable]):
        """Builds navigation path to the destination page"""
        step_metadata = step_tree.get(destination)
        if step_metadata is None:
            return

        page_instance = step_metadata.cls(self.page)
        bound_method = getattr(page_instance, step_metadata.method.__name__)
        self.path.append(bound_method)
        if self._is_displayed(page_instance):
            return
        self._construct_path(step_metadata.cls)

    def _run(self):
        """Executes the constructed navigation path"""
        for i in reversed(self.path):
            try:
                i()
            except (PlaywrightTimeoutError, PlaywrightError) as e:
                raise AssertionError(f"Navigation failed at {type(i.__self__).__name__}: {e}") from e

    def navigate(self, dest_page: Type[Navigable]):
        """Navigates to the destination page and returns its instance"""
        self.path.clear()
        self._construct_path(dest_page)
        self._run()
        return dest_page(self.page)
