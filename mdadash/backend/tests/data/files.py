"""
Location of data files
======================

Use as ::

    from mdadash.backend.tests.data.files import *

"""

__all__ = [
    "TPR",
    "XTC",
]

import importlib.resources

data_directory = importlib.resources.files("mdadash") / "backend" / "tests" / "data"

TPR = data_directory / "adk_oplsaa.tpr"
XTC = data_directory / "adk_oplsaa.xtc"
