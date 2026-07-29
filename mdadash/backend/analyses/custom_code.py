"""
Custom user-defined code
"""

import logging
from typing import ClassVar

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class CustomCode(WidgetBase):
    """Custom Code

    This widget allows custom user-defined code to run during widget execution.
    The run frequency can be `every-frame` or `batch` similar to other widgets.
    User-defined code can be split into two parts - **Setup code** and **Execute code**
    as shown below:

    .. figure:: /_static/images/custom-code-widget-inputs.png
        :alt: Custom code widget inputs

    The code under **Setup code** is executed only once at the time of widget creation.
    Examples of code that goes here would be common functions, initialization blocks etc.

    The code under **Execute code** is executed as per the chosen run frequency. The
    outputs of this code is what will show up as the widget outputs. The outputs can
    include both text and images. Any errors, including syntax errors and code errors
    will show up in the output as well.

    The variable ``u`` points to the current MDAnalysis ``Universe`` and can be used
    directly in the code. There is support for code complete and inspect as shown below:

    .. figure:: /_static/images/custom-code-widget-code-complete-inspect.png
        :alt: Code complete and inspect

    Examples
    --------
    To print the current box volume, the following can be used in the **Execute code**:

    >>> print(f"Box Volume = {u.trajectory.ts.volume:.2f} Å³")

    To print / display the Kinetic Energy of an ``AtomGroup`` a simple KE function can
    defined in the **Setup code** as follows (executes only once):

    >>> import numpy as np
    >>> def ke(ag):
    >>>     return 0.5 * np.sum(ag.masses[:, np.newaxis] * (ag.velocities**2))

    The above function can be invoked in the **Execute code** section as follows:

    >>> ke1 = ke(u.select_atoms("protein"))
    >>> print(f"Protein KE = {ke1:.2f}")
    >>> plt1.show("KE (protein)", ke1)

    The **Setup code** can also include code to create ``matplotlib`` plots that can be
    displayed in the **Execute code** section.

    """

    name = "Custom Code"
    description = "Custom user-defined code"

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
        """on_post_connect handler"""
        self._run_code(self.setup_code)

    def run_every_frame(self):
        """every-frame run handler"""
        return self._run_code(self.execute_code)

    def run_batch(self):
        """batch run handler"""
        return self._run_code(self.execute_code)
