import asyncio, sys
sys.path.insert(0, '.')
from data.database import db
from data.repositories.task_repo import task_repo
from data.repositories.analytics_repo import analytics_repo
from datetime import date

async def check():
    await db.initialize()
    tasks = await task_repo.get_tasks_for_date(date(2024, 12, 26))
    print(f"Tasks on 2024-12-26: {len(tasks)}")
    for t in tasks[:3]:
        print(f"  - {t.start_time} {t.task[:40]} ({t.task_class.value})")

    metrics = await analytics_repo.get_latest(5)
    print(f"Latest analytics rows: {len(metrics)}")
    for m in metrics:
        print(f"  - {m.date}: disc={m.discipline:.1f}% aura={m.aura:.2f} streak={m.retention_streak}")

    row = await db.fetch_one("SELECT COUNT(*) as c FROM tasks")
    print(f"Total tasks in DB: {row['c']}")

asyncio.run(check())
