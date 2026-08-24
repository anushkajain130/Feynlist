import sqlite3
import math
from datetime import date, datetime
import asyncio
from pathlib import Path
import sys

# Adjust path to find settings/modules
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.append(str(PROJECT_ROOT))

from data.database import db
from data.repositories.task_repo import task_repo
from analytics.pipeline import pipeline

async def main():
    # Initialize the db connection
    await db.initialize()
    
    print("Fetching Academics_Selfstudy tasks from the database...")
    # Fetch all tasks of class Academics_Selfstudy
    tasks = await db.fetch_all(
        "SELECT id, date, start_time, end_time, ps_var FROM tasks WHERE task_class = 'Academics_Selfstudy'"
    )
    
    updated_dates = set()
    update_count = 0
    
    for row in tasks:
        task_id = row["id"]
        task_date = row["date"]
        start_time = row["start_time"]
        end_time = row["end_time"]
        current_ps_var = row["ps_var"]
        
        try:
            h1, m1 = map(int, start_time.split(":"))
            h2, m2 = map(int, end_time.split(":"))
            diff_mins = (h2 * 60 + m2) - (h1 * 60 + m1)
            if diff_mins < 0:
                diff_mins += 1440
            calculated_ps_var = round(diff_mins / 60.0, 2)
        except Exception as e:
            print(f"Error parsing times for task {task_id}: {e}")
            continue
            
        if current_ps_var != calculated_ps_var:
            print(f"Updating task {task_id} ({start_time}-{end_time}): ps_var {current_ps_var} -> {calculated_ps_var}")
            async with db.connection() as conn:
                await conn.execute(
                    "UPDATE tasks SET ps_var = ? WHERE id = ?",
                    (calculated_ps_var, task_id)
                )
                await conn.commit()
            updated_dates.add(task_date)
            update_count += 1

    print(f"Updated {update_count} task(s).")
    
    if updated_dates:
        print(f"Recalculating daily analytics for {len(updated_dates)} unique date(s)...")
        for date_str in sorted(updated_dates):
            d = date.fromisoformat(date_str)
            print(f"Running analytics pipeline for {d}...")
            try:
                await pipeline.run(d)
            except Exception as e:
                print(f"Failed to recalculate for {d}: {e}")
                
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
