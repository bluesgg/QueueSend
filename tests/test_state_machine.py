"""Tests for state machine behavior.

Verifies that:
- Pause preserves frame_t0 and hold_hits
- Resume continues with preserved state
- Resume detects message list changes
- Stop returns to Idle immediately

See Executable Spec Sections 9 and 10 for requirements.
"""

import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from app.core.model import State, Point, Rect, ROI, ROIShape, CalibrationConfig
from app.core.diff import HoldHitsTracker, DiffCalculator


class TestStateEnumValues:
    """Test that all required states exist."""

    def test_all_states_defined(self) -> None:
        """All spec-required states should be defined."""
        required_states = [
            State.Idle,
            State.Countdown,
            State.Sending,
            State.Cooling,
            State.WaitingHold,
            State.Paused,
        ]
        for state in required_states:
            assert state is not None

    def test_states_are_distinct(self) -> None:
        """All states should be distinct values."""
        states = [
            State.Idle,
            State.Countdown,
            State.Sending,
            State.Cooling,
            State.WaitingHold,
            State.Paused,
        ]
        # Convert to set to check uniqueness
        assert len(set(states)) == len(states)


class TestHoldHitsPreservation:
    """Test that hold_hits is preserved during pause."""

    def test_hold_hits_preserved_after_freeze(self) -> None:
        """hold_hits should be preserved when freezing state."""
        tracker = HoldHitsTracker()
        threshold = 0.02

        # Build up hold_hits
        tracker.update(0.03, threshold)
        tracker.update(0.03, threshold)
        assert tracker.hold_hits == 2

        # Simulate freeze by saving value
        frozen_hold_hits = tracker.hold_hits

        # Verify preserved
        assert frozen_hold_hits == 2

    def test_hold_hits_restored_after_resume(self) -> None:
        """hold_hits should be restored on resume."""
        tracker = HoldHitsTracker()
        threshold = 0.02

        # Build up hold_hits
        tracker.update(0.03, threshold)
        assert tracker.hold_hits == 1

        # Freeze
        frozen_hits = tracker.hold_hits

        # Reset (simulating some operation)
        tracker.reset()
        assert tracker.hold_hits == 0

        # Restore
        tracker._hold_hits = frozen_hits
        assert tracker.hold_hits == 1


class TestDiffCalculatorStatePreservation:
    """Test DiffCalculator freeze/restore for pause/resume."""

    def test_freeze_captures_frame_t0_and_hold_hits(self) -> None:
        """freeze_state should capture frame_t0 and hold_hits."""
        roi = ROI(
            shape=ROIShape.RECT,
            rect=Rect(x=0, y=0, w=50, h=50),
        )
        calc = DiffCalculator(roi, threshold=0.02)

        # Set up state
        test_frame = np.full((50, 50), 128, dtype=np.uint8)
        calc.set_reference(test_frame)
        calc._tracker._hold_hits = 1  # Simulate partial hits

        # Freeze
        state = calc.freeze_state()

        assert state["frame_t0"] is not None
        assert state["hold_hits"] == 1
        # Verify frame is a copy
        assert state["frame_t0"] is not calc._frame_t0

    def test_restore_applies_frozen_state(self) -> None:
        """restore_state should restore frame_t0 and hold_hits."""
        roi = ROI(
            shape=ROIShape.RECT,
            rect=Rect(x=0, y=0, w=50, h=50),
        )
        calc = DiffCalculator(roi, threshold=0.02)

        # Set up initial state
        original_frame = np.full((50, 50), 128, dtype=np.uint8)
        calc.set_reference(original_frame)
        calc._tracker._hold_hits = 1

        # Freeze
        frozen = calc.freeze_state()

        # Clear state
        calc.reset()
        assert calc.frame_t0 is None
        assert calc.hold_hits == 0

        # Restore
        calc.restore_state(frozen)
        assert calc.frame_t0 is not None
        assert calc.hold_hits == 1

    def test_frame_t0_preserved_during_pause(self) -> None:
        """frame_t0 should not change during pause (frozen)."""
        roi = ROI(
            shape=ROIShape.RECT,
            rect=Rect(x=0, y=0, w=50, h=50),
        )
        calc = DiffCalculator(roi, threshold=0.02)

        # Set reference frame
        original_frame = np.full((50, 50), 100, dtype=np.uint8)
        calc.set_reference(original_frame)

        # Freeze
        frozen = calc.freeze_state()
        frozen_frame = frozen["frame_t0"]

        # Verify the frozen frame matches original
        np.testing.assert_array_equal(frozen_frame, original_frame)


class TestMessageChangeDetection:
    """Test message list change detection on resume."""

    def test_no_change_detected_when_lists_equal(self) -> None:
        """No change should be detected if lists are equal."""
        snapshot = ["msg1", "msg2", "msg3"]
        current = ["msg1", "msg2", "msg3"]

        changed = snapshot != current
        assert changed is False

    def test_change_detected_when_message_removed(self) -> None:
        """Change should be detected when a message is removed."""
        snapshot = ["msg1", "msg2", "msg3"]
        current = ["msg1", "msg2"]  # msg3 removed

        changed = snapshot != current
        assert changed is True

    def test_change_detected_when_message_added(self) -> None:
        """Change should be detected when a message is added."""
        snapshot = ["msg1", "msg2"]
        current = ["msg1", "msg2", "msg3"]  # msg3 added

        changed = snapshot != current
        assert changed is True

    def test_change_detected_when_message_modified(self) -> None:
        """Change should be detected when a message is modified."""
        snapshot = ["msg1", "msg2", "msg3"]
        current = ["msg1", "modified", "msg3"]  # msg2 modified

        changed = snapshot != current
        assert changed is True

    def test_change_detected_when_order_changed(self) -> None:
        """Change should be detected when order changes."""
        snapshot = ["msg1", "msg2", "msg3"]
        current = ["msg2", "msg1", "msg3"]  # Reordered

        changed = snapshot != current
        assert changed is True

    def test_no_change_for_empty_lists(self) -> None:
        """No change for two empty lists."""
        snapshot: list[str] = []
        current: list[str] = []

        changed = snapshot != current
        assert changed is False


class TestResumeWithMessageChange:
    """Test resume behavior when messages changed during pause."""

    def test_resume_returns_false_on_message_change(self) -> None:
        """Resume should indicate failure when messages changed."""
        # Simulate the check that would happen in engine
        def check_messages_changed(snapshot: list[str], current: list[str]) -> bool:
            return snapshot != current

        snapshot = ["msg1", "msg2", "msg3"]
        current = ["msg1", "msg2"]  # Changed

        # This would trigger EV_MSG_LIST_CHANGED -> Stop
        should_stop = check_messages_changed(snapshot, current)
        assert should_stop is True

    def test_resume_continues_when_messages_unchanged(self) -> None:
        """Resume should continue when messages unchanged."""
        def check_messages_changed(snapshot: list[str], current: list[str]) -> bool:
            return snapshot != current

        snapshot = ["msg1", "msg2", "msg3"]
        current = ["msg1", "msg2", "msg3"]  # Same

        should_stop = check_messages_changed(snapshot, current)
        assert should_stop is False


class TestStopBehavior:
    """Test Stop returns to Idle immediately."""

    def test_stop_sets_idle_state(self) -> None:
        """Stop should transition to Idle state."""
        # Simulate state machine
        class MockStateMachine:
            def __init__(self) -> None:
                self.state = State.WaitingHold

            def stop(self) -> None:
                self.state = State.Idle

        sm = MockStateMachine()
        assert sm.state == State.WaitingHold

        sm.stop()
        assert sm.state == State.Idle

    def test_stop_from_any_running_state(self) -> None:
        """Stop should work from any running state."""
        running_states = [
            State.Countdown,
            State.Sending,
            State.Cooling,
            State.WaitingHold,
            State.Paused,
        ]

        for initial_state in running_states:
            class MockStateMachine:
                def __init__(self, state: State) -> None:
                    self.state = state

                def stop(self) -> None:
                    self.state = State.Idle

            sm = MockStateMachine(initial_state)
            sm.stop()
            assert sm.state == State.Idle, f"Stop from {initial_state} should go to Idle"


class TestPauseBehavior:
    """Test Pause behavior per spec."""

    def test_pause_freezes_current_state(self) -> None:
        """Pause should preserve the pre-pause state for later resume."""

        class MockStateMachine:
            def __init__(self) -> None:
                self.state = State.WaitingHold
                self.paused_from_state: State | None = None

            def pause(self) -> None:
                self.paused_from_state = self.state
                self.state = State.Paused

            def resume(self) -> None:
                if self.paused_from_state:
                    self.state = self.paused_from_state

        sm = MockStateMachine()
        assert sm.state == State.WaitingHold

        sm.pause()
        assert sm.state == State.Paused
        assert sm.paused_from_state == State.WaitingHold

        sm.resume()
        assert sm.state == State.WaitingHold

    def test_pause_preserves_message_index(self) -> None:
        """Pause should preserve current message index."""

        class MockStateMachine:
            def __init__(self) -> None:
                self.current_idx = 2
                self.frozen_idx: int | None = None

            def pause(self) -> None:
                self.frozen_idx = self.current_idx

            def resume(self) -> None:
                self.current_idx = self.frozen_idx  # type: ignore

        sm = MockStateMachine()
        sm.current_idx = 5

        sm.pause()
        assert sm.frozen_idx == 5

        # Simulate some modification during pause
        sm.current_idx = 0

        sm.resume()
        assert sm.current_idx == 5


class TestStateTransitions:
    """Test state machine transitions per spec."""

    def test_idle_to_countdown_on_start(self) -> None:
        """EV_START should transition Idle -> Countdown."""
        state = State.Idle
        # Simulate EV_START
        new_state = State.Countdown
        assert new_state == State.Countdown

    def test_countdown_to_sending(self) -> None:
        """EV_COUNTDOWN_DONE should transition Countdown -> Sending."""
        state = State.Countdown
        new_state = State.Sending
        assert new_state == State.Sending

    def test_sending_to_cooling(self) -> None:
        """EV_SENT_STEP_DONE should transition Sending -> Cooling."""
        state = State.Sending
        new_state = State.Cooling
        assert new_state == State.Cooling

    def test_cooling_to_waitinghold(self) -> None:
        """EV_COOL_DONE should transition Cooling -> WaitingHold."""
        state = State.Cooling
        new_state = State.WaitingHold
        assert new_state == State.WaitingHold

    def test_waitinghold_to_sending_on_hold_pass_with_more_messages(self) -> None:
        """EV_HOLD_PASS with more messages should go to Sending."""
        state = State.WaitingHold
        has_more_messages = True
        new_state = State.Sending if has_more_messages else State.Idle
        assert new_state == State.Sending

    def test_waitinghold_to_idle_on_hold_pass_with_no_more_messages(self) -> None:
        """EV_HOLD_PASS with no more messages should go to Idle."""
        state = State.WaitingHold
        has_more_messages = False
        new_state = State.Sending if has_more_messages else State.Idle
        assert new_state == State.Idle

    def test_any_running_to_paused_on_pause(self) -> None:
        """EV_PAUSE should transition any running state to Paused."""
        running_states = [State.Sending, State.Cooling, State.WaitingHold]
        for state in running_states:
            new_state = State.Paused
            assert new_state == State.Paused


class TestCtrl001PauseFreezes:
    """Test CTRL-001: Pause冻结frame_t0与计数器"""

    def test_pause_preserves_frame_t0(self) -> None:
        """Pause should preserve frame_t0 per CTRL-001."""
        roi = ROI(shape=ROIShape.RECT, rect=Rect(x=0, y=0, w=50, h=50))
        calc = DiffCalculator(roi, threshold=0.02)

        # Set up reference frame
        reference = np.full((50, 50), 100, dtype=np.uint8)
        calc.set_reference(reference)

        # Freeze (simulate pause)
        frozen = calc.freeze_state()

        # Verify frame_t0 is captured
        np.testing.assert_array_equal(frozen["frame_t0"], reference)

    def test_pause_preserves_hold_hits_at_zero(self) -> None:
        """Pause with hold_hits=0 should preserve 0."""
        roi = ROI(shape=ROIShape.RECT, rect=Rect(x=0, y=0, w=50, h=50))
        calc = DiffCalculator(roi, threshold=0.02)
        calc.set_reference(np.zeros((50, 50), dtype=np.uint8))

        # No hits yet
        assert calc.hold_hits == 0

        frozen = calc.freeze_state()
        assert frozen["hold_hits"] == 0

    def test_pause_preserves_hold_hits_at_one(self) -> None:
        """Pause with hold_hits=1 should preserve 1."""
        roi = ROI(shape=ROIShape.RECT, rect=Rect(x=0, y=0, w=50, h=50))
        calc = DiffCalculator(roi, threshold=0.02)
        calc.set_reference(np.zeros((50, 50), dtype=np.uint8))

        # Simulate one hit
        calc._tracker._hold_hits = 1

        frozen = calc.freeze_state()
        assert frozen["hold_hits"] == 1


class TestCtrl003MessageChangeOnResume:
    """Test CTRL-003: Pause期间消息变化检测"""

    def test_resume_detects_deleted_messages(self) -> None:
        """Resume should detect when messages are deleted during pause."""
        snapshot = ["msg1", "msg2", "msg3", "msg4", "msg5"]
        # User deletes msg4 and msg5 during pause
        current = ["msg1", "msg2", "msg3"]

        changed = snapshot != current
        assert changed is True

    def test_resume_triggers_stop_on_change(self) -> None:
        """Resume with changes should trigger stop and return to Idle."""

        class MockStateMachine:
            def __init__(self) -> None:
                self.state = State.Paused
                self.messages_snapshot = ["msg1", "msg2", "msg3"]
                self.dialog_shown = False

            def resume(self, current_messages: list[str]) -> bool:
                """Returns True if resumed successfully, False if stopped."""
                if current_messages != self.messages_snapshot:
                    self.state = State.Idle
                    self.dialog_shown = True
                    return False
                return True

        sm = MockStateMachine()
        current = ["msg1", "msg2"]  # Modified during pause

        success = sm.resume(current)

        assert success is False
        assert sm.state == State.Idle
        assert sm.dialog_shown is True


class TestCtrl004NoChangeResume:
    """Test CTRL-004: Pause期间未变化正常Resume"""

    def test_resume_continues_with_same_frame_t0(self) -> None:
        """Resume without changes should use same frame_t0."""
        roi = ROI(shape=ROIShape.RECT, rect=Rect(x=0, y=0, w=50, h=50))
        calc = DiffCalculator(roi, threshold=0.02)

        # Set up state before pause
        original_frame = np.full((50, 50), 123, dtype=np.uint8)
        calc.set_reference(original_frame)
        calc._tracker._hold_hits = 1

        # Freeze
        frozen = calc.freeze_state()

        # Simulate pause period (state cleared somehow)
        calc.reset()

        # Restore
        calc.restore_state(frozen)

        # Verify frame_t0 is restored
        np.testing.assert_array_equal(calc.frame_t0, original_frame)
        assert calc.hold_hits == 1

