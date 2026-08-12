Adding Custom Widgets
=====================

Custom Widgets share the same underlying framework used by :doc:`built_in_widgets`.

A Custom Widget has to derive from the :class:`~mdadash.backend.widgets.base.WidgetBase`
base class and implement certain handlers as described here.

Widget Registration
-------------------

A Widget class must have a unique ``name`` class attibute to be registered.

.. code-block:: python

    class CustomWidget(WidgetBase)
        name = "Custom Widget"


An error is raised when the ``name`` class attribute is missing or if it exists but
is the same as an already registered widget. The uniqueness of the ``name`` exists to
prevent accidental overwrite of existing Widget classes. During testing or for use in
Notebooks, an option is provided to force re-registraion of a Widget class if a
``_override_name`` class attribute set to ``True`` exists in the class defintion.

In the example below, the ``CustomWidget`` class overrides the built-in 
:class:`~mdadash.backend.analyses.energies.AbsoluteTemperature` widget because it uses
the same name "Absolute Temperature".

.. code-block:: python

    class CustomWidget(WidgetBase)
        name = "Absolute Temperature"
        _override_name = True

This also enables customization of :doc:`built_in_widgets` by cloning them in Notebooks
and modifying them as needed.

An optional ``description`` class attribute can be used to specify more details about the
Widget and this gets displayed along with the name in the list of available Widgets in
the dashboard UI.

Run frequency and Run mode
--------------------------

The :class:`~mdadash.backend.widgets.base.WidgetBase` base class specifies two attributes
for all Widgets (defaults shown below):

.. code-block:: python

    _run_frequency = "every-frame"
    _run_mode = "serial"

``_run_frequency`` specifies how often the widget is run. It takes one of two values:
``every-frame`` or ``batch``.

``_run_mode`` specifies how the widget code is run. It takes one of two values:
``serial`` or ``parallel``.

By default, all Widgets run every frame serially (due to defaults above) unless the above
attributes are customized.

Both these attributes can be configured independent of each other. Which method(s) in
the Widget class gets invoked depend on both these attributes as described below.

.. note::

    A Widget can make these attributes dynamically changeable at runtime as well by making
    them as `Inputs`_, which then show corresponding options in the UI.

_run_frequency
~~~~~~~~~~~~~~

This attribute specifies how often the widget is run.

When ``_run_frequency`` is ``every-frame``, a method is invoked for every frame of the
trajectory iteration.

When ``_run_frequency`` is ``batch``, a method is invoked when a new batch of timesteps
is full. A global "Buffer / batch size" under "Settings > Universe Configuration" in the
dashboard controls the size of this timesteps buffer.

The method that is invoked depends on the ``_run_mode``.

If the ``_run_mode`` is ``parallel``, see the next section to see what gets invoked.

If the ``_run_mode`` is ``serial``:

* When ``_run_frequency`` is ``every-frame``,
  :meth:`~mdadash.backend.widgets.base.WidgetBase.run_every_frame` method is invoked.

* When ``_run_frequency`` is ``batch``,
  :meth:`~mdadash.backend.widgets.base.WidgetBase.run_batch` method is invoked.

_run_mode
~~~~~~~~~

This attribute specifies how the widget analysis code is run.

If the ``_run_mode`` is ``parallel`` for a given widget instance, a
:meth:`~mdadash.backend.widgets.base.WidgetBase.get_parallel_job` method is invoked to
retrieve the parallel job (a ``joblib.delayed`` tuple). A global "Parallel Jobs" under
"Settings > Dashboard Configuration" in the dasboard controls the total number of jobs
run in parallel during each iteration (``n_jobs`` param for ``joblib.Parallel`` call).

If a widget has ``_run_mode`` as ``parallel``, after the parallel job is completed, a
:meth:`~mdadash.backend.widgets.base.WidgetBase.apply_parallel_results` method is invoked
where the results from the parallel job are passed back to the instance. The instance can
apply the results back to its data structures (like updating it's values ``deque`` etc).

If a widget has ``_run_mode`` as ``serial``, one of the methods described in the previous
section are invoked.

Lifecycle methods
-----------------

There are several lifecycle methods that Widgets can implement (handlers) and these get
invoked by the dashboard framework at those stages.

* :meth:`~mdadash.backend.widgets.base.WidgetBase.on_post_create`
* :meth:`~mdadash.backend.widgets.base.WidgetBase.on_post_connect`
* :meth:`~mdadash.backend.widgets.base.WidgetBase.on_post_disconnect`
* :meth:`~mdadash.backend.widgets.base.WidgetBase.on_post_pause`
* :meth:`~mdadash.backend.widgets.base.WidgetBase.on_pre_resume`
* :meth:`~mdadash.backend.widgets.base.WidgetBase.on_input_change`

Inputs
------

Widgets can specify certain instance variables as inputs. These inputs show up in the
dashboard UI allowing users to configure and modify them at runtime.

An array of inputs is specified using the ``_inputs`` class attribute. Each item of this
array is a dict that has at minimum the following keys:

* ``attribute``

  * The attribute that will be get / set

* ``name``

  * The name to display in the UI for this input

* ``description``

  * An optional description to display as hint for the input in the UI

* ``type``

  * The type of the input. The following types are supported:

    * ``str`` - A text input
    * ``int`` - An integer number input
    * ``float`` - A decimal number input
    * ``bool`` - A switch input
    * ``select`` - A select dropdown with options
    * ``toggle`` - A binary toggle between two options
    * ``cell`` - A Notebook cell

Here is an example that creates a string input for the ``selection`` attribute:

.. code-block:: python

    {
        "attribute": "selection",
        "name": "Selection",
        "description": "MDAnalysis selection phrase",
        "type": "str",
    },

Some of the input types take additonal keys as shown in the examples below:

A select dropdown with options: 

.. code-block:: python

    {
        "attribute": "physical_property",
        "name": "Physical property",
        "description": "Physical property to analyze",
        "type": "select",
        "items": [
            "velocity",
            "position",
            "force",
        ],
    },

A toggle option:

.. code-block:: python

        {
            "attribute": "x_type",
            "name": "X-axis",
            "type": "toggle",
            "options": [
                {"name": "Time", "value": "time"},
                {"name": "Step", "value": "step"},
            ],
        },

The :mod:`~mdadash.backend.analyses.custom_code` Widget uses the ``cell`` input type as
shown below:

.. code-block:: python

    {
        "attribute": "setup_code",
        "name": "Setup code",
        "description": "This code will run once during widget creation",
        "type": "cell",
    },

The :meth:`~mdadash.backend.widgets.base.WidgetBase.on_input_change` handler gets invoked
for any input change made from the dasboard UI. Any validation errors raised by the
handler will show up as errors in the UI as well.

.. caution::

    Widgets will not be run as long as there are input errors as shown in the dasboard UI.
    Users will need to fix the inputs after which they will automatically run as configured.

Utils
-----

The following utils are available for Widgets to create alerts and pause the simulation
if required when any custom conditions are met in their code.

* :meth:`~mdadash.backend.widgets.base.WidgetBase.alert`
* :meth:`~mdadash.backend.widgets.base.WidgetBase.pause_simulation`


Automatic refresh
-----------------

All existing instances of a given Widget are automatically refreshed (re-created) when that
Widget class gets updated (typically through a Notebook cell execution in the dashboard).
All existing inputs are retained as is. This allows updates to the Widget class code reflect
immediately in existing Widget outputs.


----

.. tip::

    :mod:`Custom Code <mdadash.backend.analyses.custom_code>` built-in Widget provides a
    quick way to run simpler custom code.

    :doc:`built_in_widgets` can also be cloned into new Notebooks in the dasboard UI and
    customized as described in this document.


If you are adding a custom Widget that could be useful for others in the community, you can
create a `pull request <https://github.com/MDAnalysis/mdadash/pulls>`_ to make it part of the
:doc:`built_in_widgets`.
