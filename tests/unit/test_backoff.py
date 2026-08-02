from src.config import RetryConfig
from src.orchestrator.pipeline import compute_backoff_delay


def test_backoff_grows_exponentially_without_jitter():
    config = RetryConfig(initial_delay_seconds=1.0, backoff_multiplier=2.0, max_delay_seconds=100.0, jitter=False)
    delays = [compute_backoff_delay(attempt, config) for attempt in range(5)]
    assert delays == [1.0, 2.0, 4.0, 8.0, 16.0]


def test_backoff_respects_max_delay_cap():
    config = RetryConfig(initial_delay_seconds=10.0, backoff_multiplier=2.0, max_delay_seconds=15.0, jitter=False)
    assert compute_backoff_delay(0, config) == 10.0
    assert compute_backoff_delay(1, config) == 15.0  # would be 20.0 uncapped
    assert compute_backoff_delay(5, config) == 15.0


def test_full_jitter_stays_within_bounds():
    config = RetryConfig(initial_delay_seconds=1.0, backoff_multiplier=2.0, max_delay_seconds=100.0, jitter=True)
    for attempt in range(6):
        cap = min(config.max_delay_seconds, config.initial_delay_seconds * (config.backoff_multiplier ** attempt))
        for _ in range(50):
            delay = compute_backoff_delay(attempt, config)
            assert 0.0 <= delay <= cap
