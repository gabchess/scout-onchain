"""Offline contract for the zero-key tour skill (ADR 0004 D-5, Q-1, Q-6)."""

import json
import re
from pathlib import Path

from scout_portfolio_manager.host import TOOL_NAMES, default_host

ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / "skills" / "try" / "SKILL.md").read_text()
PLANNED = ["get_portfolio_risk", "get_pnl", "preview_dca", "search_defi_knowledge"]


def test_skill_names_exactly_the_planned_tools_in_tour_order():
    named = {name for name in TOOL_NAMES if re.search(rf"`{name}`", SKILL)}
    assert named == set(PLANNED)
    tour = SKILL.split("## Tour", 1)[1]
    positions = [tour.index(f"`{name}`") for name in PLANNED]
    assert positions == sorted(positions)


def test_skill_carries_source_line_proposal_fields_and_key_rules():
    assert "Source: bundled synthetic fixture (not your wallet)" in SKILL
    assert "`approval_state=required`" in SKILL
    assert "`execution_available=false`" in SKILL
    assert "Proposal only. Scout cannot sign or send." in SKILL
    assert "Do not paste keys into this chat." in SKILL
    assert "rotate" in SKILL
    assert SKILL.split("# Try Scout", 1)[1].strip().startswith("If the Scout tools")


def test_tour_requests_work_on_the_packaged_fixture():
    host = default_host()
    calls = re.findall(r"Call `(\w+)` with `(\{.*?\})`", SKILL)
    fixed = [(name, json.loads(args)) for name, args in calls if "<" not in args]
    assert [name for name, _ in fixed] == PLANNED[:3]
    results = {name: host.call_tool(name, args) for name, args in fixed}
    assert results["get_portfolio_risk"]["source"]["kind"] == "fixture"
    assert results["get_pnl"]["status"] == "ok"
    preview = results["preview_dca"]
    assert preview["status"] == "preview_ready"
    assert preview["approval_state"] == "required"
    assert preview["execution_available"] is False


def test_trigger_evals_cover_both_outcomes():
    cases = json.loads((ROOT / "skills" / "try" / "trigger-evals.json").read_text())
    assert {case["should_trigger"] for case in cases} == {True, False}
