"""
Base Class for Widgets and Widget Manager
"""

import inspect
from abc import ABC
from contextlib import contextmanager
from threading import Thread
from typing import Any
from uuid import uuid1

import IPython
import MDAnalysis as mda
from joblib import Parallel


class WidgetBase(ABC):
    """WidgetBase

    This is the base class for all widgets.

    """

    _run_frequency = "per-frame"
    _run_mode = "serial"

    def __init_subclass__(cls, **kwargs):
        """Register any derived class with the WidgetManager"""
        super().__init_subclass__(**kwargs)
        WidgetManager.register_class(cls)

    def __init__(self):
        self.uid = None
        self.u = None
        self.uuid = None
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

    def on_post_create(self) -> None:
        """on_post_create handler

        This handler is called after the widget instance is created
        and after all the inputs are set.
        (widget create, duplicate, re-create from state)

        """

    def on_post_connect(self) -> None:
        """on_post_connect handler

        This handler is called after connecting to the simulation

        """

    def on_post_disconnect(self) -> None:
        """on_post_disconnect handler

        This handler is called after disconnection from simulation

        """

    def on_post_pause(self) -> None:
        """on_post_pause handler

        This handler is called after user pauses trajectory iteration

        """

    def on_pre_resume(self) -> None:
        """on_pre_resume handler

        This handler is called after user resumes trajectory iteration

        """

    def on_input_change(self, attribute: str, old_value: Any, new_value: Any) -> None:
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

    def run_per_frame(self) -> None:
        """run_per_frame handler

        This handler is called during every trajectory iteration if the run
        frequency is set to `per-frame` (`_run_frequency='per-frame'`). The
        trajectory timestep is the current frame.

        """

    def run_batch(self, batch_size: int) -> None:
        """run_batch handler

        This handler is called every time a new batch of timesteps is full
        and ready to be run if the run frequency is set to `batch`
        (`_run_frequency='batch'`).

        Parameters
        ----------
        batch_size: int
            The batch size, which indicates the number of buffered timesteps
            available in the buffer is passed

        """

    def get_parallel_job(self, batch_size: int) -> Any:
        """get_parallel_job handler

        This handler is called if the run mode is set to `parallel`
        (`_run_mode='parallel'`) to get the parallel job to run.

        Parameters
        ----------
        batch_size: int
            The configured batch size to use in the parallel jobs
            if their run frequency is `batch`

        Returns
        -------
        job: Any
            A joblib's delayed function

        """

    def apply_parallel_results(self, values: Any) -> None:
        """apply_parallel_results handler

        This handler is called with the results of the parallel job
        execution. This is invoked when the run mode is set to `parallel`
        (`_run_mode='parallel'`) after the parallel job completes.

        Parameters
        ----------
        values: Any
            The results returned by the parallel job run

        """


class WidgetManager:
    """WidgetManager

    This is the manager that manager all widgets.

    """

    _classes = {}
    _instances = {}

    def __init__(self):
        self.n_jobs = 2
        self._patch_IMDReader()

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
        cls._classes[widget_class.name] = widget_class

    @classmethod
    def _validate_widget_class(cls, widget_class: WidgetBase) -> None:
        """Internal: Method to validate a widget class"""
        if not issubclass(widget_class, WidgetBase):
            raise ValueError(f"{widget_class} is not a widget class")
        if not hasattr(widget_class, "name"):
            raise ValueError("name not specified in widget class")
        widget_name = widget_class.name
        if widget_name in cls._classes:
            raise ValueError(f"Widget name '{widget_name}' already registered")
        # check for one of the run methods to exist with correct params
        run_methods = {
            "run_per_frame": 1,
            "run_batch": 2,
        }
        has_valid_run_method = False
        for run_method, n_params in run_methods.items():
            method = getattr(widget_class, run_method)
            if method == getattr(WidgetBase, run_method):
                continue
            if not callable(method):
                continue
            signature = inspect.signature(method)
            has_valid_run_method = len(signature.parameters.values()) == n_params
            break
        if not has_valid_run_method:
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
                try:
                    handler()
                # pylint: disable=broad-exception-caught
                except Exception as e:  # pragma: no cover
                    print(e)

    def _set_widget_universe(
        self, widget: WidgetBase, uid: int, u: mda.Universe
    ) -> None:
        """Internal: Set the universe for instance"""
        if widget.uid == uid:
            widget._set_universe(u)
            # invoke the on_post_connect handler
            self._invoke_widget_lifecyle_method(widget, "on_post_connect")

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

    def _get_inputs_state(self, inputs):
        """Internal: Get all the input values and any errors"""
        return [
            {k: i[k] for k in ("attribute", "value", "error") if k in i} for i in inputs
        ]

    def add_widget_instance(
        self, uid: int, widget_name: str
    ) -> tuple[str, dict] | None:
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
        uuid of instance added and input details or None, None

        """
        if widget_name in self.classes:
            widget_class = self.classes[widget_name]
            uuid = str(uuid1())
            instance = widget_class()
            setattr(instance, "uid", uid)
            setattr(instance, "uuid", uuid)
            self.instances[uuid] = instance
            details = {
                "uid": uid,
                "class_name": widget_name,
                "inputs": self._get_inputs_state(instance._get_inputs()),
            }
            # invoke the on_post_create handler
            self._invoke_widget_lifecyle_method(instance, "on_post_create")
            return uuid, details
        return None, None

    def duplicate_widget_instance(self, uid: int, uuid: str) -> tuple[str, dict]:
        """Duplicate widget instance

        Duplicate widget instance based on existing instance uuid

        Parameters
        ----------
        uid: int
            Universe ID (index into universes array)

        uuid: str
            The uuid of the instance to be duplicated

        Returns
        -------
        uuid of new instance created and input details

        """
        # get existing instance
        instance = self.instances[uuid]
        # duplicate instance
        widget_class = instance.__class__
        new_instance = widget_class()
        setattr(new_instance, "uid", uid)
        # set inputs for new instance
        inputs = instance._get_inputs()
        for _input in inputs:
            attribute = _input["attribute"]
            setattr(new_instance, attribute, _input["value"])
            if _input["error"] is not None:
                new_instance._set_input_state(attribute, _input["error"])
        # add new instance to instances list
        new_uuid = str(uuid1())
        setattr(new_instance, "uuid", new_uuid)
        self.instances[new_uuid] = new_instance
        details = {
            "uid": uid,
            "class_name": widget_class.name,
            "inputs": self._get_inputs_state(inputs),
        }
        # invoke the on_post_create handler
        self._invoke_widget_lifecyle_method(new_instance, "on_post_create")
        return new_uuid, details

    def recreate_widget_instances(self, data: dict) -> None:
        """Recreate widget instances

        Recreate widget instances from state file

        Parameters
        ----------
        data: dict
            Data of the instances that need to be recreated

        """
        ret = True
        for widget_uuid, widget in data.items():
            try:
                widget_class = self.classes[widget["class_name"]]
                instance = widget_class()
                setattr(instance, "uid", widget["uid"])
                setattr(instance, "uuid", widget_uuid)
                inputs = widget["inputs"]
                for _input in inputs:
                    attribute = _input["attribute"]
                    setattr(instance, attribute, _input["value"])
                    if _input["error"] is not None:
                        instance._set_input_state(attribute, _input["error"])
                self.instances[widget_uuid] = instance
                # invoke the on_post_create handler
                self._invoke_widget_lifecyle_method(instance, "on_post_create")
            except KeyError as e:
                print(e)
                ret = False
        return ret

    def delete_widget_instance(self, uuid: str) -> str | None:
        """Remove widget instance

        Remove widget instance based on uuid returned during
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
        old_type = type(old_value)
        # set input using the same existing type
        setattr(widget, attribute, old_type(value))
        try:
            widget.on_input_change(attribute, old_value, value)
            widget._set_input_state(attribute)
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            widget._set_input_state(attribute, str(e))
        return False

    def update_n_jobs(self, data: dict) -> None:
        """Update n_jobs for joblib.Parallel"""
        self.n_jobs = data["n_jobs"]

    def _patch_IMDReader(self):
        """Internal: Patch `IMDReader` to make it serializable"""
        # pylint: disable=import-outside-toplevel
        from MDAnalysis.coordinates.IMD import IMDReader

        def custom_getstate(self):
            state = self.__dict__.copy()
            del state["_imdclient"]
            return state

        def custom_setstate(self, state):
            self.__dict__.update(state)
            self._imdclient = None

        IMDReader.__setstate__ = custom_setstate
        IMDReader.__getstate__ = custom_getstate

    def _run_parallel_jobs(self, parallel_widgets, batch_size, parallel_results):
        """Internal: Run parallel jobs using joblib.Parallel"""
        parallel_jobs = []
        for widget in parallel_widgets:
            parallel_jobs.append(widget.get_parallel_job(batch_size))
        try:
            results = Parallel(n_jobs=self.n_jobs, initializer=self._patch_IMDReader)(
                parallel_jobs
            )
            parallel_results.extend(results)
        # pylint: disable=broad-exception-caught
        except Exception as e:  # pragma: no cover
            print(f"parallel run failed with '{e}'")

    def run_widgets(self, uid: int, batch_ready: bool, batch_size: int) -> None:
        """Run widget instances

        Parameters
        ----------
        uid: int
            Universe ID (index into universes array)

        batch_ready: bool
            Flag indicating if a batch of timesteps is full

        batch_size: int
            Size of the batch

        """
        # collect widgets that need to be run
        parallel_widgets = []
        serial_widgets = []
        for widget in self.instances.values():
            # only run widget if there are no input errors
            if widget.uid != uid or widget._input_errors:
                continue
            if widget._run_mode == "parallel":
                if widget._run_frequency == "per-frame" or batch_ready:
                    parallel_widgets.append(widget)
            else:
                serial_widgets.append(widget)
        # run parallel widgets in separate thread
        if parallel_widgets:
            parallel_results = []
            parallel_thread = Thread(
                target=self._run_parallel_jobs,
                args=(
                    parallel_widgets,
                    batch_size,
                    parallel_results,
                ),
            )
            parallel_thread.start()
        # run serial widgets
        for widget in serial_widgets:
            with _widget_uuid_in_metadata(widget.uuid):
                try:
                    if widget._run_frequency == "per-frame":
                        widget.run_per_frame()
                    elif batch_ready:
                        widget.run_batch(batch_size)
                # pylint: disable=broad-exception-caught
                except Exception as e:  # pragma: no cover
                    print(f"{widget.uuid} serial run failed with '{e}'")
        # apply parallel results back
        if parallel_widgets:
            # wait for all parallel jobs to be done
            parallel_thread.join()
            for i, widget in enumerate(parallel_widgets):
                with _widget_uuid_in_metadata(widget.uuid):
                    widget.apply_parallel_results(parallel_results[i])


@contextmanager
def _widget_uuid_in_metadata(uuid: str):
    """Internal: Add uuid in content metadata sent from kernel"""
    session = IPython.get_ipython().kernel.session
    original_send = session.send

    def patched_send(stream, msg_type_or_msg, *args, **kwargs):
        msg_type = None
        content = None
        if isinstance(msg_type_or_msg, str):  # pragma: no cover
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
