"""
Unit Tests: Analytics Metrics
==============================
Tests all metric formulas with known inputs/outputs.
These are pure function tests — zero database dependency.
"""

import math
from datetime import date, time, datetime
from unittest.mock import patch

import pytest

from analytics.metrics import (
    AlertnessMetric,
    DisciplineMetric,
    PSHoursMetric,
    AuraMetric,
    ConsistencyStreakMetric,
    PointsMetric,
)
from core.models import Task, TaskClass, DailyMetrics


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def make_task(
    task="Test Task",
    start="08:00",
    end="09:00",
    points=100,
    task_class=TaskClass.UNSPECIFIED,
    slider_val=0,
    start_and_sit=False,
    complete_task=False,
    be_attentive=False,
    ps_var=0.0,
    sub_class=None,
) -> Task:
    return Task(
        date=date(2025, 6, 1),
        task=task,
        start_time=start,
        end_time=end,
        points=points,
        task_class=task_class,
        slider_val=slider_val,
        start_and_sit=start_and_sit,
        complete_task=complete_task,
        be_attentive=be_attentive,
        ps_var=ps_var,
        sub_class=sub_class,
    )


def make_metrics(
    alertness=50.0,
    discipline=80.0,
    ps_hrs=2.0,
    aura=1.5,
    retention_streak=5,
) -> DailyMetrics:
    return DailyMetrics(
        date=date(2025, 5, 31),
        alertness=alertness,
        discipline=discipline,
        ps_hrs=ps_hrs,
        aura=aura,
        retention_streak=retention_streak,
    )


# =============================================================================
# ALERTNESS TESTS
# =============================================================================

class TestAlertnessMetric:
    """Alertness = points-weighted attention rating over tasks the user rated
    (Be Attentive checked). Unrated, unfinished and future tasks don't lower it."""

    def test_zero_when_nothing_rated(self):
        task = make_task(points=100, slider_val=100)
        assert AlertnessMetric.compute_raw([task]) == 0.0
        assert AlertnessMetric.compute([task], yesterday=make_metrics(alertness=80.0)) == 0.0

    def test_full_score_perfect_slider(self):
        task = make_task(points=100, slider_val=100, be_attentive=True)
        assert AlertnessMetric.compute_raw([task]) == pytest.approx(100.0)

    def test_partial_score(self):
        task = make_task(points=100, slider_val=50, be_attentive=True)
        assert AlertnessMetric.compute_raw([task]) == pytest.approx(50.0)

    def test_points_weighted(self):
        big = make_task(points=100, slider_val=80, be_attentive=True)
        small = make_task(points=20, slider_val=20, be_attentive=True)
        # (0.8*100 + 0.2*20) / 120 = 84/120 = 70%
        assert AlertnessMetric.compute_raw([big, small]) == pytest.approx(70.0)

    def test_early_day_not_deflated_by_future_tasks(self):
        """Baseline bug B-18: at 09:30, one rated 08–09 task + two future tasks gave 33%."""
        done = make_task(start="08:00", end="09:00", slider_val=100, be_attentive=True)
        noon = make_task(start="12:00", end="13:00")
        evening = make_task(start="18:00", end="19:00")
        assert AlertnessMetric.compute_raw([done, noon, evening], now=time(9, 30)) == pytest.approx(100.0)

    def test_unrated_tasks_ignored(self):
        rated = make_task(points=50, slider_val=60, be_attentive=True)
        unrated = make_task(points=50, slider_val=100)
        assert AlertnessMetric.compute_raw([rated, unrated]) == pytest.approx(60.0)

    def test_ewm_with_yesterday(self):
        """EWM weighting: 0.85 * today + 0.15 * yesterday."""
        task = make_task(points=100, slider_val=50, be_attentive=True)
        yesterday = make_metrics(alertness=80.0)
        result = AlertnessMetric.compute([task], yesterday=yesterday, now=time(10, 0))
        # raw = 50.0, ewm = 0.85*50 + 0.15*80 = 42.5 + 12 = 54.5
        assert result == pytest.approx(54.5)


class TestMidnightCrossingTasks:
    """Blocks like Sleep 22:00–06:00 end on the next calendar day (baseline bug B-17)."""

    def sleep(self, **kw):
        return make_task(task="Sleep", start="22:00", end="06:00", task_class=TaskClass.SLEEP, **kw)

    def test_crossing_flag(self):
        assert self.sleep().ends_next_day
        assert not make_task(start="08:00", end="09:00").ends_next_day

    def test_not_past_during_the_day(self):
        s = self.sleep()
        assert not s.is_past_at(time(10, 0))
        assert not s.is_past_at(time(23, 59))
        assert not s.has_ended_by(time(10, 0))

    def test_active_late_evening_not_morning_of_same_date(self):
        s = self.sleep()
        assert s.is_active_at(time(23, 0))
        assert not s.is_active_at(time(12, 0))

    def test_counts_once_day_is_over(self):
        assert self.sleep().has_ended_by(time(10, 0), day_over=True)

    def test_discipline_ignores_unstarted_sleep_block(self):
        study = make_task(start="08:00", end="09:00", start_and_sit=True)
        assert DisciplineMetric.compute_raw([study, self.sleep()], now=time(10, 0)) == pytest.approx(100.0)

    def test_discipline_on_finished_day_counts_all_blocks(self):
        study = make_task(start="08:00", end="09:00", start_and_sit=True)
        sleep = self.sleep()
        # 50 of (50 + 50) start-and-sit points
        assert DisciplineMetric.compute_raw([study, sleep], now=time(10, 0), day_over=True) == pytest.approx(50.0)

    def test_ps_hours_duration_wraps(self):
        late = make_task(start="23:00", end="01:00", task_class=TaskClass.ACADEMICS_SELFSTUDY)
        assert late.ps_var == pytest.approx(2.0)


# =============================================================================
# DISCIPLINE TESTS
# =============================================================================

class TestDisciplineMetric:

    def test_zero_no_past_tasks(self):
        tasks = [make_task(start="23:00", end="23:59")]
        result = DisciplineMetric.compute_raw(tasks, now=time(8, 0))
        assert result == 0.0

    def test_full_discipline_all_started(self):
        tasks = [
            make_task(start="08:00", end="09:00", points=100, start_and_sit=True),
            make_task(start="09:00", end="10:00", points=100, start_and_sit=True),
        ]
        result = DisciplineMetric.compute_raw(tasks, now=time(12, 0))
        assert result == pytest.approx(100.0)

    def test_half_discipline(self):
        tasks = [
            make_task(start="08:00", end="09:00", points=100, start_and_sit=True),
            make_task(start="09:00", end="10:00", points=100, start_and_sit=False),
        ]
        result = DisciplineMetric.compute_raw(tasks, now=time(12, 0))
        # started=50pts, total=100pts → 50%
        assert result == pytest.approx(50.0)

    def test_ewm_with_yesterday(self):
        tasks = [make_task(start="08:00", end="09:00", points=100, start_and_sit=True)]
        yesterday = make_metrics(discipline=60.0)
        result = DisciplineMetric.compute([tasks[0]], yesterday=yesterday, now=time(12, 0))
        # raw=100, ewm = 0.95*100 + 0.05*60 = 95 + 3 = 98
        assert result == pytest.approx(98.0)


# =============================================================================
# PS HOURS TESTS
# =============================================================================

class TestPSHoursMetric:

    def test_only_selfstudy_with_complete(self):
        tasks = [
            make_task(task_class=TaskClass.ACADEMICS_SELFSTUDY, ps_var=2.0, complete_task=True),
            make_task(task_class=TaskClass.ACADEMICS_SELFSTUDY, ps_var=1.5, complete_task=True),
            make_task(task_class=TaskClass.SOCIAL, ps_var=3.0, complete_task=True),  # should not count
        ]
        result = PSHoursMetric.compute(tasks)
        assert result == pytest.approx(3.5)

    def test_incomplete_selfstudy_excluded(self):
        tasks = [
            make_task(task_class=TaskClass.ACADEMICS_SELFSTUDY, ps_var=2.0, complete_task=False),
        ]
        result = PSHoursMetric.compute(tasks)
        assert result == 0.0

    def test_zero_with_no_selfstudy(self):
        tasks = [make_task(task_class=TaskClass.SLEEP, ps_var=5.0, complete_task=True)]
        result = PSHoursMetric.compute(tasks)
        assert result == 0.0

    def test_auto_calculate_ps_var_for_academics_selfstudy(self):
        # 07:00 to 09:00 -> should be 2.0 hours
        task = make_task(
            task_class=TaskClass.ACADEMICS_SELFSTUDY,
            start="07:00",
            end="09:00",
            ps_var=0.0,
            complete_task=True
        )
        assert task.ps_var == 2.0
        
        # 09:00 to 09:40 -> should be 0.67 hours
        task2 = make_task(
            task_class=TaskClass.ACADEMICS_SELFSTUDY,
            start="09:00",
            end="09:40",
            ps_var=0.0,
            complete_task=True
        )
        assert task2.ps_var == 0.67


# =============================================================================
# AURA TESTS
# =============================================================================

class TestAuraMetric:

    def test_zero_streak_not_zero_aura(self):
        """V0 bug: streak=0 caused aura=0 via ^0.5. log(1+0)=0 so it's still 0,
        but discipline and ps still contribute properly."""
        # streak=0 → log(1+0) = 0, so aura = 0. That's correct behavior.
        result = AuraMetric.compute(discipline=90.0, ps_hrs=2.0, retention_streak=0)
        assert result == 0.0  # Correct: just earned, streak not yet started

    def test_growing_streak_increases_aura(self):
        """Aura grows as streak grows."""
        aura_1 = AuraMetric.compute(discipline=90.0, ps_hrs=2.0, retention_streak=1)
        aura_7 = AuraMetric.compute(discipline=90.0, ps_hrs=2.0, retention_streak=7)
        aura_30 = AuraMetric.compute(discipline=90.0, ps_hrs=2.0, retention_streak=30)
        assert aura_1 < aura_7 < aura_30

    def test_zero_discipline_zeroes_aura(self):
        result = AuraMetric.compute(discipline=0.0, ps_hrs=3.0, retention_streak=10)
        assert result == 0.0

    def test_no_study_planned_is_neutral(self):
        """Non-students (no Study blocks) aren't penalised by the study factor."""
        with_study_missed = AuraMetric.compute(discipline=100.0, ps_hrs=0.0, retention_streak=3)
        no_study = AuraMetric.compute(discipline=100.0, ps_hrs=0.0, retention_streak=3, study_planned=False)
        assert no_study == pytest.approx(math.log(4), rel=1e-3)
        assert with_study_missed == pytest.approx(math.sqrt(0.2) * math.log(4), rel=1e-3)

    def test_formula_correctness(self):
        """Manual formula verification."""
        disc, ps, streak = 90.0, 2.0, 7
        # aura = sqrt(0.9) * sqrt(2.0/2.0) * log(8)
        expected = math.sqrt(0.9) * math.sqrt(1.0) * math.log(8)
        result = AuraMetric.compute(discipline=disc, ps_hrs=ps, retention_streak=streak, ps_target=2.0)
        assert result == pytest.approx(expected, rel=1e-3)


# =============================================================================
# CONSISTENCY STREAK TESTS (neutral check-in)
# =============================================================================

class TestConsistencyStreakMetric:

    def compute(self, **kw):
        args = dict(yesterday_streak=5, commitment_kept=None, tasks_completed=0,
                    tasks_total=4, day_in_progress=False, min_completion=0.5)
        args.update(kw)
        return ConsistencyStreakMetric.compute(**args)

    def test_kept_commitment_increments(self):
        assert self.compute(commitment_kept=True) == 6

    def test_not_today_resets(self):
        assert self.compute(commitment_kept=False, tasks_completed=4) == 0

    def test_completion_threshold_counts_without_checkin(self):
        assert self.compute(tasks_completed=2) == 6   # 50% meets threshold

    def test_below_threshold_finished_day_resets(self):
        assert self.compute(tasks_completed=1) == 0

    def test_below_threshold_in_progress_day_holds(self):
        """Today isn't over yet: the streak is not broken, just not extended."""
        assert self.compute(tasks_completed=1, day_in_progress=True) == 5

    def test_checkin_with_no_tasks_counts(self):
        assert self.compute(tasks_total=0, commitment_kept=True) == 6

    def test_no_tasks_no_checkin_does_not_count(self):
        assert ConsistencyStreakMetric.day_counts(None, 0, 0, 0.5) is False

    def test_new_user_first_day(self):
        assert self.compute(yesterday_streak=0, commitment_kept=True) == 1


# =============================================================================
# POINTS TESTS
# =============================================================================

class TestPointsMetric:

    def test_all_subtasks_complete(self):
        task = make_task(
            points=100,
            start_and_sit=True,
            complete_task=True,
            be_attentive=True,
            slider_val=100,  # 100% of 100
        )
        result = PointsMetric.compute_for_task(task)
        # 50 + 30 + 20 = 100
        assert result == 100

    def test_only_start_and_sit(self):
        task = make_task(points=100, start_and_sit=True)
        result = PointsMetric.compute_for_task(task)
        assert result == 50

    def test_no_subtasks_zero_points(self):
        task = make_task(points=100)
        result = PointsMetric.compute_for_task(task)
        assert result == 0

    def test_total_points_multiple_tasks(self):
        tasks = [
            make_task(points=100, start_and_sit=True, complete_task=True, be_attentive=True, slider_val=100),
            make_task(points=50, start_and_sit=True),
        ]
        result = PointsMetric.compute_total(tasks)
        # 100 + 25 = 125
        assert result == 125


# =============================================================================
# BURNOUT HEURISTIC (Signal 4: high discipline, low alertness)
# =============================================================================

class TestBurnoutAlertnessSignal:

    async def run(self, monkeypatch, records):
        from analytics import trends
        async def fake_latest(n=7):
            return records
        monkeypatch.setattr(trends.analytics_repo, "get_latest", fake_latest)
        return await trends.trend_analyzer.detect_burnout_signal()

    async def test_unrated_days_do_not_trigger(self, monkeypatch):
        """Days with alertness 0.0 (nothing rated) are not 'low focus'."""
        recs = [make_metrics(discipline=90.0, alertness=0.0) for _ in range(6)]
        sig = await self.run(monkeypatch, recs)
        assert not any("low focus" in f for f in sig.contributing_factors)

    async def test_rated_low_focus_days_trigger(self, monkeypatch):
        recs = [make_metrics(discipline=90.0, alertness=20.0) for _ in range(6)]
        sig = await self.run(monkeypatch, recs)
        assert any("low focus" in f for f in sig.contributing_factors)
