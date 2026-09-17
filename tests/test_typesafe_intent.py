"""Offline tests for optional TypeSafe DCA intent resolution (ADR 0004 D-9).

No test calls the live TypeSafe API. Responses are synthesized from the documented
response shape (docs.typesafe.ai quickstart, 2026-09-16).
"""

from __future__ import annotations

import email
import io
import json
import os
import socket
import time
import urllib.request
import urllib.response
from decimal import Decimal
from pathlib import Path

import pytest
from tests import dca_v061

from scout_portfolio_manager import typesafe_intent as ts
from scout_portfolio_manager.host import ReadOnlyHost

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "portfolio.json"
KEY_VALUE = "ts-test-value-123"
Q = '"'


def _write_env(tmp_path, body: str, mode: int = 0o600) -> Path:
    path = tmp_path / "scout.env"
    path.write_text(body)
    path.chmod(mode)
    return path


def _env(tmp_path, body: str | None = None) -> dict[str, str]:
    path = _write_env(tmp_path, body if body is not None else f"{ts.KEY_NAME}={KEY_VALUE}\n")
    return {ts.ENABLE_ENV: "1", ts.DOTENV_ENV: str(path)}


def choice(chosen, probabilities, confidence=0.95):
    return {
        "type": "choice",
        "choice": chosen,
        "probabilities": probabilities,
        "confidence": confidence,
    }


def complete(value=0.97):
    return {"type": "noul", "noul": value}


class StubTransport:
    def __init__(self, response=None, error: BaseException | None = None):
        self.response = response
        self.error = error
        self.calls: list[tuple[str, bytes]] = []

    def __call__(self, bearer, body, timeout):
        self.calls.append((bearer, body))
        if self.error is not None:
            raise self.error
        return self.response

    def bodies(self) -> list[dict]:
        return [json.loads(body) for _, body in self.calls]


# --- feature off equals 0.6.1 exactly (R-3) ----------------------------------------

CORPUS = [
    "DCA another $300 of ETH",
    "DCA $300 ETH on ethereum weekly from wallet:0xabc123 to wallet:0xdef456",
    "DCA $300 ETH on ethereum and on base weekly from wallet:0xabc123 to wallet:0xdef456",
    "DCA $300 ETH on ethereum weekly from wallet:0xabc123 to wallet:0xdef456 and to wallet:0x9",
    "DCA $300 ETH on ethereum weekly and monthly from wallet:0xabc123 to wallet:0xdef456",
    "Buy $50 of ETH weekly on base from wallet:tour-wallet to rail:tour-rail",
    "put $50 into ether every week on base from wallet:a to rail:b",
    "$200 budget, put $50 weekly into ETH, not SOL, on arbitrum from wallet:a to rail:b",
    "buy ETH, not SOL, $25 daily on op mainnet from wallet:a to wallet:b",
    "my base currency is USD, $10 of bitcoin one-time on arc from wallet:a to rail:b",
    "$50 ETH weekly on base then $50 again from wallet:a to rail:b",
    "",
]


def _core(result) -> dict:
    return {
        "intent": result.intent.model_dump(),
        "status": result.status,
        "missing": result.missing,
        "question": result.question,
    }


@pytest.mark.parametrize("text", CORPUS)
@pytest.mark.parametrize(
    "environ",
    [
        {},
        {ts.ENABLE_ENV: "1"},
        {ts.ENABLE_ENV: "1", ts.DOTENV_ENV: "relative/.env"},
        {ts.ENABLE_ENV: "0", ts.DOTENV_ENV: "/nonexistent/.env"},
        {ts.ENABLE_ENV: "1", ts.DOTENV_ENV: "/nonexistent/.env"},
    ],
)
def test_feature_off_matches_frozen_061_parser(text, environ):
    transport = StubTransport(error=AssertionError("must not be called"))
    result = ts.resolve_dca_request(text, environ, transport=transport)
    assert _core(result) == _core(dca_v061.parse_dca_request(text))
    assert transport.calls == []
    assert set(result.field_sources.values()) <= {"regex"}


def test_host_default_environment_is_off(monkeypatch):
    monkeypatch.delenv(ts.ENABLE_ENV, raising=False)
    monkeypatch.delenv(ts.DOTENV_ENV, raising=False)
    text = CORPUS[1]
    result = ReadOnlyHost(FIXTURE).parse_dca_request(text)
    frozen = dca_v061.parse_dca_request(text)
    assert result["status"] == frozen.status == "ready"
    assert result["intent"] == frozen.intent.model_dump(mode="json")
    assert set(result["field_sources"].values()) == {"regex"}


# --- .env activation and reader (D-9.1, R-5) ---------------------------------------


def test_load_key_reads_only_typesafe_key(tmp_path):
    key = ts.load_key(_env(tmp_path))
    assert key is not None
    assert key.bearer() == f"Bearer {KEY_VALUE}"
    assert KEY_VALUE not in repr(key) and KEY_VALUE not in str(key)
    assert ts.KEY_NAME not in os.environ


def test_other_keys_values_are_never_parsed(tmp_path, monkeypatch):
    seen: list[str] = []
    original = ts._parse_value

    def spy(raw):
        seen.append(raw)
        return original(raw)

    monkeypatch.setattr(ts, "_parse_value", spy)
    body = "\n".join(
        [
            "ZERION_API_KEY=zerion-other-value",
            "ZERION_X402_PRIVATE_KEY=x402-other-value",
            f"{ts.KEY_NAME}={KEY_VALUE}",
            "OTHER=unrelated",
        ]
    )
    assert ts.load_key(_env(tmp_path, body)) is not None
    assert seen == [KEY_VALUE]


@pytest.mark.parametrize(
    "body,expected",
    [
        (f"\ufeff{ts.KEY_NAME}={KEY_VALUE}\n", KEY_VALUE),
        (f"{ts.KEY_NAME}={KEY_VALUE}\r\nOTHER=x\r\n", KEY_VALUE),
        (f"\n# comment\n\n{ts.KEY_NAME}={KEY_VALUE}\n", KEY_VALUE),
        (f"export {ts.KEY_NAME}={KEY_VALUE}\n", KEY_VALUE),
        (f"  {ts.KEY_NAME}  =  {KEY_VALUE}  \n", KEY_VALUE),
        (f"{ts.KEY_NAME}={Q}a # b 'c'{Q}\n", "a # b 'c'"),
        (f"{ts.KEY_NAME}='a=b \"c\"'\n", 'a=b "c"'),
        (f"{ts.KEY_NAME}={Q}quoted{Q} # trailing comment\n", "quoted"),
        (f"{ts.KEY_NAME}=plain # comment\n", "plain"),
        (f"{ts.KEY_NAME}=\n", None),
        (f"{ts.KEY_NAME}={Q}{Q}\n", None),
        (f"{ts.KEY_NAME}=first\n{ts.KEY_NAME}=second\n", "second"),
        (f"# {ts.KEY_NAME}=commented\n", None),
        (f"{ts.KEY_NAME}_EXTRA=nope\n", None),
        ("", None),
    ],
)
def test_dotenv_parsing_rules(body, expected):
    assert ts.parse_dotenv_key(body) == expected


def test_symlink_is_refused(tmp_path):
    target = _write_env(tmp_path, f"{ts.KEY_NAME}={KEY_VALUE}\n")
    link = tmp_path / "link.env"
    link.symlink_to(target)
    assert ts.load_key({ts.ENABLE_ENV: "1", ts.DOTENV_ENV: str(link)}) is None


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o604, 0o660])
def test_group_or_world_bits_are_refused(tmp_path, mode):
    env = _env(tmp_path)
    Path(env[ts.DOTENV_ENV]).chmod(mode)
    assert ts.load_key(env) is None


def test_foreign_owner_is_refused(tmp_path, monkeypatch):
    env = _env(tmp_path)
    real = os.getuid()
    monkeypatch.setattr(os, "getuid", lambda: real + 1)
    assert ts.load_key(env) is None


def test_oversize_file_is_refused(tmp_path):
    body = f"{ts.KEY_NAME}={KEY_VALUE}\n" + "#" * ts.MAX_DOTENV_BYTES
    assert ts.load_key(_env(tmp_path, body)) is None


def test_directory_is_refused(tmp_path):
    folder = tmp_path / "dir.env"
    folder.mkdir(mode=0o700)
    assert ts.load_key({ts.ENABLE_ENV: "1", ts.DOTENV_ENV: str(folder)}) is None


def test_relative_path_and_missing_opt_in_are_off(tmp_path, monkeypatch):
    env = _env(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert ts.load_key({ts.ENABLE_ENV: "1", ts.DOTENV_ENV: "scout.env"}) is None
    assert ts.load_key({ts.DOTENV_ENV: env[ts.DOTENV_ENV]}) is None
    assert ts.load_key({ts.ENABLE_ENV: "true", ts.DOTENV_ENV: env[ts.DOTENV_ENV]}) is None


def test_key_in_process_environment_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv(ts.KEY_NAME, KEY_VALUE)
    assert ts.load_key(_env(tmp_path, "OTHER=1\n")) is None


@pytest.mark.parametrize("missing", ["O_NOFOLLOW", "getuid"])
def test_platform_without_nofollow_or_getuid_is_off_without_raising(
    tmp_path, monkeypatch, capsys, missing
):
    env = _env(tmp_path)
    monkeypatch.delattr(os, missing)
    assert ts.load_key(env) is None
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and ts.ENABLE_ENV in err and KEY_VALUE not in err


# --- transport (D-9.2) -------------------------------------------------------------


class FakeHTTPS(urllib.request.BaseHandler):
    handler_order = 100

    def __init__(self, script):
        self.script = list(script)
        self.requests: list[tuple[str, dict[str, str]]] = []

    def https_open(self, req):
        self.requests.append((req.full_url, dict(req.header_items())))
        status, headers, body = self.script.pop(0)
        response = urllib.response.addinfourl(
            io.BytesIO(body), email.message_from_string(headers + "\n"), req.full_url, status
        )
        response.msg = "fake"
        return response


def _via(handler):
    return lambda bearer, body, timeout: ts._urllib_transport(bearer, body, timeout, handler)


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
def test_redirects_are_never_followed(code):
    handler = FakeHTTPS(
        [
            (code, "Location: https://evil.example/steal\n", b""),
            (200, "Content-Type: application/json\n", b"{}"),
        ]
    )
    with pytest.raises(ts.TypeSafeUnavailable) as caught:
        ts.call_with_deadline("Bearer secret-bearer", b"{}", transport=_via(handler))
    assert str(caught.value) == f"http_{code}"
    assert [url for url, _ in handler.requests] == [ts.ENDPOINT]
    assert "secret-bearer" not in str(caught.value)


def test_default_urllib_opener_would_forward_authorization_on_302():
    """Control: proves the redirect test above would catch a plain opener."""
    handler = FakeHTTPS(
        [
            (302, "Location: https://evil.example/steal\n", b""),
            (200, "Content-Type: application/json\n", b"{}"),
        ]
    )
    opener = urllib.request.build_opener(handler)
    request = urllib.request.Request(
        ts.ENDPOINT, data=b"{}", headers={"Authorization": "Bearer secret-bearer"}
    )
    opener.open(request, timeout=1)
    assert handler.requests[1][0] == "https://evil.example/steal"
    assert handler.requests[1][1].get("Authorization") == "Bearer secret-bearer"


@pytest.mark.parametrize(
    "script,kind",
    [
        ([(401, "", b"denied")], "http_401"),
        ([(500, "", b"boom")], "http_500"),
        ([(200, "Content-Type: application/json\n", b"not json")], "JSONDecodeError"),
    ],
)
def test_http_errors_and_non_json_fail_closed(script, kind):
    with pytest.raises(ts.TypeSafeUnavailable) as caught:
        ts.call_with_deadline("Bearer b", b"{}", transport=_via(FakeHTTPS(script)))
    assert str(caught.value) == kind


def test_successful_call_posts_to_constant_endpoint_with_bearer():
    handler = FakeHTTPS([(200, "Content-Type: application/json\n", b'{"answers": {}}')])
    result = ts.call_with_deadline("Bearer b", b'{"x": 1}', transport=_via(handler))
    assert result == {"answers": {}}
    url, headers = handler.requests[0]
    assert url == ts.ENDPOINT and headers["Authorization"] == "Bearer b"


def test_slow_dns_hits_the_total_deadline(monkeypatch):
    def slow_dns(*args, **kwargs):
        time.sleep(5)
        raise socket.gaierror("slow")

    monkeypatch.setattr(socket, "getaddrinfo", slow_dns)
    started = time.monotonic()
    with pytest.raises(ts.TypeSafeUnavailable, match="deadline"):
        ts.call_with_deadline("Bearer b", b"{}", deadline=0.3)
    assert time.monotonic() - started < 1.5
    assert ts.DEADLINE_SECONDS == 3.0


def test_socket_timeout_fails_closed():
    transport = StubTransport(error=TimeoutError("read timed out"))
    with pytest.raises(ts.TypeSafeUnavailable, match="TimeoutError"):
        ts.call_with_deadline("Bearer b", b"{}", transport=transport)
    assert len(transport.calls) == 1


def test_no_retry_after_failure(tmp_path):
    transport = StubTransport(error=ConnectionResetError("reset"))
    text = "$200 budget, put $50 weekly into ETH on base from wallet:a to rail:b"
    result = ts.resolve_dca_request(text, _env(tmp_path), transport=transport)
    assert len(transport.calls) == 1
    assert result.status == "needs_clarification" and "amount_usd" in result.missing


# --- redaction and windows (D-9.3, R-2) --------------------------------------------

ADDRESS_CASES = {
    "evm": "0x" + "ab12" * 10,
    "solana": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
    "bech32": "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
    "ens": "vitalik.eth",
    "sns": "toly.sol",
    "email": "someone@example.com",
    "wallet": "wallet:my-main-wallet",
    "rail": "rail:bank-account-7",
}


@pytest.mark.parametrize("label", list(ADDRESS_CASES))
def test_each_address_class_never_leaves(tmp_path, label):
    secret = ADDRESS_CASES[label]
    text = f"send {secret} $200 then $50 weekly ETH on base {secret} from wallet:a to rail:b"
    transport = StubTransport(response={"answers": {}})
    ts.resolve_dca_request(text, _env(tmp_path), transport=transport)
    assert transport.calls, "an ambiguous amount must trigger one call"
    raw = transport.calls[0][1].decode()
    assert secret not in raw
    assert ts.redact(secret) == ts.REDACTED


def test_address_straddling_a_window_edge_sends_no_fragment(tmp_path):
    address = "0x" + "c0ffee" * 8
    text = f"$200 {address} $50 weekly ETH on base from wallet:a to rail:b"
    transport = StubTransport(response={"answers": {}})
    ts.resolve_dca_request(text, _env(tmp_path), transport=transport)
    state = transport.bodies()[0]["state"]
    for size in range(6, len(address)):
        for start in range(0, len(address) - size + 1, 6):
            assert address[start : start + size] not in state


def test_body_contains_only_candidate_windows_labels_and_model(tmp_path):
    filler = "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod"
    text = f"{filler} $200 budget {filler} put $50 weekly into ETH on base from wallet:a to rail:b"
    transport = StubTransport(response={"answers": {}})
    ts.resolve_dca_request(text, _env(tmp_path), transport=transport)
    body = transport.bodies()[0]
    assert set(body) == {"model", "state", "questions"}
    assert body["model"] == ts.MODEL == "jev-1.12"
    redacted = ts.redact(text)
    for window in body["state"].split("\n"):
        assert window in redacted
        assert len(window) <= len("$200") + 2 * ts.WINDOW_CHARS
    assert filler not in body["state"]
    assert set(body["questions"]) == {"amount_usd", "complete"}
    assert set(body["questions"]["amount_usd"]["criteria"]) == {"$200", "$50", "none"}


def test_windows_shrink_to_word_boundaries_and_never_extend():
    redacted = "aaaaaaaaaa bbbbbbbbbbbbbbbbbbbb $50 cccccccccccccccccccc dddddddddd"
    start = redacted.index("$50")
    windows = ts.candidate_windows(redacted, [(start, start + 3)])
    assert windows == ["bbbbbbbbbbbbbbbbbbbb $50 cccccccccccccccccccc"]


# --- fill rules (D-9.4, R-3, R-4, C-5) ---------------------------------------------

AMBIGUOUS_AMOUNT = "$200 budget, put $50 weekly into ETH on base from wallet:a to rail:b"


def _amount_answer(probabilities, confidence=0.95, chosen="$50", noul=0.97):
    return {
        "answers": {
            "amount_usd": choice(chosen, probabilities, confidence),
            "complete": complete(noul),
        }
    }


def test_high_confidence_amount_fills_but_needs_confirmation(tmp_path):
    transport = StubTransport(_amount_answer({"$200": 0.03, "$50": 0.96, "none": 0.01}))
    result = ts.resolve_dca_request(AMBIGUOUS_AMOUNT, _env(tmp_path), transport=transport)
    assert result.intent.amount_usd == 50.0
    assert result.field_sources["amount_usd"] == "model_selected"
    assert result.field_sources["asset"] == "regex"
    assert result.status == "needs_confirmation"
    assert result.question == "I read $50. Confirm or restate."


@pytest.mark.parametrize(
    "response",
    [
        _amount_answer({"$200": 0.03, "$50": 0.96, "none": 0.01}, confidence=0.85),
        _amount_answer({"$200": 0.35, "$50": 0.64, "none": 0.01}),
        _amount_answer({"$200": 0.03, "$50": 0.96, "none": 0.01}, noul=0.5),
        _amount_answer({"$200": 0.01, "$50": 0.01, "none": 0.98}, chosen="none"),
        _amount_answer({"$200": 0.03, "$50": 0.96, "none": 0.01}, chosen="$75"),
        _amount_answer({"$200": 0.03, "$50": 0.96}),
        _amount_answer({"$200": 0.03, "$50": 0.96, "none": 0.01, "$75": 0.0}),
        _amount_answer({"$200": 0.2, "$50": 0.96, "none": 0.01}),
        _amount_answer({"$200": -0.01, "$50": 1.0, "none": 0.01}),
        _amount_answer({"$200": "0.03", "$50": 0.96, "none": 0.01}),
        _amount_answer({"$200": 0.03, "$50": 0.96, "none": 0.01}, confidence=1.2),
        _amount_answer({"$200": 0.96, "$50": 0.03, "none": 0.01}, chosen="$50"),
        {"answers": {"amount_usd": {"type": "choice", "choice": "$50", "confidence": 0.99}}},
        {"answers": {"complete": complete()}},
        {"answers": "nope"},
        {},
        ["not", "a", "dict"],
        None,
    ],
)
def test_invalid_or_uncertain_answers_fall_back_to_clarification(tmp_path, response):
    transport = StubTransport(response)
    result = ts.resolve_dca_request(AMBIGUOUS_AMOUNT, _env(tmp_path), transport=transport)
    assert result.intent.amount_usd is None
    assert result.status == "needs_clarification"
    assert result.question == "Which amount usd should I use?"
    assert "amount_usd" not in result.field_sources


def test_identical_amount_spans_collapse_without_a_question(tmp_path):
    text = "$50 ETH weekly on base, yes $50, from wallet:a to rail:b"
    transport = StubTransport(error=AssertionError("no call expected"))
    result = ts.resolve_dca_request(text, _env(tmp_path), transport=transport)
    assert transport.calls == []
    assert result.intent.amount_usd == 50.0
    assert result.status == "needs_confirmation"


def test_negated_candidate_is_excluded_before_asking(tmp_path):
    text = "$50 weekly on base into ETH, not SOL, from wallet:a to rail:b"
    transport = StubTransport(
        {
            "answers": {
                "asset": choice("ETH", {"ETH": 0.97, "none": 0.03}),
                "complete": complete(),
            }
        }
    )
    result = ts.resolve_dca_request(text, _env(tmp_path), transport=transport)
    body = transport.bodies()[0]
    assert set(body["questions"]["asset"]["criteria"]) == {"ETH", "none"}
    assert result.intent.asset == "ETH"
    assert result.field_sources["asset"] == "model_selected"
    assert result.status == "needs_confirmation"


def test_negated_only_candidate_leaves_field_missing(tmp_path):
    text = "$50 weekly, not SOL, on base from wallet:a to rail:b"
    transport = StubTransport(error=AssertionError("no call expected"))
    result = ts.resolve_dca_request(text, _env(tmp_path), transport=transport)
    assert result.intent.asset is None and "asset" in result.missing
    assert transport.calls == []


def test_negated_regex_value_is_not_kept(tmp_path):
    text = "$50 weekly, not ETH, on base from wallet:a to rail:b"
    assert dca_v061.parse_dca_request(text).intent.asset == "ETH"
    result = ts.resolve_dca_request(text, _env(tmp_path), transport=StubTransport())
    assert result.intent.asset is None


def test_synonyms_fill_with_synonym_source_and_need_confirmation(tmp_path):
    text = "put $50 into ether every week on op mainnet from wallet:a to rail:b"
    transport = StubTransport(error=AssertionError("no call expected"))
    result = ts.resolve_dca_request(text, _env(tmp_path), transport=transport)
    assert transport.calls == []
    assert result.intent.asset == "ETH"
    assert result.intent.schedule == "weekly"
    assert result.intent.chain == "optimism"
    assert result.field_sources == {
        "asset": "synonym",
        "amount_usd": "regex",
        "chain": "synonym",
        "schedule": "synonym",
        "source": "regex",
        "destination": "regex",
    }
    assert result.status == "needs_confirmation"
    assert result.question == "I read ETH, optimism, weekly. Confirm or restate."


def test_chain_synonym_requires_on_form(tmp_path):
    text = "my base currency: $50 of ETH weekly, base amount, from wallet:a to rail:b"
    result = ts.resolve_dca_request(text, _env(tmp_path), transport=StubTransport())
    assert result.intent.chain is None and "chain" in result.missing


def test_chain_name_is_not_an_asset_candidate(tmp_path):
    text = "$50 BTC weekly on ethereum from wallet:a to rail:b"
    transport = StubTransport(error=AssertionError("no call expected"))
    result = ts.resolve_dca_request(text, _env(tmp_path), transport=transport)
    assert result.intent.asset == "BTC" and result.status == "ready"


def test_fully_regex_request_is_ready_without_a_call(tmp_path):
    transport = StubTransport(error=AssertionError("no call expected"))
    result = ts.resolve_dca_request(CORPUS[1], _env(tmp_path), transport=transport)
    assert result.status == "ready" and transport.calls == []


def test_source_and_destination_are_never_asked_or_model_filled(tmp_path):
    text = "$50 ETH weekly on base from wallet:a from wallet:b to rail:c"
    transport = StubTransport(error=AssertionError("no call expected"))
    result = ts.resolve_dca_request(text, _env(tmp_path), transport=transport)
    assert result.intent.source is None and "source" in result.missing


@pytest.mark.parametrize(
    "span,expected",
    [("$50", 50.0), ("$12.34", 12.34), ("$0.1", 0.1), ("$1.234", None), ("$0", None)],
)
def test_model_amount_decimal_boundary(span, expected):
    value = ts._amount(span)
    assert value == expected
    if value is not None:
        assert Decimal(str(value)) == Decimal(span.lstrip("$"))


# --- tool outputs (D-9.5) ----------------------------------------------------------


def test_host_outputs_carry_field_sources_and_no_preview(tmp_path, monkeypatch):
    for name, value in _env(tmp_path).items():
        monkeypatch.setenv(name, value)
    transport = StubTransport(_amount_answer({"$200": 0.03, "$50": 0.96, "none": 0.01}))
    monkeypatch.setattr(ts, "_urllib_transport", transport)
    host = ReadOnlyHost(FIXTURE)
    parsed = host.parse_dca_request(AMBIGUOUS_AMOUNT)
    preview = host.preview_dca(AMBIGUOUS_AMOUNT)
    for result in (parsed, preview):
        assert result["status"] == "needs_confirmation"
        assert result["field_sources"]["amount_usd"] == "model_selected"
    assert preview["preview"] is None
    assert "approval_state" not in preview


def test_no_key_or_request_text_in_failure_counts(tmp_path):
    ts.failure_counts.clear()
    text = "$200 budget, put $50 weekly into ETH on base from wallet:a to rail:b"
    ts.resolve_dca_request(text, _env(tmp_path), transport=StubTransport(error=OSError(text)))
    assert all(KEY_VALUE not in k and "budget" not in k for k in ts.failure_counts)


# --- review fixes (Harrier L1, L3; Kestrel negation clause) ------------------------


def test_fifo_at_dotenv_path_is_refused_without_hanging(tmp_path):
    fifo = tmp_path / "scout.fifo"
    os.mkfifo(fifo, 0o600)
    started = time.monotonic()
    assert ts.load_key({ts.ENABLE_ENV: "1", ts.DOTENV_ENV: str(fifo)}) is None
    assert time.monotonic() - started < 1.0


def test_bare_64_hex_and_long_base58_runs_are_redacted():
    hex64 = "ab" * 32
    base58_long = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU" * 2
    joined = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZ_RuJosgAsU7xKXtg2CW87d97TXJSDpb"
    for secret in (hex64, base58_long, joined):
        assert ts.redact(f"x {secret} y") == f"x {ts.REDACTED} y"


def test_chain_candidate_cannot_carry_a_64_hex_string(tmp_path):
    hex64 = "c0" * 32
    text = f"$50 ETH weekly on base or on {hex64} from wallet:a to rail:b"
    transport = StubTransport(response={"answers": {}})
    ts.resolve_dca_request(text, _env(tmp_path), transport=transport)
    raw = b"".join(body for _, body in transport.calls).decode()
    assert hex64 not in raw and "c0c0c0" not in raw
    found = ts.find_candidates(ts.redact(text))["chain"]
    assert [c.value for c in found] == ["base"]


def test_unknown_chain_names_are_capped_at_20_characters():
    found = ts.find_candidates("on abcdefghijklmnopqrstuvwxyz and on short")["chain"]
    assert [c.value for c in found] == ["short"]


def test_negation_lookback_stops_at_clause_punctuation(tmp_path):
    text = "buy $50 of ETH, not SOL, weekly on base from wallet:a to rail:b"
    found = ts.find_candidates(ts.redact(text))
    assert [(c.value, c.negated) for c in found["asset"]] == [("ETH", False), ("SOL", True)]
    assert [(c.value, c.negated) for c in found["schedule"]] == [("weekly", False)]
    assert [(c.value, c.negated) for c in found["chain"]] == [("base", False)]


# --- 0.7.1 hardening -----------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("$50 ETH weekly on base-sepolia from wallet:a to rail:b", ["base-sepolia"]),
        ("$50 ETH weekly on arc-testnet from wallet:a to rail:b", ["arc-testnet"]),
        ("$50 ETH weekly on base from wallet:a to rail:b", ["base"]),
        ("$50 ETH weekly on base. from wallet:a to rail:b", ["base"]),
        ("on arbitrum-sepolia", ["arbitrum-sepolia"]),
    ],
)
def test_hyphenated_chain_names_are_not_truncated(text, expected):
    assert [c.value for c in ts.find_candidates(text)["chain"]] == expected


def test_over_long_hyphenated_chain_is_dropped_not_truncated():
    found = ts.find_candidates("on abcdefghijklmnopqrst-uvw and on short")["chain"]
    assert [c.value for c in found] == ["short"]


def test_once_is_not_a_schedule_synonym(tmp_path):
    text = "my base currency is USD, $10 of bitcoin once on arc from wallet:a to rail:b"
    result = ts.resolve_dca_request(text, _env(tmp_path), transport=StubTransport())
    assert result.intent.schedule is None and "schedule" in result.missing


def test_weekly_once_i_get_paid_stays_weekly(tmp_path):
    text = "$50 ETH weekly, once I get paid, on base from wallet:a to rail:b"
    transport = StubTransport(error=AssertionError("no call expected"))
    result = ts.resolve_dca_request(text, _env(tmp_path), transport=transport)
    assert transport.calls == []
    assert result.intent.schedule == "weekly"


def test_zero_amount_is_not_filled_on_the_typesafe_path(tmp_path):
    text = "$0 ETH weekly on base from wallet:a to rail:b"
    transport = StubTransport(error=AssertionError("no call expected"))
    result = ts.resolve_dca_request(text, _env(tmp_path), transport=transport)
    assert result.intent.amount_usd is None
    assert result.status == "needs_clarification" and "amount_usd" in result.missing
