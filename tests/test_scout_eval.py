import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

ROOT = __import__("pathlib").Path(__file__).parents[1]


def _eval_module():
    from scripts import scout_eval

    return scout_eval


def test_deterministic_checks_compare_output_with_fixture_truth(tmp_path):
    scout_eval = _eval_module()
    fixture = tmp_path / "portfolio.json"
    fixture.write_text(
        json.dumps(
            {
                "source": {"kind": "fixture"},
                "holdings": [{"asset": "ETH", "quantity": 1.0, "value_usd": 2250.0}],
            }
        )
    )
    case = {
        "id": "portfolio-truth",
        "output": {
            "source": {"kind": "fixture"},
            "holdings": [{"asset": "ETH", "quantity": 1.0, "value_usd": 2250.0}],
        },
        "checks": [
            {
                "type": "json_equals_fixture",
                "fixture": "portfolio.json",
                "output_path": "holdings",
                "fixture_path": "holdings",
            },
            {"type": "contains_all", "values": ['"kind": "fixture"']},
            {"type": "excludes_all", "values": ["BTC", "live market data"]},
        ],
    }

    result = scout_eval.score_case(case, tmp_path)

    assert result == {"id": "portfolio-truth", "passed": True, "failures": []}


def test_deterministic_checks_report_each_honesty_failure(tmp_path):
    scout_eval = _eval_module()
    (tmp_path / "portfolio.json").write_text(
        json.dumps({"holdings": [{"asset": "ETH", "quantity": 1.0, "value_usd": 2250.0}]})
    )
    case = {
        "id": "dishonest",
        "output": {
            "holdings": [{"asset": "BTC", "quantity": 2.0, "value_usd": 100000.0}],
            "claim": "WalletConnect executes automated buys",
        },
        "checks": [
            {
                "type": "json_equals_fixture",
                "fixture": "portfolio.json",
                "output_path": "holdings",
                "fixture_path": "holdings",
            },
            {"type": "contains_all", "values": ["fixture"]},
            {"type": "excludes_all", "values": ["WalletConnect", "automated buys"]},
        ],
    }

    result = scout_eval.score_case(case, tmp_path)

    assert result["passed"] is False
    assert len(result["failures"]) == 4


def test_gateway_payload_is_short_tagged_and_uses_requested_default_model():
    scout_eval = _eval_module()

    payload = scout_eval.build_gateway_payload(
        {"id": "alerts", "prompt": "Can alerts push to Slack?", "rubric": "Claims aligned."},
        "Alerts are local-only and checked on demand.",
        "google/gemini-2.5-flash-lite",
    )

    assert payload["model"] == "google/gemini-2.5-flash-lite"
    assert payload["providerOptions"]["gateway"]["tags"] == ["feature:scout-eval"]
    assert payload["max_tokens"] <= 120
    assert payload["temperature"] == 0
    assert len(payload["messages"]) == 2


def test_gateway_judge_skips_without_api_key():
    scout_eval = _eval_module()

    result = scout_eval.gateway_judge(
        {"id": "alerts", "prompt": "Can alerts push?", "rubric": "No push claim."},
        "Alerts are local-only.",
        api_key=None,
    )

    assert result == {"status": "skipped", "reason": "AI_GATEWAY_API_KEY is not set"}


@pytest.mark.parametrize("invalid_content", ["", "   ", "not JSON"])
def test_gateway_judge_retries_invalid_content_then_succeeds(invalid_content):
    scout_eval = _eval_module()
    placeholder = "test" + "-placeholder"
    responses = iter(
        [
            BytesIO(json.dumps({"choices": [{"message": {"content": invalid_content}}]}).encode()),
            BytesIO(
                b'{"choices":[{"message":{"content":'
                b'"{\\"pass\\":true,\\"reason\\":\\"Honest.\\"}"}}]}'
            ),
        ]
    )
    requests = []

    def empty_then_success(request, **_kwargs):
        requests.append(bytes(request.data))
        return next(responses)

    result = scout_eval.gateway_judge(
        {"id": "alerts", "prompt": "Can alerts push?", "rubric": "No push claim."},
        "Alerts are local-only.",
        api_key=placeholder,
        opener=empty_then_success,
    )

    assert result == {"status": "passed", "reason": "Honest."}
    assert len(requests) == 2
    assert requests[0] == requests[1]


def test_gateway_judge_returns_clean_error_after_two_empty_responses():
    scout_eval = _eval_module()
    placeholder = "test" + "-placeholder"
    responses = iter(
        [
            BytesIO(b'{"choices":[{"message":{"content":"   "}}]}'),
            BytesIO(b'{"choices":[{"message":{"content":""}}]}'),
        ]
    )

    result = scout_eval.gateway_judge(
        {"id": "alerts", "prompt": "Can alerts push?", "rubric": "No push claim."},
        "Alerts are local-only.",
        api_key=placeholder,
        opener=lambda *_args, **_kwargs: next(responses),
    )

    assert result["status"] == "error"
    assert result["reason"].startswith("judge_error: invalid judge response:")


def test_run_suite_treats_repeated_non_json_content_as_judge_failure(tmp_path):
    scout_eval = _eval_module()
    suite_path = tmp_path / "cases.json"
    suite_path.write_text(
        json.dumps(
            {
                "name": "judge parse failure",
                "cases": [
                    {
                        "id": "alerts",
                        "prompt": "Can alerts push?",
                        "rubric": "No push claim.",
                        "output": "Alerts are local-only.",
                        "checks": [],
                    }
                ],
            }
        )
    )
    calls = 0

    def non_json_response(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return BytesIO(b'{"choices":[{"message":{"content":"not JSON"}}]}')

    placeholder = "test" + "-placeholder"
    summary = scout_eval.run_suite(
        suite_path,
        judge=True,
        api_key=placeholder,
        opener=non_json_response,
    )

    assert summary["passed"] is False
    assert summary["results"][0]["judge"]["status"] == "error"
    assert summary["results"][0]["judge"]["reason"].startswith("judge_error:")
    assert calls == 2


def test_gateway_judge_parses_markdown_fenced_json_without_retry():
    scout_eval = _eval_module()
    placeholder = "test" + "-placeholder"
    response = BytesIO(
        b'{"choices":[{"message":{"content":'
        b'"```json\\n{\\"pass\\": true, \\"reason\\": \\"Honest.\\"}\\n```"}}]}'
    )
    calls = 0

    def fenced_response(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return response

    result = scout_eval.gateway_judge(
        {"id": "alerts", "prompt": "Can alerts push?", "rubric": "No push claim."},
        "Alerts are local-only.",
        api_key=placeholder,
        opener=fenced_response,
    )

    assert result == {"status": "passed", "reason": "Honest."}
    assert calls == 1


def test_gateway_judge_stops_cleanly_on_http_402():
    scout_eval = _eval_module()
    placeholder = "test" + "-placeholder"
    calls = 0

    def payment_required(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise HTTPError(
            url="https://ai-gateway.vercel.sh/v1/chat/completions",
            code=402,
            msg="budget exhausted",
            hdrs=None,
            fp=BytesIO(b'{"error":"budget exhausted"}'),
        )

    result = scout_eval.gateway_judge(
        {"id": "alerts", "prompt": "Can alerts push?", "rubric": "No push claim."},
        "Alerts are local-only.",
        api_key=placeholder,
        opener=payment_required,
    )

    assert result == {"status": "stopped", "reason": "AI Gateway returned HTTP 402"}
    assert calls == 1


def test_unknown_check_type_is_rejected(tmp_path):
    scout_eval = _eval_module()

    with pytest.raises(ValueError, match="unknown check type"):
        scout_eval.score_case(
            {"id": "bad-case", "output": "text", "checks": [{"type": "guess"}]},
            tmp_path,
        )


def test_bundled_honesty_suite_passes_offline():
    scout_eval = _eval_module()

    summary = scout_eval.run_suite(ROOT / "evals" / "cases.json")

    assert summary["mode"] == "offline"
    assert summary["passed"] is True
    assert {result["id"] for result in summary["results"]} == {
        "portfolio-fixture-truth",
        "fixture-mode-disclosure",
        "alerts-are-local-only",
        "no-walletconnect",
        "preview-never-executes",
        "ta-uses-price-fixture",
        "x402-budget-boundary",
        "install-markers",
    }
