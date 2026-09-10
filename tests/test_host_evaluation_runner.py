import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.run_host_evaluation import load_prompts, preflight_mcp


def test_reference_answer_and_rubric_are_not_forwarded(tmp_path):
    suite = tmp_path / "suite.json"
    suite.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "debt",
                        "prompt": "Evaluate this position.",
                        "reference_answer": "SECRET ANSWER",
                        "criteria": [{"description": "SECRET RUBRIC"}],
                    }
                ]
            }
        )
    )
    assert load_prompts(suite) == [{"id": "debt", "prompt": "Evaluate this position."}]


@pytest.mark.parametrize(
    "cases",
    [
        [],
        ["invalid"],
        [{"id": "../escape", "prompt": "x"}],
        [{"id": "ok", "prompt": ""}],
        [{"id": "same", "prompt": "a"}, {"id": "same", "prompt": "b"}],
    ],
)
def test_invalid_suite_rejected_before_starting_host(tmp_path, cases):
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps({"cases": cases}))
    with pytest.raises(ValueError):
        load_prompts(suite)


def test_frozen_array_suite_supported_without_rewriting_it(tmp_path):
    suite = tmp_path / "suite.json"
    suite.write_text(
        json.dumps([{"id": "CASE-01", "prompt": "Assess this.", "reference_answer": "hidden"}])
    )
    assert load_prompts(suite) == [{"id": "CASE-01", "prompt": "Assess this."}]


def test_failed_mcp_startup_cannot_create_pass_evidence(tmp_path):
    launcher = tmp_path / "broken.py"
    launcher.write_text("raise RuntimeError('intentional preflight failure')\n")
    with pytest.raises(subprocess.CalledProcessError):
        preflight_mcp(Path(sys.executable), launcher, tmp_path)
    assert not (tmp_path / "mcp-preflight.json").exists()
