"""Synthetic public-wire contract tests; no hosted or chain evidence."""

import asyncio
import copy
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scout_portfolio_manager.hedwig_hosted_client import HedwigHostedClient, HedwigHostedError

FIXTURES = Path(__file__).parent / "fixtures"
REQUEST = json.loads((FIXTURES / "hedwig-hosted-request-v1.json").read_text())
RESPONSES = json.loads((FIXTURES / "hedwig-hosted-responses-v1.json").read_text())
SOURCE_URLS = json.loads((FIXTURES / "hedwig-source-urls-v1.json").read_text())


@pytest.mark.parametrize("case", SOURCE_URLS)
def test_shared_source_url_contract_preserves_accepted_strings(case):
    response = copy.deepcopy(RESPONSES["unknownIntermediate"])
    response["assessment"]["citations"] = [{"lane": "defi", "source": case["source"]}]
    client, _ = client_for(reply(response))
    if case["accepted"]:
        assert asyncio.run(client.assess(REQUEST)) == response
    else:
        with pytest.raises(HedwigHostedError, match="HEDWIG_RESPONSE_INVALID"):
            asyncio.run(client.assess(REQUEST))


def reply(
    value, *, status=200, content_type="application/json", redirected=False, retry_after=None
):
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()

    async def chunks():
        yield raw

    return SimpleNamespace(
        status=status,
        content_type=content_type,
        body=chunks(),
        redirected=redirected,
        retry_after=retry_after,
    )


def client_for(response, **options):
    calls = []

    async def transport(path, body, *, deadline, max_response_bytes):
        calls.append((path, body, deadline, max_response_bytes))
        return response

    return HedwigHostedClient(transport, enabled=True, **options), calls


def test_default_disabled_never_calls_transport():
    try:
        module = importlib.import_module("scout_portfolio_manager.hedwig_hosted_client")
    except ModuleNotFoundError:
        module = None
    assert module is not None, "the public hosted client must exist"

    async def transport(*args, **kwargs):
        pytest.fail("disabled client dispatched transport")

    client = module.HedwigHostedClient(transport=transport)
    with pytest.raises(module.HedwigHostedError, match="HEDWIG_DISABLED"):
        asyncio.run(client.assess({}))


@pytest.mark.parametrize("name", list(RESPONSES))
def test_complete_synthetic_score_envelopes_are_preserved(name):
    client, calls = client_for(reply(RESPONSES[name]))
    result = asyncio.run(client.assess(REQUEST))
    assert result == RESPONSES[name]
    assert calls[0][0] == "/v1/assess"
    assert type(calls[0][1]) is bytes
    assert json.loads(calls[0][1]) == REQUEST
    assert calls[0][3] == 32768
    assert len(calls) == 1


def test_escaped_utf16_code_units_are_preserved_in_request_and_response():
    body = copy.deepcopy(REQUEST)
    body["request"]["question"] = "escaped \ud800 code unit"
    response = copy.deepcopy(RESPONSES["unknownIntermediate"])
    response["assessment"]["note"] = "escaped \udfff code unit"
    client, calls = client_for(reply(response))
    assert asyncio.run(client.assess(body)) == response
    assert json.loads(calls[0][1]) == body


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("version",), 2),
        (("version",), True),
        (("extra",), "ignored"),
        (("assessment", "extra"), "ignored"),
        (("assessment", "score"), True),
        (("assessment", "score"), -0.1),
        (("assessment", "score"), 0.8),
        (("assessment", "proceed"), True),
        (("assessment", "proceed"), 0),
        (("assessment", "status"), "unavailable"),
        (("assessment", "verdict"), "DENY"),
        (("assessment", "rating"), 1.01),
        (("assessment", "label"), "approved"),
        (("assessment", "reasons"), [{"source": "provider", "code": "X", "text": "x"}]),
        (("assessment", "reasons"), [{"source": "check", "code": "X", "text": "x", "extra": 1}]),
        (("assessment", "citations"), [{"lane": "defi", "source": "https://u:p@example.invalid"}]),
        (("assessment", "citations"), [{"lane": "wrong", "source": "https://example.invalid"}]),
        (("assessment", "note"), "x" * 281),
        (("assessment", "rating"), float("nan")),
        (("reference",), None),
        (("reference", "handle"), "A" * 64),
        (("reference", "requestDigest"), "a" * 63),
        (("reference", "expiresAt"), True),
        (("reference", "expiresAt"), 9007199254740992),
        (("reference", "extra"), 1),
    ],
)
def test_inconsistent_or_unknown_score_fields_fail_closed(path, value):
    response = copy.deepcopy(RESPONSES["unknownIntermediate"])
    target = response
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    client, calls = client_for(reply(response))
    with pytest.raises(HedwigHostedError, match="HEDWIG_RESPONSE_INVALID"):
        asyncio.run(client.assess(REQUEST))
    assert len(calls) == 1


@pytest.mark.parametrize(
    "field",
    ["status", "score", "verdict", "proceed", "reasons", "label", "rating", "citations", "note"],
)
def test_each_of_the_nine_assessment_fields_is_required(field):
    response = copy.deepcopy(RESPONSES["allowThreshold"])
    del response["assessment"][field]
    client, _ = client_for(reply(response))
    with pytest.raises(HedwigHostedError, match="HEDWIG_RESPONSE_INVALID"):
        asyncio.run(client.assess(REQUEST))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("chainId",), "eip155:8453"),
        (("contractAddress",), "0x1234"),
        (("issuerSource", "origin"), "example.invalid"),
        (("issuerSource", "url"), "https://example.invalid"),
        (("issuerSource", "retrievedAt"), True),
        (("issuerSource", "extra"), "ignored"),
    ],
)
def test_nested_issuer_metadata_is_validated_without_discarding_fields(path, value):
    response = copy.deepcopy(RESPONSES["denyWithIssuer"])
    target = response["assessment"]["reasons"][1]["canonicalAsset"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    client, _ = client_for(reply(response))
    with pytest.raises(HedwigHostedError, match="HEDWIG_RESPONSE_INVALID"):
        asyncio.run(client.assess(REQUEST))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("version",), True),
        (("headers",), {"Authorization": "synthetic-only"}),
        (("identity",), {"ownerScope": "synthetic-only"}),
        (("request", "policy"), "synthetic"),
        (("request", "chainId"), "eip155:8453"),
        (("request", "action"), "pay"),
        (("request", "transaction", "signature"), "0x1234"),
        (("request", "transaction", "data"), "0x123"),
        (("request", "transaction", "value"), "01"),
        (("request", "transaction", "value"), str(2**255)),
        (("request", "transaction", "from"), "0x" + "0" * 39 + "1"),
        (("request", "contracts", "target"), "0x" + "1" * 40),
        (("request", "amounts"), []),
        (("request", "setup", "slippageBps"), True),
        (("request", "swapIntent", "approvalAmount"), "1"),
        (("request", "question"), "😀" * 1001),
    ],
)
def test_invalid_request_is_rejected_before_transport(path, value):
    request = copy.deepcopy(REQUEST)
    target = request
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    client, calls = client_for(reply(RESPONSES["allowThreshold"]))
    with pytest.raises(HedwigHostedError, match="HEDWIG_REQUEST_INVALID"):
        asyncio.run(client.assess(request))
    assert calls == []


def test_request_is_captured_before_transport_yields():
    async def run():
        request = copy.deepcopy(REQUEST)
        entered, release = asyncio.Event(), asyncio.Event()
        sent = []

        async def transport(path, body, **options):
            sent.append(body)
            entered.set()
            await release.wait()
            return reply(RESPONSES["denyWithIssuer"])

        task = asyncio.create_task(HedwigHostedClient(transport, enabled=True).assess(request))
        await entered.wait()
        request["request"]["transaction"]["data"] = "0xdead"
        release.set()
        assert await task == RESPONSES["denyWithIssuer"]
        assert json.loads(sent[0]) == REQUEST

    asyncio.run(run())


def test_non_plain_and_oversized_input_never_runs_custom_serialization():
    class Hostile(dict):
        def items(self):
            pytest.fail("custom serialization ran")

    cycle = {}
    cycle["cycle"] = cycle
    for request in [Hostile(REQUEST), cycle, {"padding": "x" * 32769}, {"bad": float("inf")}]:
        client, calls = client_for(reply(RESPONSES["allowThreshold"]))
        with pytest.raises(HedwigHostedError, match="HEDWIG_REQUEST_INVALID"):
            asyncio.run(client.assess(request))
        assert calls == []


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (400, "invalid_request"),
        (401, "authentication_required"),
        (403, "access_denied"),
        (413, "request_too_large"),
        (415, "unsupported_media_type"),
        (429, "rate_limited"),
        (503, "service_unavailable"),
    ],
)
def test_transport_errors_are_fixed_client_errors_without_score_or_retry(status, code):
    client, calls = client_for(
        reply(
            {"error": {"code": code, "message": "private response detail"}},
            status=status,
            retry_after="12" if status == 429 else None,
        )
    )
    with pytest.raises(HedwigHostedError) as caught:
        asyncio.run(client.assess(REQUEST))
    assert caught.value.code == code
    assert str(caught.value) == code
    assert caught.value.retry_after == (12 if status == 429 else None)
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("options", "code"),
    [
        ({"status": 402}, "HEDWIG_PAYMENT_REQUIRED"),
        ({"status": 302}, "HEDWIG_REDIRECT"),
        ({"redirected": True}, "HEDWIG_REDIRECT"),
        ({"content_type": "text/html"}, "HEDWIG_RESPONSE_INVALID"),
        ({"status": 500}, "HEDWIG_HTTP_ERROR"),
    ],
)
def test_no_payment_redirect_or_non_json_body_is_followed(options, code):
    response = reply(RESPONSES["allowThreshold"], **options)

    async def forbidden_body():
        pytest.fail("forbidden body was read")
        yield b""

    response.body = forbidden_body()
    client, calls = client_for(response)
    with pytest.raises(HedwigHostedError, match=code):
        asyncio.run(client.assess(REQUEST))
    assert len(calls) == 1


@pytest.mark.parametrize(
    "raw",
    [
        b"{",
        b"\xff",
        b'{"version":1,"version":1}',
        b'{"x":NaN}',
        b"[" * 4097 + b"]" * 4097,
        b"x" * 32769,
    ],
)
def test_malformed_duplicate_or_oversized_wire_data_is_rejected(raw):
    client, _ = client_for(reply(raw))
    with pytest.raises(HedwigHostedError, match="HEDWIG_RESPONSE_INVALID"):
        asyncio.run(client.assess(REQUEST))


def test_streamed_size_is_bounded_before_parsing_and_closes_on_failure():
    closed = []

    async def chunks():
        try:
            yield b" " * 32768
            yield b" "
            pytest.fail("read beyond the byte ceiling")
        finally:
            closed.append(True)

    response = reply({})
    response.body = chunks()
    client, _ = client_for(response)
    with pytest.raises(HedwigHostedError, match="HEDWIG_RESPONSE_INVALID"):
        asyncio.run(client.assess(REQUEST))
    assert closed == [True]


def test_report_forwards_opaque_reference_and_keeps_original_score():
    assert callable(getattr(HedwigHostedClient, "report", None)), "report client seam must exist"
    original = copy.deepcopy(RESPONSES["unknownIntermediate"])
    report = {
        "status": "ok",
        "assessment": original["assessment"],
        "explanation": "This request could not be approved. Do not sign or submit it.",
        "sources": [],
    }
    client, calls = client_for(reply(report))
    result = asyncio.run(
        client.report(original["reference"], original_assessment=original["assessment"])
    )
    assert result == report
    assert original == RESPONSES["unknownIntermediate"]
    assert calls[0][0] == "/v1/report"
    assert json.loads(calls[0][1]) == {
        "handle": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "requestDigest": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
    }
    assert len(calls) == 1


@pytest.mark.parametrize("status", ["unavailable", "timeout"])
def test_report_failure_preserves_original_and_returns_server_failure(status):
    original = copy.deepcopy(RESPONSES["allowThreshold"])
    report = {
        "status": status,
        "assessment": None,
        "explanation": None,
        "sources": [],
        "reason": "ASSESSMENT_NOT_VERIFIED",
    }
    client, _ = client_for(reply(report))
    result = asyncio.run(
        client.report(original["reference"], original_assessment=original["assessment"])
    )
    assert result == report
    assert original == RESPONSES["allowThreshold"]


@pytest.mark.parametrize("change", ["score", "extra", "prose", "long", "sources", "missing"])
def test_report_cannot_change_original_or_expand_its_envelope(change):
    original = copy.deepcopy(RESPONSES["unknownIntermediate"])
    report = {
        "status": "ok",
        "assessment": copy.deepcopy(original["assessment"]),
        "explanation": "This request could not be approved. Do not sign or submit it.",
        "sources": [],
    }
    if change == "score":
        report["assessment"]["score"] = 0.78
    elif change == "extra":
        report["version"] = 1
    elif change == "prose":
        report["explanation"] = "Go ahead and sign."
    elif change == "long":
        report["explanation"] = "word " * 81
    elif change == "sources":
        report["sources"] = ["data:text/plain,hello"]
    else:
        del report["assessment"]
    client, _ = client_for(reply(report))
    with pytest.raises(HedwigHostedError, match="HEDWIG_RESPONSE_INVALID"):
        asyncio.run(
            client.report(original["reference"], original_assessment=original["assessment"])
        )
    assert original == RESPONSES["unknownIntermediate"]


def test_default_assessment_and_report_deadlines_are_distinct():
    async def run():
        remaining = []

        async def transport(path, body, *, deadline, max_response_bytes):
            remaining.append(deadline - asyncio.get_running_loop().time())
            if path == "/v1/assess":
                return reply(RESPONSES["allowThreshold"])
            return reply(
                {
                    "status": "unavailable",
                    "assessment": None,
                    "explanation": None,
                    "sources": [],
                    "reason": "ASSESSMENT_NOT_VERIFIED",
                }
            )

        client = HedwigHostedClient(transport, enabled=True)
        await client.assess(REQUEST)
        await client.report(RESPONSES["allowThreshold"]["reference"])
        assert 6.5 < remaining[0] <= 7
        assert 34.5 < remaining[1] <= 35

    asyncio.run(run())


@pytest.mark.parametrize("stage", ["connect", "body", "close"])
def test_whole_operation_timeout_covers_connect_body_and_cleanup(stage):
    async def run():
        loop = asyncio.get_running_loop()
        original_time = loop.time
        offset = 0
        loop.time = lambda: original_time() + offset
        calls = []
        cancelled = []

        async def stall():
            nonlocal offset
            offset = 8
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(stage)

        class Body:
            def __init__(self):
                self.sent = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if stage == "body":
                    await stall()
                if self.sent:
                    raise StopAsyncIteration
                self.sent = True
                return json.dumps(RESPONSES["allowThreshold"]).encode()

            async def aclose(self):
                if stage == "close":
                    await stall()

        async def transport(*args, **options):
            calls.append(1)
            if stage == "connect":
                await stall()
            response = reply({})
            response.body = Body()
            return response

        client = HedwigHostedClient(transport, enabled=True)
        try:
            with pytest.raises(HedwigHostedError, match="HEDWIG_TIMEOUT"):
                await asyncio.wait_for(client.assess(REQUEST), timeout=10)
            await asyncio.sleep(0)
            assert len(calls) == 1
            assert cancelled == [stage]
        finally:
            loop.time = original_time

    asyncio.run(run())


def test_deadline_is_not_reset_after_headers_and_late_success_is_rejected():
    async def run():
        loop = asyncio.get_running_loop()
        original_time = loop.time
        offset = 0
        loop.time = lambda: original_time() + offset
        try:

            async def transport(*args, **kwargs):
                nonlocal offset
                offset = 8
                return reply(RESPONSES["allowThreshold"])

            with pytest.raises(HedwigHostedError, match="HEDWIG_TIMEOUT"):
                await HedwigHostedClient(transport, enabled=True).assess(REQUEST)
        finally:
            loop.time = original_time

    asyncio.run(run())


@pytest.mark.parametrize("blocking_close", [False, True], ids=["cooperative", "stalled"])
def test_acquired_body_timeout_keeps_detached_cleanup_bounded(blocking_close):
    """Offline regression: an acquired body needs async cleanup after its read expires."""

    async def run():
        loop = asyncio.get_running_loop()
        original_time = loop.time
        offset = 0
        loop.time = lambda: original_time() + offset
        release = asyncio.Event()
        finished = asyncio.Event()
        close_calls = []
        closed = []
        cancelled = []

        class Body:
            def __aiter__(self):
                return self

            async def __anext__(self):
                nonlocal offset
                offset = 8
                await asyncio.Event().wait()

            async def aclose(self):
                close_calls.append(1)
                try:
                    await release.wait()
                    closed.append(True)
                except asyncio.CancelledError:
                    cancelled.append(True)
                    raise
                finally:
                    finished.set()

        response = reply({})
        response.body = Body()
        client, calls = client_for(response)
        try:
            with pytest.raises(HedwigHostedError, match="HEDWIG_TIMEOUT"):
                await client.assess(REQUEST)
            # Cleanup can finish only after the caller has received its timeout.
            if not blocking_close:
                release.set()
            await asyncio.wait_for(finished.wait(), timeout=0.3)
            assert close_calls == [1]
            assert len(calls) == 1
            assert closed == ([] if blocking_close else [True])
            assert cancelled == ([True] if blocking_close else [])
        finally:
            loop.time = original_time
            release.set()

    asyncio.run(run())


@pytest.mark.parametrize("late", [False, True])
@pytest.mark.parametrize("blocking_close", [False, True])
def test_abandoned_transport_response_closes_once_without_delaying_timeout(late, blocking_close):
    async def run():
        loop = asyncio.get_running_loop()
        original_time = loop.time
        offset = 0
        loop.time = lambda: original_time() + offset
        release = asyncio.Event()
        closed = asyncio.Event()
        close_calls = []

        class Body:
            async def __anext__(self):
                pytest.fail("an abandoned response body must not be read")

            async def aclose(self):
                close_calls.append(1)
                try:
                    if blocking_close:
                        await asyncio.Event().wait()
                finally:
                    closed.set()

        async def transport(*args, **kwargs):
            nonlocal offset
            if late:
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    await release.wait()
            else:
                offset = 8
            response = reply({})
            response.body = Body()
            return response

        try:
            client = HedwigHostedClient(transport, enabled=True, assessment_timeout=0.02)
            with pytest.raises(HedwigHostedError, match="HEDWIG_TIMEOUT"):
                await client.assess(REQUEST)
            release.set()
            await asyncio.wait_for(closed.wait(), timeout=0.3)
            assert close_calls == [1]
        finally:
            loop.time = original_time
            release.set()

    asyncio.run(run())


@pytest.mark.parametrize(
    "options",
    [
        {"assessment_timeout": 7.01},
        {"report_timeout": 35.01},
        {"assessment_timeout": True},
        {"assessment_timeout": 0},
        {"report_timeout": float("inf")},
    ],
)
def test_invalid_time_limits_cannot_dispatch(options):
    client, calls = client_for(reply({}), **options)
    with pytest.raises(HedwigHostedError, match="HEDWIG_CONFIG_INVALID"):
        asyncio.run(client.assess(REQUEST))
    assert calls == []


def test_missing_transport_and_injected_auth_or_connection_failure_are_safe():
    with pytest.raises(HedwigHostedError, match="HEDWIG_CONFIG_INVALID"):
        asyncio.run(HedwigHostedClient(enabled=True).assess(REQUEST))
    for error, expected in [
        (RuntimeError("private transport detail"), "HEDWIG_TRANSPORT_FAILED"),
        (HedwigHostedError("authentication_required"), "authentication_required"),
    ]:
        calls = []

        async def transport(*args, **kwargs):
            calls.append(1)
            raise error

        with pytest.raises(HedwigHostedError) as caught:
            asyncio.run(HedwigHostedClient(transport, enabled=True).assess(REQUEST))
        assert str(caught.value) == expected
        assert len(calls) == 1


@pytest.mark.parametrize("header", [None, "-1", "86401", "1.5", "Wed, 21 Oct 2026 07:28:00 GMT"])
def test_rate_limit_header_is_a_bounded_integer_without_retry(header):
    client, calls = client_for(
        reply(
            {"error": {"code": "rate_limited", "message": "Wait."}}, status=429, retry_after=header
        )
    )
    with pytest.raises(HedwigHostedError, match="HEDWIG_RESPONSE_INVALID"):
        asyncio.run(client.assess(REQUEST))
    assert len(calls) == 1


def test_successful_report_prose_and_exact_response_byte_boundaries():
    original = RESPONSES["allowThreshold"]
    report = {
        "status": "ok",
        "assessment": original["assessment"],
        "explanation": " ".join(["Synthetic"] * 80),
        "sources": ["https://example.invalid/source"],
    }
    raw = json.dumps(report).encode()
    padded = raw + b" " * (32768 - len(raw))
    client, _ = client_for(reply(padded))
    assert asyncio.run(client.report(original["reference"])) == report
    client, _ = client_for(reply(padded + b" "))
    with pytest.raises(HedwigHostedError, match="HEDWIG_RESPONSE_INVALID"):
        asyncio.run(client.report(original["reference"]))
    for explanation in [" ".join(["Synthetic"] * 81), "a" * 2401]:
        client, _ = client_for(reply({**report, "explanation": explanation}))
        with pytest.raises(HedwigHostedError, match="HEDWIG_RESPONSE_INVALID"):
            asyncio.run(client.report(original["reference"]))


def test_report_request_rejects_extra_fields_and_does_not_recompute_digest():
    ref = {"handle": "1" * 64, "requestDigest": "a" * 64}
    report = {
        "status": "unavailable",
        "assessment": None,
        "explanation": None,
        "sources": [],
        "reason": "ASSESSMENT_NOT_VERIFIED",
    }
    client, calls = client_for(reply(report))
    assert asyncio.run(client.report(ref)) == report
    assert json.loads(calls[0][1]) == ref
    for invalid in [
        {**ref, "question": "re-score"},
        {**ref, "authorization": "synthetic"},
        {**ref, "handle": "x" * 64},
        {**ref, "expiresAt": True},
        None,
    ]:
        client, calls = client_for(reply(report))
        with pytest.raises(HedwigHostedError, match="HEDWIG_REQUEST_INVALID"):
            asyncio.run(client.report(invalid))
        assert calls == []
