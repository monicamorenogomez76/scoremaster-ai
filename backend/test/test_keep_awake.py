"""Render's free plan puts the service to sleep after 15 minutes without use, and the first visit then waited about a
minute (2026-11-01). A scheduled workflow of this public repository, which spends no Actions minutes, asks /health every
ten minutes; the free plan's 750 hours a month cover one service always on."""
import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "despertar.yml"


def test_the_service_is_asked_every_ten_minutes_and_by_hand():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r"schedule:\s*\n\s*- cron: \"\*/10 \* \* \* \*\"", text)
    assert "workflow_dispatch:" in text


def test_it_only_reads_the_health_of_the_public_address():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "https://scoremaster-iz4j.onrender.com/health" in text
    assert "secrets." not in text, "no secret is needed to wake the service"
    assert re.search(r"permissions:\s*\{\}", text), "the job needs no access to the repository"
    assert "--max-time" in text and "--retry" in text, "a sleeping service is waited for, never forever"
    assert "timeout-minutes:" in text
