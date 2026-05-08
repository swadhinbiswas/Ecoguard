"""Test drift detector with various scenarios."""

import pytest

from src.services.drift_detector import StatisticalDriftDetector, drift_detector


class TestStatisticalDriftDetector:
    def setup_method(self):
        self.detector = StatisticalDriftDetector(window_size=50)

    def test_empty_history_returns_zero(self):
        score = self.detector.update_and_check(100.0, 50)
        assert score == 0.0

    def test_small_history_returns_zero(self):
        for _ in range(5):
            self.detector.update_and_check(100.0, 50)
        score = self.detector.update_and_check(100.0, 50)
        assert score == 0.0

    def test_stable_history_low_drift(self):
        import numpy as np

        for val in [
            100.0,
            102.0,
            98.0,
            101.0,
            99.0,
            103.0,
            97.0,
            100.0,
            104.0,
            96.0,
            101.0,
            99.0,
            102.0,
            98.0,
            100.0,
            103.0,
            97.0,
            101.0,
            100.0,
            99.0,
        ]:
            self.detector.update_and_check(val, 50)
        score = self.detector.update_and_check(105.0, 50)
        assert score < 0.5

    def test_anomaly_increases_drift(self):
        import numpy as np

        for val in [
            100.0,
            102.0,
            98.0,
            101.0,
            99.0,
            103.0,
            97.0,
            100.0,
            104.0,
            96.0,
            101.0,
            99.0,
            102.0,
            98.0,
            100.0,
            103.0,
            97.0,
            101.0,
            100.0,
            99.0,
        ]:
            self.detector.update_and_check(val, 50)
        normal_score = self.detector.update_and_check(105.0, 50)
        self.detector._latency_history.pop()
        self.detector._token_history.pop()
        anomaly_score = self.detector.update_and_check(500.0, 200)
        assert anomaly_score > normal_score

    def test_window_size_enforced(self):
        detector = StatisticalDriftDetector(window_size=10)
        for i in range(15):
            detector.update_and_check(float(i * 10), i)
        assert len(detector._latency_history) == 10
        assert len(detector._token_history) == 10

    def test_drift_score_bounded(self):
        for _ in range(20):
            self.detector.update_and_check(100.0, 50)
        score = self.detector.update_and_check(10000.0, 50)
        assert 0.0 <= score <= 1.0


class TestDriftDetectorSingleton:
    def test_singleton_exists(self):
        assert drift_detector is not None

    def test_singleton_is_instance(self):
        assert isinstance(drift_detector, StatisticalDriftDetector)
