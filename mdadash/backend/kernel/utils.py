"""
Utils
"""


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

    def update(self, value: int | float) -> int:
        """Update current value and return trend

        Parameters
        ----------
        value: int | float
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
