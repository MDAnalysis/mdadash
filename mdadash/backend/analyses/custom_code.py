"""
Custom user-defined code
"""

import logging
from typing import ClassVar

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class CustomCode(WidgetBase):
    """

    **Custom Code**

    This widget allows custom user-defined code to run during widget execution.
    The run frequency can be `every-frame` or `batch` similar to other widgets.
    User-defined code can be split into two parts - **Setup code** and **Execute code**
    as shown below:

    .. figure:: /_static/images/custom-code-widget-inputs.png
        :alt: Custom code widget inputs

    The code under **Setup code** is executed only once at the time of widget creation.
    Examples of code that goes here would be common functions, class definitions,
    initializations etc.

    The code under **Execute code** is executed as per the chosen run frequency. The
    outputs of this code will show up as the widget outputs. The outputs can include
    both text and images. Any errors, including syntax errors and code errors will show
    up in the output as well.

    The global variable ``u`` points to the current MDAnalysis ``Universe`` and can be
    used directly in the code. There is support for code complete and inspect as shown
    below:

    .. figure:: /_static/images/custom-code-widget-code-complete-inspect.png
        :alt: Code complete and inspect

    Examples
    --------

    **Example 1: Box volume**

    To print the current box volume, the following can be used in the **Execute code**:

    .. code-block:: python

        print(f"Box Volume = {u.trajectory.ts.volume:.2f} Å³")

    **Example 2: Kinetic Energy of an AtomGroup**

    To print and display the Kinetic Energy of an ``AtomGroup`` a simple KE function
    and plot can be defined in the **Setup code** as follows (executes only once):

    .. code-block:: python

        import numpy as np
        from collections import deque
        import matplotlib.pyplot as plt

        def ke(ag):
            return 0.5 * np.sum(ag.masses[:, np.newaxis] * (ag.velocities**2))

        class SimplePlot:
            def __init__(self, universe, max_values=100):
                self.u = universe
                self.times = deque(maxlen=max_values)
                self.values = deque(maxlen=max_values)

            def show(self, name, values):
                self.values.append(values)
                self.times.append(self.u.trajectory.ts.data["time"])
                plt.plot(self.times, self.values)
                plt.ylabel("Values")
                plt.xlabel("Time (ps)")
                plt.title(name)
                plt.grid(True)
                plt.show()

        plt1 = SimplePlot(u)

    The above function and plot can be invoked in the **Execute code** section as
    follows:

    .. code-block:: python

        ke1 = ke(u.select_atoms("protein"))
        print(f"Protein KE = {ke1:.2f}")
        plt1.show("KE (protein)", ke1)

    Here is an example of the widget output when the widget is running:

    .. figure:: /_static/images/custom-code-widget-output.png
        :alt: Widget output

    .. caution::

        Variables and Classes created in custom code blocks are common across the
        dashboard kernel and hence must be chosen to not overwrite each other.

    .. tip::
        This widget supports batching

    """

    name = "Custom Code"
    description = "Custom user-defined code"

    _doclink = (
        "https://mdadash.readthedocs.io/en/latest/autosummary/"
        "mdadash.backend.analyses.custom_code.html"
    )

    _inputs: ClassVar = [
        {
            "attribute": "_run_frequency",
            "name": "Run frequency",
            "description": "The frequency with which the widget is run",
            "type": "select",
            "items": [
                "every-frame",
                "batch",
            ],
        },
        {
            "attribute": "setup_code",
            "name": "Setup code",
            "description": "This code will run once during widget creation",
            "type": "cell",
        },
        {
            "attribute": "execute_code",
            "name": "Execute code",
            "description": "This code will run as per the run frequency",
            "type": "cell",
        },
    ]

    def __init__(self):
        super().__init__()
        self.setup_code = ""
        self.execute_code = ""

    def on_post_connect(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.on_post_connect` handler"""
        self._run_code(self.setup_code)

    def run_every_frame(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.run_every_frame` handler"""
        return self._run_code(self.execute_code)

    def run_batch(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.run_batch` handler"""
        return self._run_code(self.execute_code)
