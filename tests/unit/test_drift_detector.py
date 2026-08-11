import pytest
from src.domain.exceptions import ObservabilityException
from src.observability.drift import DriftDetector, DriftReport


def test_drift_detector_stable():
    detector = DriftDetector(psi_threshold=0.20, ks_threshold=0.25)
    baseline = [0.85, 0.87, 0.88, 0.89, 0.90, 0.91, 0.92, 0.93, 0.94, 0.95]
    detector.set_baseline(baseline)

    # Similar distribution from same domain
    for val in [0.85, 0.87, 0.88, 0.89, 0.90, 0.91, 0.92, 0.93, 0.94, 0.95]:
        detector.add_sample(val)

    report: DriftReport = detector.evaluate_drift("cosine_similarity")
    assert report.drift_detected is False
    assert report.status == "STABLE"
    assert report.psi_score < 0.10


def test_drift_detector_significant_drift():
    detector = DriftDetector(psi_threshold=0.20, ks_threshold=0.15)
    baseline = [0.90, 0.92, 0.95, 0.91, 0.89, 0.93, 0.94]
    detector.set_baseline(baseline)

    # Shifted distribution (much lower scores indicating query drift / OOD queries)
    for val in [0.20, 0.25, 0.30, 0.15, 0.22, 0.18]:
        detector.add_sample(val)

    report: DriftReport = detector.evaluate_drift("cosine_similarity")
    assert report.drift_detected is True
    assert report.status == "SIGNIFICANT_DRIFT"
    assert report.psi_score >= 0.20


def test_drift_detector_empty_baseline():
    detector = DriftDetector()
    with pytest.raises(ObservabilityException):
        detector.evaluate_drift()
