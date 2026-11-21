"""The smoke script must report failures and skips honestly (baseline B-20)."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(*args, env_extra=None):
    env = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY")}
    env["GEMINI_API_KEY"] = ""   # never make a live call from tests
    env["GOOGLE_API_KEY"] = ""
    return subprocess.run([sys.executable, "-m", "scripts.smoke_test", *args],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)


def test_skip_is_reported_not_called_all_passed():
    p = run()
    assert p.returncode == 0
    assert "[SKIP] live_llm" in p.stdout
    assert "PASSED WITH SKIPS" in p.stdout
    assert "every check ran and passed" not in p.stdout


def test_require_llm_skip_is_not_ok():
    assert run("--require-llm").returncode == 2


async def test_failure_gives_exit_1(monkeypatch, capsys):
    saved = os.environ.get("DATABASE_PATH")
    import scripts.smoke_test as smoke
    if saved is None:
        monkeypatch.delenv("DATABASE_PATH", raising=False)
    else:
        monkeypatch.setenv("DATABASE_PATH", saved)

    async def ok():
        return smoke.Result("a", smoke.PASS, "fine")

    async def bad():
        return smoke.Result("b", smoke.FAIL, "broken")

    async def boom():
        raise RuntimeError("crash")

    monkeypatch.setattr(smoke, "CHECKS", [ok, bad, boom])
    code = await smoke.run_smoke_test()
    out = capsys.readouterr().out
    assert code == 1
    assert "[FAIL] b: broken" in out and "[FAIL] boom: exception: crash" in out
    assert "RESULT: FAILED" in out
