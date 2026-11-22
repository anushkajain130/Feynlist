"""Baseline probe of metric behaviour (no code changes). Run: python evals/evidence/baseline_metric_probe.py"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from datetime import date, time
from core.models import Task, TaskClass
from analytics.metrics import AlertnessMetric, DisciplineMetric, AuraMetric

def T(name, s, e, cls=TaskClass.ACADEMICS_SELFSTUDY, **kw):
    return Task(id=name, date=date.today(), task=name, start_time=s, end_time=e, points=100, task_class=cls, **kw)
day = [T("morning", "08:00", "09:00", start_and_sit=True, complete_task=True, completed=True),
       T("noon", "12:00", "13:00"), T("evening", "18:00", "19:00")]
print("A1 Alertness at 09:30, only the 08-09 task is past & completed, slider untouched (default slider_val=%s):" % day[0].slider_val,
      AlertnessMetric.compute_raw(day, time(9, 30)))
print("A2 Same day at 19:30 (all tasks past, only first completed):", AlertnessMetric.compute_raw(day, time(19, 30)))
sleep = T("sleep", "22:00", "06:00", cls=TaskClass.SLEEP)
study = T("study", "08:00", "09:00", start_and_sit=True)
print("D1 Discipline at 10:00 with a 22:00-06:00 sleep block not yet begun + one started past task:",
      DisciplineMetric.compute_raw([study, sleep], time(10, 0)))
print("D2 sleep.is_past_at(10:00) =", sleep.is_past_at(time(10, 0)), "| sleep.is_current_at(23:00) =",
      sleep.is_current_at(time(23, 0)) if hasattr(sleep, "is_current_at") else "n/a")
print("AU1 Aura streak=0:", AuraMetric.compute(90, 2, 0), "| streak=1:", AuraMetric.compute(90, 2, 1), "| disc=0:", AuraMetric.compute(0, 2, 5))
