"""
Dashboard for tracking and analyzing live MD simulations with streaming.
"""

# Add imports here
from importlib.metadata import version

from .backend import analyses

__version__ = version("mdadash")

__all__ = [
    "analyses",
]
