import logging
from collections import defaultdict, deque

import matplotlib.pyplot as plt
import MDAnalysis as mda
import numpy as np
from IPython.display import display
from joblib import delayed

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class MSDAnalysis(WidgetBase):
    name = "MSD Analysis"
    description = "Mean squared displacement analysis"

    _inputs = [
        {
            "attribute": "_run_mode",
            "name": "Run mode",
            "description": "The mode in which the widget is run",
            "type": "select",
            "items": [
                "serial",
                "parallel",
            ],
        },
        {
            "attribute": "selection",
            "name": "Selection",
            "description": "MDAnalysis selection phrase",
            "type": "str",
        },
        {
            "attribute": "msd_type",
            "name": "MSD type",
            "description": "Desired dimensions to be included in the MSD",
            "type": "select",
            "items": [
                "xyz",
                "xy",
                "yz",
                "xz",
                "x",
                "y",
                "z",
            ],
        },
        {
            "attribute": "log_scale",
            "name": "Log scale",
            "description": "Use a log scale for the axes",
            "type": "bool",
        },
        {
            "attribute": "custom_title",
            "name": "Custom title",
            "description": "Custom title for the plot",
            "type": "str",
        },
    ]

    def __init__(self):
        super().__init__()
        self.msd = None
        self.selection = "all"
        self.msd_type = "xyz"
        self.log_scale = False
        self.title = "MSD"
        self.custom_title = None
        self._setup_plot()

    def _setup_plot(self):
        """Setup matplotlib plot"""
        self.fig, self.ax = plt.subplots()
        (self.plot,) = self.ax.plot([], [])
        self.ax.set_xlabel(r"Lag time $\Delta$t (ps)")
        self.ax.set_ylabel(r"MSD ($\AA^2$)")
        self.ax.grid(True, linestyle="--", alpha=0.6)
        self._set_title()
        self._set_axes_scale()

    def _set_title(self):
        """Set plot title"""
        self.ax.set_title(self.custom_title if self.custom_title else self.title)

    def _set_axes_scale(self):
        """Set axes scale"""
        self.ax.set_xscale("log" if self.log_scale else "linear")
        self.ax.set_yscale("log" if self.log_scale else "linear")

    def _create_msd(self):
        """Create msd instance"""
        self.msd = SlidingWindowMSD(
            self.u,
            select=self.selection,
            msd_type=self.msd_type,
        )
        self.title = f"MSD of '{self.selection}'"
        self._set_title()

    def on_post_create(self):
        """on_post_create handler"""
        self._set_title()
        self._set_axes_scale()

    def on_post_connect(self):
        """on_post_connect handler"""
        self._create_msd()

    def on_input_change(self, attribute, _old_value, new_value):
        """on_input_change handler"""
        if attribute == "custom_title":
            self._set_title()
        elif attribute == "log_scale":
            self._set_axes_scale()
        elif attribute == "_run_mode":
            pass
        else:
            self._create_msd()

    def _compute(self, parallel: bool = False):
        """Run MSD for the current timesteps window"""
        return self.msd.run(parallel=parallel)

    def _update_plot(self, x_values, y_values):
        """Update plot with computed values"""
        self.plot.set_data(x_values, y_values)
        self.ax.relim()
        self.ax.autoscale_view()
        self.fig.canvas.draw()
        display(self.fig)

    def run_every_frame(self):
        """every-frame run handler"""
        x_values, y_values, _ = self._compute()
        self._update_plot(x_values, y_values)

    def get_parallel_job(self, batch_size):
        """get parallel job handler"""
        return delayed(self._compute)(parallel=True)

    def apply_parallel_results(self, values):
        """apply parallel results handler"""
        x_values, y_values, self.msd.msd_dict = values
        self._update_plot(x_values, y_values)


class SlidingWindowMSD:
    """Sliding Window MSD

    Calculate MSD for a sliding window of frames

    """

    def __init__(self, u: mda.Universe, select: str = "all", msd_type: str = "xyz"):
        self.u = u
        self.select = select
        self.msd_type = msd_type
        self._parse_msd_type()
        self.ag = u.select_atoms(self.select)
        self.msd_dict = defaultdict(lambda: deque(maxlen=self.u.trajectory.buffer_size))
        self.msd_dict[0] = deque([0])

    def _parse_msd_type(self):
        """Sets up the desired dimensionality of the MSD."""
        keys = {
            "x": [0],
            "y": [1],
            "z": [2],
            "xy": [0, 1],
            "xz": [0, 2],
            "yz": [1, 2],
            "xyz": [0, 1, 2],
        }
        self._dim = keys[self.msd_type.lower()]

    def run(self, parallel: bool = False) -> tuple:
        """Run MSD for the current window"""

        time_current = self.u.trajectory.ts.time
        positions_current = self.ag.positions[:, self._dim]

        for i in range(0, len(self.u.trajectory) - 1):
            ts = self.u.trajectory[i]  # set the buffered trajectory frame
            delta_t = round(time_current - ts.time, 2)
            disp = positions_current - self.ag.positions[:, self._dim]
            squared_disp = np.sum(disp**2, axis=1)
            msd = np.mean(squared_disp)
            self.msd_dict[delta_t].append(msd)

        delta_t_values = sorted(self.msd_dict.keys())
        avg_msds = np.array([np.mean(self.msd_dict[dt]) for dt in delta_t_values])

        return (
            delta_t_values,
            avg_msds,
            self.msd_dict if parallel else None,
        )
