"""After-fix probe of the same scenarios as baseline_metric_probe.py.
Difference: the finished 08-09 task is built the way the app saves it (all three
marks set, so Be Attentive is checked and the slider value counts). The baseline
probe set completed=True without be_attentive, which the app never produces.
Run: python evals/evidence/after_metric_probe.py"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from datetime import date, time
from core.models import Task, TaskClass
from analytics.metrics import AlertnessMetric, DisciplineMetric, AuraMetric
def T(name, s, e, cls=TaskClass.ACADEMICS_SELFSTUDY, **kw):
    return Task(id=name, date=date.today(), task=name, start_time=s, end_time=e, points=100, task_class=cls, **kw)
done = dict(start_and_sit=True, complete_task=True, be_attentive=True, completed=True, slider_val=100)
day = [T("morning", "08:00", "09:00", **done), T("noon", "12:00", "13:00"), T("evening", "18:00", "19:00")]
print("A1 Alertness at 09:30, 08-09 task finished with focus 100, two future tasks:", AlertnessMetric.compute_raw(day, time(9, 30)))
print("A2 Same day at 19:30 (noon/evening never done, unrated):", AlertnessMetric.compute_raw(day, time(19, 30)))
print("A3 Unrated day (nothing has Be Attentive):", AlertnessMetric.compute_raw([T("x", "08:00", "09:00")]), "(0.0 = no data; burnout signal skips it)")
sleep = T("sleep", "22:00", "06:00", cls=TaskClass.SLEEP)
study = T("study", "08:00", "09:00", start_and_sit=True)
print("D1 Discipline at 10:00, started 08-09 task + 22:00-06:00 sleep block not yet begun:", DisciplineMetric.compute_raw([study, sleep], time(10, 0)))
print("D2 sleep.is_past_at(10:00) =", sleep.is_past_at(time(10, 0)), "| sleep.is_active_at(23:00) =", sleep.is_active_at(time(23, 0)))
print("AU1 Aura streak=0:", AuraMetric.compute(90, 2, 0), "| streak=1:", AuraMetric.compute(90, 2, 1),
      "| no Study planned, streak=3:", AuraMetric.compute(100, 0, 3, study_planned=False))
