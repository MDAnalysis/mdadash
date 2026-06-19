"""
Base Class for Widgets and Widget Manager
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any
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

    def __init__(self):
        self.uid = None
        self.u = None
        self._input_errors = {}

    def _set_universe(self, u: mda.Universe):
        """Internal: Set the universe"""
        self.u = u

    def _get_inputs(self):
        """Internal: Get the current instance inputs"""
        inputs = getattr(self, "_inputs")
        for _input in inputs:
            # set the value and error states
            _input["value"] = getattr(self, _input["attribute"], None)
            _input["error"] = self._input_errors.get(_input["attribute"], None)
        return inputs

    def _set_input_state(self, attribute: str, error: str = None):
        """Internal: Set input attribute validation state"""
        if error is not None:
            self._input_errors[attribute] = error
        else:
            if attribute in self._input_errors:
                del self._input_errors[attribute]

    def post_connect(self):
        """post_connect handler

        This handler is called after connecting to the simulation

        """

    def post_disconnect(self):
        """post_disconnect handler

        This handler is called after disconnection from simulation

        """

    def post_pause(self):
        """post_pause handler

        This handler is called after user pauses trajectory iteration

        """

    def pre_resume(self):
        """pre_resume handler

        This handler is called after user resumes trajectory iteration

        """

    def on_input_change(self, attribute: str, old_value: Any, new_value: Any):
        """on_input_change handler

        This handler is called after a widget input has changed.
        Validations can be performed in this handler and any exceptions
        raised with messages will show up as errors in the UI

        Parameters
        ----------
        attribute: str
            The input attribute that changed

        old_value: Any
            The previous value held by this attribute

        new_value: Any
            The current value of this attribute

        """

    @abstractmethod
    def run(self):
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
        """Internal: Method to validate a widget class"""
        if not issubclass(widget_class, WidgetBase):
            raise ValueError(f"{widget_class} is not a widget class")
        if not hasattr(widget_class, "name"):
            raise ValueError("name not specified in widget class")
        if widget_class.run.__qualname__ == "WidgetBase.run":
            raise ValueError("run method not found in class")
        # TODO: add more validations

    def _invoke_widget_lifecyle_method(self, widget: WidgetBase, method: str) -> None:
        """Internal: Invoke the lifecycle method if implemented"""
        if widget._input_errors:
            # lifecycle methods not invoked when
            # there are input errors
            return
        if hasattr(widget, method):
            handler = getattr(widget, method)
            if callable(handler):
                handler()

    def _set_widget_universe(
        self, widget: WidgetBase, uid: int, u: mda.Universe
    ) -> None:
        """Internal: Set the universe for instance"""
        if widget.uid == uid:
            widget._set_universe(u)
            # invoke the post_connect handler
            self._invoke_widget_lifecyle_method(widget, "post_connect")

    def _set_universe(self, uid: int, u: mda.Universe, uuid: str = None) -> None:
        """Internal: Set the universe for all or given widget"""
        if uuid is None:
            for widget in self.instances.values():
                self._set_widget_universe(widget, uid, u)
        else:
            widget = self.instances[uuid]
            self._set_widget_universe(widget, uid, u)

    def _invoke_lifecycle_method(self, method: str) -> None:
        """Internal: Invoke given lifecycle method for all instances"""
        for widget in self.instances.values():
            self._invoke_widget_lifecyle_method(widget, method)

    def add_widget_instance(self, uid: int, widget_name: str) -> str | None:
        """Add widget instance

        Add a widget instance based on the widget name already
        registered with the manager.

        Parameters
        ----------
        uid: int
            Universe ID (index into universes array)

        widget_name: str
            Name of the widget class registered

        Returns
        -------
        uuid of instance added or None

        """
        if widget_name in self.classes:
            widget_class = self.classes[widget_name]
            uuid = str(uuid1())
            instance = widget_class()
            setattr(instance, "uid", uid)
            self.instances[uuid] = instance
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

    def get_inputs(self, uuid: str) -> list:
        """Get inputs for widget instance

        Parameters
        ----------
        uuid: str
            The uuid of the widget instance

        Returns
        -------
        response: list
            List of input dicts

        """
        widget = self.instances[uuid]
        return widget._get_inputs()

    def set_input(self, uuid: str, attribute: str, value: Any) -> bool:
        """Set input for a widget instance attribute

        Parameters
        ----------
        uuid: str
            The uuid of the widget instance

        attribute: str
            The input attribute to set

        value: Any
            The value to set for the attribute

        Returns
        -------
        response: bool
            True or False to indicate if input validation succeeded

        """
        widget = self.instances[uuid]
        old_value = getattr(widget, attribute, value)
        setattr(widget, attribute, value)
        try:
            widget.on_input_change(attribute, old_value, value)
            widget._set_input_state(attribute)
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            widget._set_input_state(attribute, str(e))
        return False

    def run_widgets(self, uid: int) -> None:
        """Run widget instances

        Parameters
        ----------
        uid: int
            Universe ID (index into universes array)

        """
        for uuid, widget in self.instances.items():
            # only run widget if there are no input errors
            if widget.uid == uid and not widget._input_errors:
                with _widget_uuid_in_metadata(uuid):
                    try:
                        widget.run()
                    # pylint: disable=broad-exception-caught
                    except Exception as e:  # pragma no cover
                        print(f"{uuid} run failed with '{e}'")


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
