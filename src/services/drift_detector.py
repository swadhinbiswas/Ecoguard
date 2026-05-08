from typing import List

import numpy as np


class StatisticalDriftDetector:
    """
    Placeholder implementation for monitoring statistical drift in inference distribution.
    Maintains a rolling window to detect distribution shifts in generation length and latency.
    """
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self._latency_history: List[float] = []
        self._token_history: List[int] = []

    def update_and_check(self, latency: float, token_count: int) -> float:
        self._latency_history.append(latency)
        self._token_history.append(token_count)

        if len(self._latency_history) > self.window_size:
            self._latency_history.pop(0)
            self._token_history.pop(0)

        # Require a minimum baseline to calculate meaningful drift
        if len(self._latency_history) < 10:
            return 0.0

        mean_latency = np.mean(self._latency_history[:-1])
        std_latency = np.std(self._latency_history[:-1]) + 1e-6

        # Calculate a simple Z-Score for latency as our synthetic drift score placeholder
        z_score = abs(latency - mean_latency) / std_latency

        # Normalize arbitrarily to a 0.0 - 1.0 risk scale for the API
        drift_score = min(1.0, z_score / 10.0)
        return float(drift_score)

drift_detector = StatisticalDriftDetector()
