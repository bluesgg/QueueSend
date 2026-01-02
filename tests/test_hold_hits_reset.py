"""Tests for hold_hits counter reset behavior.

Verifies that:
- hold_hits resets to 0 when diff < TH_HOLD
- hold_hits increments when diff >= TH_HOLD
- Consecutive hits requirement works correctly

See Executable Spec Section 7.2 for requirements.
"""

import pytest

from app.core.diff import HoldHitsTracker
from app.core.constants import HOLD_HITS_REQUIRED


class TestHoldHitsTrackerBasics:
    """Basic tests for HoldHitsTracker."""

    def test_initial_hold_hits_is_zero(self) -> None:
        """Tracker should start with hold_hits = 0."""
        tracker = HoldHitsTracker()
        assert tracker.hold_hits == 0

    def test_default_required_hits_is_two(self) -> None:
        """Default required hits should be 2 per spec."""
        tracker = HoldHitsTracker()
        assert tracker.required_hits == HOLD_HITS_REQUIRED
        assert tracker.required_hits == 2

    def test_custom_required_hits(self) -> None:
        """Tracker should accept custom required hits value."""
        tracker = HoldHitsTracker(required_hits=5)
        assert tracker.required_hits == 5


class TestHoldHitsIncrement:
    """Tests for hold_hits incrementing on hits."""

    def test_diff_above_threshold_increments(self) -> None:
        """diff >= TH_HOLD should increment hold_hits."""
        tracker = HoldHitsTracker()
        threshold = 0.02

        # diff = 0.03 >= 0.02 (threshold)
        tracker.update(0.03, threshold)
        assert tracker.hold_hits == 1

        # Another hit
        tracker.update(0.025, threshold)
        assert tracker.hold_hits == 2

    def test_diff_equal_to_threshold_is_hit(self) -> None:
        """diff == TH_HOLD should count as a hit (>= not just >)."""
        tracker = HoldHitsTracker()
        threshold = 0.02

        tracker.update(0.02, threshold)  # Exactly equal
        assert tracker.hold_hits == 1

    def test_consecutive_hits_accumulate(self) -> None:
        """Multiple consecutive hits should accumulate."""
        tracker = HoldHitsTracker()
        threshold = 0.02

        for i in range(5):
            tracker.update(0.05, threshold)
            assert tracker.hold_hits == i + 1


class TestHoldHitsReset:
    """Tests for hold_hits resetting to 0 on miss."""

    def test_diff_below_threshold_resets_to_zero(self) -> None:
        """diff < TH_HOLD should reset hold_hits to 0."""
        tracker = HoldHitsTracker()
        threshold = 0.02

        # Build up some hits
        tracker.update(0.03, threshold)
        tracker.update(0.03, threshold)
        assert tracker.hold_hits == 2

        # Miss: diff < threshold
        tracker.update(0.01, threshold)
        assert tracker.hold_hits == 0

    def test_single_miss_resets_all_progress(self) -> None:
        """A single miss should reset all accumulated hits."""
        tracker = HoldHitsTracker()
        threshold = 0.02

        # Build up 10 hits
        for _ in range(10):
            tracker.update(0.05, threshold)
        assert tracker.hold_hits == 10

        # Single miss resets everything
        tracker.update(0.01, threshold)
        assert tracker.hold_hits == 0

    def test_must_restart_counting_after_miss(self) -> None:
        """After a miss, counting must restart from 0."""
        tracker = HoldHitsTracker()
        threshold = 0.02

        # Hit, hit, miss, hit
        tracker.update(0.03, threshold)  # hit: 1
        tracker.update(0.03, threshold)  # hit: 2
        tracker.update(0.01, threshold)  # miss: 0
        tracker.update(0.03, threshold)  # hit: 1 (not 3!)

        assert tracker.hold_hits == 1


class TestHoldHitsPassCondition:
    """Tests for the pass condition (consecutive hits met)."""

    def test_returns_false_before_required_hits(self) -> None:
        """update() should return False before reaching required hits."""
        tracker = HoldHitsTracker(required_hits=2)
        threshold = 0.02

        # First hit - not enough
        passed = tracker.update(0.03, threshold)
        assert passed is False
        assert tracker.hold_hits == 1

    def test_returns_true_when_required_hits_reached(self) -> None:
        """update() should return True when required hits reached."""
        tracker = HoldHitsTracker(required_hits=2)
        threshold = 0.02

        tracker.update(0.03, threshold)  # 1
        passed = tracker.update(0.03, threshold)  # 2

        assert passed is True
        assert tracker.hold_hits == 2

    def test_returns_true_when_exceeding_required_hits(self) -> None:
        """update() should continue returning True after passing."""
        tracker = HoldHitsTracker(required_hits=2)
        threshold = 0.02

        tracker.update(0.03, threshold)  # 1
        tracker.update(0.03, threshold)  # 2 - pass
        passed = tracker.update(0.03, threshold)  # 3

        assert passed is True
        assert tracker.hold_hits == 3

    def test_miss_after_pass_resets(self) -> None:
        """Miss after passing should reset to 0."""
        tracker = HoldHitsTracker(required_hits=2)
        threshold = 0.02

        tracker.update(0.03, threshold)  # 1
        tracker.update(0.03, threshold)  # 2 - pass

        # Miss
        passed = tracker.update(0.01, threshold)
        assert passed is False
        assert tracker.hold_hits == 0


class TestHoldHitsResetMethod:
    """Tests for explicit reset() method."""

    def test_reset_clears_hold_hits(self) -> None:
        """reset() should set hold_hits to 0."""
        tracker = HoldHitsTracker()
        threshold = 0.02

        tracker.update(0.03, threshold)
        tracker.update(0.03, threshold)
        assert tracker.hold_hits == 2

        tracker.reset()
        assert tracker.hold_hits == 0


class TestHoldHitsScenarios:
    """Test realistic scenarios from the spec."""

    def test_scenario_det001a_consecutive_hits(self) -> None:
        """DET-001a: Consecutive hits should pass.

        When diff >= TH_HOLD for 2 consecutive samples, should pass.
        """
        tracker = HoldHitsTracker(required_hits=2)
        threshold = 0.02

        # Simulate: diff=0.03, 0.03 (two consecutive hits)
        diffs = [0.03, 0.03]
        results = [tracker.update(d, threshold) for d in diffs]

        assert results == [False, True]
        assert tracker.hold_hits == 2

    def test_scenario_det001b_interrupted_hits(self) -> None:
        """DET-001b: Interrupted hits should reset.

        Scenario from test plan:
        - Second 1: diff=0.03 (>= 0.02), hold_hits=1
        - Second 2: diff=0.01 (< 0.02), hold_hits=0
        - Second 3: diff=0.03 (>= 0.02), hold_hits=1
        - Second 4: diff=0.03 (>= 0.02), hold_hits=2 -> pass
        """
        tracker = HoldHitsTracker(required_hits=2)
        threshold = 0.02

        # Simulate the scenario
        scenarios = [
            (0.03, 1, False),   # Second 1: hit, hold_hits=1
            (0.01, 0, False),   # Second 2: miss, hold_hits=0
            (0.03, 1, False),   # Second 3: hit, hold_hits=1
            (0.03, 2, True),    # Second 4: hit, hold_hits=2, pass
        ]

        for diff, expected_hits, expected_pass in scenarios:
            passed = tracker.update(diff, threshold)
            assert tracker.hold_hits == expected_hits, \
                f"After diff={diff}: expected hold_hits={expected_hits}, got {tracker.hold_hits}"
            assert passed == expected_pass, \
                f"After diff={diff}: expected passed={expected_pass}, got {passed}"

    def test_scenario_multiple_misses_between_hits(self) -> None:
        """Multiple misses between hits should not affect the reset logic."""
        tracker = HoldHitsTracker(required_hits=2)
        threshold = 0.02

        # Hit once
        tracker.update(0.03, threshold)
        assert tracker.hold_hits == 1

        # Multiple misses
        tracker.update(0.01, threshold)
        assert tracker.hold_hits == 0
        tracker.update(0.005, threshold)
        assert tracker.hold_hits == 0
        tracker.update(0.015, threshold)
        assert tracker.hold_hits == 0

        # New hits
        tracker.update(0.03, threshold)
        assert tracker.hold_hits == 1
        tracker.update(0.03, threshold)
        assert tracker.hold_hits == 2

    def test_threshold_boundary_conditions(self) -> None:
        """Test behavior at threshold boundaries."""
        tracker = HoldHitsTracker()
        threshold = 0.02

        # Just below threshold - miss
        tracker.update(0.019999, threshold)
        assert tracker.hold_hits == 0

        # Exactly at threshold - hit
        tracker.update(0.02, threshold)
        assert tracker.hold_hits == 1

        # Just above threshold - hit
        tracker.update(0.020001, threshold)
        assert tracker.hold_hits == 2

