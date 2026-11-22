"""
Post-deploy check
=================
Runs the evaluator journey against the deployed URLs and prints PASS/FAIL per
step. Uses a fresh demo session, so it never touches anyone else's data. It
sends ONE chat message, which uses one live reply if quota allows (otherwise
you get a labelled sample, which is also a pass).

    python -m scripts.check_deploy --api https://feynlist-api.onrender.com --web https://feynlist.vercel.app

Exit code 0 = every step passed, 1 = something failed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid

import httpx
import websockets


async def main(api: str, web: str | None) -> int:
    api = api.rstrip("/")
    sid = uuid.uuid4().hex
    h = {"X-Feynlist-Session": sid, "X-Feynlist-TZ": "UTC"}
    results: list[tuple[str, bool, str]] = []

    def record(name, ok, detail=""):
        results.append((name, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)

    async with httpx.AsyncClient(timeout=60) as c:
        # 1. Health (free hosts sleep: wait up to ~2 minutes)
        t0, ok, detail = time.time(), False, ""
        while time.time() - t0 < 120:
            try:
                r = await c.get(f"{api}/health")
                ok, detail = r.status_code == 200, f"HTTP {r.status_code} {r.text[:80]}"
                if ok:
                    break
            except Exception as e:
                detail = f"not answering yet ({type(e).__name__})"
            await asyncio.sleep(5)
        record("health", ok, f"{detail} after {time.time() - t0:.0f}s")
        if not ok:
            return 1

        r = await c.get(f"{api}/api/demo/status", headers=h)
        record("demo mode on", r.status_code == 200 and r.json().get("demo_mode") is True, r.text[:120])

        r = await c.get(f"{api}/api/tasks/today", headers=h)
        tasks = r.json().get("tasks", []) if r.status_code == 200 else []
        record("sample plan seeded", len(tasks) > 0, f"{len(tasks)} tasks today")

        r = await c.get(f"{api}/api/analytics/history?days=14", headers=h)
        record("sample history", r.status_code == 200 and len(r.json()) >= 10, f"{len(r.json()) if r.status_code == 200 else r.status_code} days")

        open_task = next((t for t in tasks if not t["start_and_sit"]), None)
        if open_task:
            before = (await c.get(f"{api}/api/analytics/today", headers=h)).json().get("total_points")
            r = await c.post(f"{api}/api/tasks/toggle-subtask", headers=h, json={
                "task_id": open_task["id"], "subtask_name": "Start_and_Sit_for_5_mins", "value": True})
            after = (await c.get(f"{api}/api/analytics/today", headers=h)).json().get("total_points")
            record("task toggle updates analytics", r.status_code == 200 and after != before, f"points {before} -> {after}")

        r = await c.post(f"{api}/api/agents/message", headers=h, json={"message": "How is my day going?", "agent_id": "freya"})
        if r.status_code == 200:
            m = r.json()["messages"][0]
            kind = "SAMPLE (" + (m.get("sample_reason") or "") + ")" if m.get("is_sample") else "LIVE"
            labelled = (not m.get("is_sample")) or m.get("sample_label") == "Sample reply (pre-written, not live)"
            record("coach reply", labelled, f"{kind}: {m['content'][:100]}")
        else:
            record("coach reply", False, f"HTTP {r.status_code} {r.text[:100]}")

        r = await c.get(f"{api}/api/agents/budget", headers=h)
        record("budget endpoint", r.status_code == 200, r.text[:160])

        r = await c.get(f"{api}/api/tasks/today")
        record("requests without a session refused", r.status_code == 400, f"HTTP {r.status_code}")

        if web:
            origin = web.rstrip("/")
            r = await c.options(f"{api}/api/tasks/today", headers={
                "Origin": origin, "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-feynlist-session,x-feynlist-tz"})
            allowed = r.headers.get("access-control-allow-origin")
            record("CORS allows the frontend", allowed == origin,
                   f"allow-origin={allowed}" + (" (ALLOWED_ORIGINS is still '*': set it to the frontend URL)" if allowed == "*" else ""))
            r = await c.options(f"{api}/api/tasks/today", headers={
                "Origin": "https://not-your-site.example", "Access-Control-Request-Method": "GET"})
            other = r.headers.get("access-control-allow-origin")
            record("CORS blocks other sites", other not in ("https://not-your-site.example", "*"),
                   f"allow-origin={other}")
            r = await c.get(origin, follow_redirects=True)
            record("frontend loads", r.status_code == 200, f"HTTP {r.status_code}")

    ws_url = api.replace("https://", "wss://").replace("http://", "ws://") + f"/api/agents/ws?session={sid}&tz=UTC"
    try:
        async with websockets.connect(ws_url, open_timeout=30) as ws:
            first = json.loads(await asyncio.wait_for(ws.recv(), 30))
            record("websocket connects", first.get("type") == "status", f"{ws_url.split('?')[0]} -> {first}")
    except Exception as e:
        record("websocket connects", False, f"{type(e).__name__}: {e}")

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed" + (f": {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--api", required=True, help="backend URL, e.g. https://feynlist-api.onrender.com")
    p.add_argument("--web", help="frontend URL, e.g. https://feynlist.vercel.app")
    a = p.parse_args()
    sys.exit(asyncio.run(main(a.api, a.web)))
