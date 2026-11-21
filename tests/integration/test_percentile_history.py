"""Percentiles are withheld until there are 14 days of history (no 'top 0%' for new users)."""

from datetime import date, timedelta

from core.models import DailyMetrics
from data.repositories.analytics_repo import analytics_repo
from tools.analytics_tools import GetPercentileInput, GetPercentileTool
from tools.base_tool import ToolContext


async def seed_days(n: int):
    for i in range(n):
        await analytics_repo.upsert_metrics(DailyMetrics(
            date=date.today() - timedelta(days=i), discipline=50 + i, aura=1.0,
            tasks_total=5, tasks_completed=3))


async def run_tool():
    return await GetPercentileTool().execute(GetPercentileInput(metric="discipline"), ToolContext(agent_id="zerotwo"))


async def test_new_user_gets_no_percentile(client):
    await seed_days(3)
    out = await run_tool()
    assert out.percentile is None
    assert "Not enough history" in out.interpretation
    r = await client.get(f"/api/analytics/percentile/{date.today().isoformat()}")
    assert r.json()["enough_history"] is False


async def test_percentile_after_two_weeks(client):
    await seed_days(14)
    out = await run_tool()
    assert out.percentile is not None and 0 <= out.percentile <= 100
