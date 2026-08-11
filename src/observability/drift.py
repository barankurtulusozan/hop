from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from src.domain.exceptions import ObservabilityException


@dataclass
class DriftReport:
    metric_name: str
    psi_score: float
    ks_statistic: float
    drift_detected: bool
    status: str
    samples_count: int
    details: dict[str, Any] = field(default_factory=dict)


class DriftDetector:
    """Real-time Embedding & Concept Drift Detection Engine utilizing PSI and KS-test statistics."""

    def __init__(self, psi_threshold: float = 0.20, ks_threshold: float = 0.15):
        self.psi_threshold = psi_threshold
        self.ks_threshold = ks_threshold
        self._baseline_scores: list[float] = []
        self._current_scores: list[float] = []

    def set_baseline(self, scores: list[float]) -> None:
        """Initialize baseline score distribution (e.g. baseline query similarity scores)."""
        if not scores:
            raise ObservabilityException("Baseline scores list cannot be empty")
        self._baseline_scores = sorted(scores)

    def add_sample(self, score: float) -> None:
        """Add incoming inference score sample."""
        self._current_scores.append(score)

    def reset_current(self) -> None:
        """Reset current tracking window."""
        self._current_scores = []

    @staticmethod
    def _calculate_psi(baseline: list[float], current: list[float], num_bins: int = 5) -> float:
        """Calculate Population Stability Index (PSI) between baseline and current distributions."""
        if not baseline or not current:
            return 0.0

        min_val = min(min(baseline), min(current))
        max_val = max(max(baseline), max(current))

        if min_val == max_val:
            return 0.0

        bin_width = (max_val - min_val) / num_bins
        bins = [min_val + i * bin_width for i in range(num_bins + 1)]
        bins[-1] += 1e-5  # Expand last bin slightly to include max value

        baseline_counts = [0] * num_bins
        current_counts = [0] * num_bins

        for val in baseline:
            for i in range(num_bins):
                if bins[i] <= val < bins[i + 1]:
                    baseline_counts[i] += 1
                    break

        for val in current:
            for i in range(num_bins):
                if bins[i] <= val < bins[i + 1]:
                    current_counts[i] += 1
                    break

        total_b = len(baseline)
        total_c = len(current)

        psi = 0.0
        epsilon = 1e-4  # Smoothing factor for zero counts

        for b_count, c_count in zip(baseline_counts, current_counts):
            pct_b = (b_count + epsilon) / (total_b + epsilon * num_bins)
            pct_c = (c_count + epsilon) / (total_c + epsilon * num_bins)
            psi += (pct_c - pct_b) * math.log(pct_c / pct_b)

        return round(psi, 4)

    @staticmethod
    def _calculate_ks(baseline: list[float], current: list[float]) -> float:
        """Calculate Kolmogorov-Smirnov (KS) two-sample test statistic."""
        if not baseline or not current:
            return 0.0

        combined = sorted(set(baseline + current))
        b_sorted = sorted(baseline)
        c_sorted = sorted(current)

        n_b = len(b_sorted)
        n_c = len(c_sorted)

        max_diff = 0.0

        for val in combined:
            # Empirical CDF for baseline
            cdf_b = sum(1 for x in b_sorted if x <= val) / n_b
            # Empirical CDF for current
            cdf_c = sum(1 for x in c_sorted if x <= val) / n_c
            diff = abs(cdf_b - cdf_c)
            if diff > max_diff:
                max_diff = diff

        return round(max_diff, 4)

    def evaluate_drift(self, metric_name: str = "similarity_distribution") -> DriftReport:
        """Evaluate baseline vs current distribution for drift."""
        if not self._baseline_scores:
            raise ObservabilityException("Cannot evaluate drift without a baseline distribution")
        if not self._current_scores:
            raise ObservabilityException("Cannot evaluate drift without current samples")

        psi = self._calculate_psi(self._baseline_scores, self._current_scores)
        ks = self._calculate_ks(self._baseline_scores, self._current_scores)

        drift_detected = psi >= self.psi_threshold or ks >= self.ks_threshold

        if psi < 0.10:
            status = "STABLE"
        elif psi < 0.20:
            status = "MODERATE_SHIFT"
        else:
            status = "SIGNIFICANT_DRIFT"

        return DriftReport(
            metric_name=metric_name,
            psi_score=psi,
            ks_statistic=ks,
            drift_detected=drift_detected,
            status=status,
            samples_count=len(self._current_scores),
            details={
                "psi_threshold": self.psi_threshold,
                "ks_threshold": self.ks_threshold,
                "baseline_count": len(self._baseline_scores),
            },
        )
