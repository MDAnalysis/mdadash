"""
Common utils for use in kernel core
"""

from .core import comms, um


class EMATrend:
    """Exponential Moving Average (EMA) based Trend

    This utility class computes trend value based on short and long
    exponential moving averages based on the respective window sizes.

    """

    def __init__(self, short_window: int = 12, long_window: int = 26):
        self.alpha_short = 2.0 / (short_window + 1)
        self.alpha_long = 2.0 / (long_window + 1)
        self.ema_short = None
        self.ema_long = None

    def update(self, value: float) -> int:
        """Update current value and return trend

        Parameters
        ----------
        value: float
            The current value to update

        Returns
        -------
        trend: int
            Trend value as -1, 0 or 1

        """

        if self.ema_short is None:
            self.ema_short = value
            self.ema_long = value
            return 0
        self.ema_short = (self.alpha_short * value) + (
            (1.0 - self.alpha_short) * self.ema_short
        )
        self.ema_long = (self.alpha_long * value) + (
            (1.0 - self.alpha_long) * self.ema_long
        )
        return 1 if self.ema_short >= self.ema_long else -1


def _get_alert_timestamp() -> dict:
    """Internal: Get dict containing the current ts info to use as timestamp"""
    u = um[0]
    return {
        "frame": u.trajectory.frame,
        "time": u.trajectory.ts.data.get("time"),
        "step": u.trajectory.ts.data.get("step"),
    }


def alert(message: str) -> None:
    """Create an alert

    A timestamp based on the current timestep is automatically prepended
    to the message.

    Parameters
    ----------
    message: str
        The string message used for the alert

    """
    comms.send(
        {
            "alert": {
                "tsinfo": _get_alert_timestamp(),
                "message": message,
            }
        }
    )


def pause_simulation(message: str = "Paused simulation") -> None:
    """Pause the simulation

    Pause simulation and add an alert.

    Parameters
    ----------
    message: str
        The string message used for the alert

    """
    comms.send(
        {
            "pause_simulation": {
                "tsinfo": _get_alert_timestamp(),
                "message": message,
            }
        }
    )
