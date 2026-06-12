"""
Base Class for Widgets and Widget Manager
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from uuid import uuid1

import IPython
import MDAnalysis as mda


class WidgetBase(ABC):
    """WidgetBase

    This is the base class for all widgets.

    """

    def __init_subclass__(cls, **kwargs):
        """Register any derived class with the WidgetManager"""
        super().__init_subclass__(**kwargs)
        WidgetManager.register_class(cls)

    @abstractmethod
    def run(self, u):
        """Run method that derived classes implement"""


class WidgetManager:
    """WidgetManager

    This is the manager that manager all widgets.

    """

    _classes = {}
    _instances = {}

    def __init__(self):
        pass

    @property
    def classes(self):
        """Dictionary of registered widget classes keyed by widget name"""
        return self._classes

    @property
    def instances(self):
        """Dictionary of widget instances keyed by widget uuid"""
        return self._instances

    @classmethod
    def register_class(cls, widget_class: WidgetBase) -> None:
        """Register widget class

        Parameters
        ----------
        widget_class
            A widget class that is derived from WidgetBase

        """
        cls._validate_widget_class(widget_class)
        widget_name = widget_class.name
        if widget_name in cls._classes:
            raise ValueError(f"Widget name '{widget_name}' already registered")
        cls._classes[widget_name] = widget_class

    @classmethod
    def _validate_widget_class(cls, widget_class: WidgetBase) -> None:
        """Internal method to validate a widget class"""
        if not issubclass(widget_class, WidgetBase):
            raise ValueError(f"{widget_class} is not a widget class")
        if not hasattr(widget_class, "name"):
            raise ValueError("name not specified in widget class")
        if widget_class.run.__qualname__ == "WidgetBase.run":
            raise ValueError("run method not found in class")
        # TODO: add more validations

    def add_widget_instance(self, widget_name: str) -> str | None:
        """Add widget instance

        Add a widget instance based on the widget name already
        registered with the manager.

        Parameters
        ----------
        widget_name: str
            Name of the widget class registered

        Returns
        -------
        uuid of instance added or None

        """
        if widget_name in self.classes:
            widget_class = self.classes[widget_name]
            uuid = str(uuid1())
            self.instances[uuid] = widget_class()
            return uuid
        return None

    def delete_widget_instance(self, uuid: str) -> str | None:
        """Remove widget instance

        Remove widget instanced based on uuid returned during
        the instance creation using :meth:`add_widget_instance`

        Parameters
        ----------
        uuid: str
            The uuid of the instance to be removed

        Returns
        -------
        uuid of instance deleted or None

        """
        if uuid in self.instances:
            del self.instances[uuid]
            return uuid
        return None

    def run_widgets(self, u: mda.Universe) -> None:
        """Run widget instances

        Parameters
        ----------
        u: mda.Universe
            The universe object to use for analysis

        """
        for uuid, widget in self.instances.items():
            with _widget_uuid_in_metadata(uuid):
                widget.run(u)


@contextmanager
def _widget_uuid_in_metadata(uuid: str):
    """Internal: Add uuid in content metadata sent from kernel"""
    session = IPython.get_ipython().kernel.session
    original_send = session.send

    def patched_send(stream, msg_type_or_msg, *args, **kwargs):
        msg_type = None
        content = None
        if isinstance(msg_type_or_msg, str):
            msg_type = msg_type_or_msg
            if len(args) > 0 and isinstance(args[0], dict):
                content = args[0]
        elif isinstance(msg_type_or_msg, dict):
            msg_type = msg_type_or_msg.get("msg_type") or msg_type_or_msg.get(
                "header", {}
            ).get("msg_type")
            content = msg_type_or_msg.get("content", msg_type_or_msg)
        # Add widget uuid to metadata
        if msg_type == "display_data" and content is not None:
            content["metadata"]["widget_uuid"] = uuid
        return original_send(stream, msg_type_or_msg, *args, **kwargs)

    session.send = patched_send
    try:
        yield
    finally:
        session.send = original_send
