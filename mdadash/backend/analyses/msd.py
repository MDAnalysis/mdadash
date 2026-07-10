import logging

import matplotlib.pyplot as plt
from IPython.display import display
from joblib import delayed
from MDAnalysis.analysis import msd

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
            "attribute": "fft",
            "name": "FFT",
            "description": "Use a fast FFT based computation",
            "type": "bool",
        },
        {
            "attribute": "non_linear",
            "name": "Non-linear",
            "description": "Frames are non-linear",
            "type": "bool",
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
        self.fft = False
        self.non_linear = False
        self.log_scale = False
        self.title = "MSD"
        self.custom_title = None
        self._setup_plot()

    def _setup_plot(self):
        """Setup matplotlib plot"""
        self.fig, self.ax = plt.subplots()
        (self.plot,) = self.ax.plot([], [])
        self.ax.set_xlabel("Lag time")
        self.ax.set_ylabel("MSD")
        self.ax.grid(True)
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
        self.msd = msd.EinsteinMSD(
            self.u,
            select=self.selection,
            msd_type=self.msd_type,
            fft=self.fft,
            non_linear=self.non_linear,
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
        else:
            self._create_msd()

    def _compute(self):
        """Run MSD for the current timesteps window"""
        self.msd.run()
        return (
            self.msd.results.delta_t_values,
            self.msd.results.timeseries,
        )

    def _update_plot(self, values):
        """Update plot with computed values"""
        self.plot.set_data(*values)
        self.ax.relim()
        self.ax.autoscale_view()
        self.fig.canvas.draw()
        display(self.fig)

    def run_every_frame(self):
        """every-frame run handler"""
        self._update_plot(self._compute())

    def get_parallel_job(self, batch_size):
        """get parallel job handler"""
        return delayed(self._compute)()

    def apply_parallel_results(self, values):
        """apply parallel results handler"""
        self._update_plot(values)
