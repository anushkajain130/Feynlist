"""
Pre-written sample replies ("sample mode")
=========================================
Used when a live reply isn't allowed or fails (see agents/ai_budget.py). Every
sample is labelled in the UI as "Sample reply (pre-written, not live)".

Written in each coach's style (agents/personas/*.yaml). They only use facts the
session really has (the task named in the event, today's completed/total,
discipline, consistency streak); if a fact is missing, a variant without it is
used, so a sample never claims data the user doesn't have.
"""

from __future__ import annotations

import re

# kind -> persona -> list of templates, most specific first.
# Kinds: chat, task_missed, task_completed, day_end_review, scheduled_checkin,
#        rest (workload signal), day_start, streak_broken, streak_milestone
TEMPLATES: dict[str, dict[str, list[str]]] = {
    "chat": {
        "freya": ["You're at {done} of {total} blocks today. Pick the next one and start it on time, that's all.",
                  "Pick the next block on your plan and start it on time. That's the whole job right now."],
        "anya": ["{done} of {total} blocks done today, which counts. What's the one thing that would make the rest of today feel okay?",
                 "Whatever today looks like so far, one small block is enough to get going again. What's next?"],
        "zerotwo": ["Today: {done}/{total} blocks, discipline {discipline}%. The fastest gain is starting the next block on time.",
                    "Start-on-time is the lever that moves everything else. Look at your next block and start it at its start time."],
        "albedo": ["{done} of {total} already? Look at you. Go grab the next one.",
                   "Next block, let's go. Tiny win, then another one."],
        "mohini": ["{done} of {total} blocks done. Take a slow breath before the next one; steady beats rushed.",
                   "Pause for a breath, then begin the next block gently. Steady beats rushed."],
    },
    "task_missed": {
        "freya": ["'{task}' didn't get started. Move it to your next free slot and keep it short, 30 to 45 minutes.",
                  "A block slipped. Move it to your next free slot and keep it short."],
        "anya": ["'{task}' slipped, and that's okay. What got in the way? A shorter version later still counts.",
                 "A block slipped, and that's okay. A shorter version later still counts."],
        "zerotwo": ["'{task}' was missed. Check what came right before it: that's usually where the slip starts.",
                    "A block was missed. Check what came right before it: that's usually where the slip starts."],
        "albedo": ["'{task}' escaped this time. Rematch later? Make it a short one and win it back.",
                   "One block escaped. Rematch later, short and winnable."],
        "mohini": ["'{task}' passed by. Notice your energy right now: if it's low, take five minutes first, then reschedule it.",
                   "A block passed by. Check your energy, take five minutes if you need it, then reschedule."],
    },
    "task_completed": {
        "freya": ["'{task}' done. Good. Next block, same energy.",
                  "Block done. Good. Next one, same energy."],
        "anya": ["You finished '{task}'. That's real progress, so let yourself feel it for a second.",
                 "You finished a block. That's real progress, so let yourself feel it for a second."],
        "zerotwo": ["'{task}' complete: that's {done} of {total} today. Keep the next start on time.",
                    "Block complete. Keep the next start on time."],
        "albedo": ["'{task}': done and dusted! That's {done} of {total}. Who's next?",
                   "Done and dusted! On to the next one."],
        "mohini": ["'{task}' complete. Take a breath before the next block; you've earned a smooth transition.",
                   "Block complete. Breathe before the next one; you've earned a smooth transition."],
    },
    "day_end_review": {
        "freya": ["Today: {done} of {total} blocks. Keep what worked, and move tomorrow's hardest block to your best hour.",
                  "Day's done. Keep what worked, and put tomorrow's hardest block in your best hour."],
        "anya": ["You did {done} of {total} blocks today. One thing went well; one thing to adjust tomorrow. Now rest.",
                 "Day's done. Name one thing that went well and one to adjust, then rest."],
        "zerotwo": ["End of day: {done}/{total} blocks, discipline {discipline}%. One change for tomorrow: start the first block on time.",
                    "End of day. One change for tomorrow: start the first block on time."],
        "albedo": ["{done} of {total} today. Tomorrow we beat it by one. Deal?",
                   "Day wrapped. Tomorrow we beat it by one. Deal?"],
        "mohini": ["The day is complete: {done} of {total}. Protect your sleep block tonight; tomorrow starts there.",
                   "The day is complete. Protect your sleep block tonight; tomorrow starts there."],
    },
    "scheduled_checkin": {
        "freya": ["Check-in: {done} of {total} blocks so far. What's the next one? Start it on time.",
                  "Check-in: what's your next block? Start it on time."],
        "anya": ["Quick check-in: {done} of {total} so far. How's your energy? Adjust the plan if you need to.",
                 "Quick check-in: how's your energy? Adjust the plan if you need to."],
        "zerotwo": ["Check-in: discipline {discipline}%, {done}/{total} blocks done. Next lever: the very next start time.",
                    "Check-in: your next lever is the very next start time."],
        "albedo": ["Check-in! {done} of {total} so far. Let's add one more before the next break.",
                   "Check-in! Let's add one more block before the next break."],
        "mohini": ["Check-in: {done} of {total}. If focus is fading, a five-minute walk resets more than you'd think.",
                   "Check-in: if focus is fading, a five-minute walk resets more than you'd think."],
    },
    "rest": {
        "freya": ["Your workload signal is up. Honest take: plan a lighter day tomorrow. That's strategy, not slacking.",
                  "Plan a lighter day tomorrow. That's strategy, not slacking."],
        "anya": ["Your workload signal is up. Please plan one block fewer tomorrow and protect a real break.",
                 "Please plan one block fewer tomorrow and protect a real break."],
        "zerotwo": ["The workload heuristic is flagging. Cut tomorrow's plan by one block and see if focus recovers.",
                    "Cut tomorrow's plan by one block and see if focus recovers."],
        "albedo": ["Rest day energy! A lighter plan tomorrow is still a win, maybe the smartest one.",
                   "A lighter plan tomorrow is still a win, maybe the smartest one."],
        "mohini": ["Your workload signal is up. Stop for today, protect your sleep and start lighter tomorrow.",
                   "Stop for today, protect your sleep and start lighter tomorrow."],
    },
    "day_start": {
        "freya": ["New day: {total} blocks on the plan. Start the first one on time and the rest gets easier.",
                  "New day. Start your first block on time and the rest gets easier."],
    },
    "streak_broken": {
        "anya": ["The streak reset, and that's okay. One kept day starts it again; tomorrow is a fresh start.",
                 "The streak reset, and that's okay. Tomorrow is a fresh start."],
    },
    "streak_milestone": {
        "albedo": ["{streak}-day consistency streak! That's earned. Same plan tomorrow?",
                   "Streak milestone! That's earned. Same plan tomorrow?"],
    },
}

EVENT_TO_KIND = {
    "user_direct_message": "chat",
    "task_missed": "task_missed",
    "task_completed": "task_completed",
    "day_end_review": "day_end_review",
    "scheduled_checkin": "scheduled_checkin",
    "burnout_detected": "rest",
    "day_start": "day_start",
    "streak_broken": "streak_broken",
    "streak_milestone": "streak_milestone",
}

_FIELD = re.compile(r"\{(\w+)\}")


def pick(persona: str, event_type: str, facts: dict) -> str:
    """Choose the most specific template whose fields are all known, and fill it."""
    kind = EVENT_TO_KIND.get(event_type, "chat")
    options = TEMPLATES.get(kind, {}).get(persona) or TEMPLATES["chat"][persona]
    for template in options:
        needed = set(_FIELD.findall(template))
        if all(facts.get(f) not in (None, "") for f in needed):
            return template.format(**{k: facts[k] for k in needed})
    return _FIELD.sub("", options[-1])


async def gather_facts(payload: dict | None) -> dict:
    """Facts a sample may mention: only what this session really has."""
    from core import clock
    from data.repositories.analytics_repo import analytics_repo
    from data.repositories.task_repo import task_repo

    facts: dict = {}
    payload = payload or {}
    if payload.get("task_name"):
        facts["task"] = payload["task_name"]
    try:
        tasks = await task_repo.get_tasks_for_date(clock.today())
        if tasks:
            facts["total"] = len(tasks)
            facts["done"] = sum(1 for t in tasks if t.completed)
        m = await analytics_repo.get_metrics_for_date(clock.today())
        if m and tasks:
            facts["discipline"] = f"{m.discipline:.0f}"
            if m.retention_streak > 0:
                facts["streak"] = m.retention_streak
    except Exception:
        pass
    return facts
