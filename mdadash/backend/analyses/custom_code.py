"""
Custom user-defined code
"""

import logging
from typing import ClassVar

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class CustomCode(WidgetBase):
    """Custom Code

    Custom user-defined code

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
