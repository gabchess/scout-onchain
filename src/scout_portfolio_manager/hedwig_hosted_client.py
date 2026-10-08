"""Offline hosted-client seam. All transport effects require explicit injection."""

from __future__ import annotations

import asyncio
import json
import math
import re
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar
from urllib.parse import urlsplit

MAX_BYTES = 32768
MAX_SAFE_INTEGER = 9007199254740991
ASSESSMENT_FIELDS = "status score verdict proceed reasons label rating citations note".split()
LABELS = (
    "documented-canonical",
    "documented-lookalike",
    "documented-risk-pattern",
    "no-documentation",
)
HTTP_ERRORS = {
    400: "invalid_request",
    401: "authentication_required",
    403: "access_denied",
    413: "request_too_large",
    415: "unsupported_media_type",
    429: "rate_limited",
    503: "service_unavailable",
}
T = TypeVar("T")


class ResponseBody(Protocol):
    def __aiter__(self) -> ResponseBody: ...
    async def __anext__(self) -> bytes: ...
    async def aclose(self) -> None: ...


class HostedResponse(Protocol):
    status: int
    content_type: str
    redirected: bool
    retry_after: str | None
    body: ResponseBody


class HostedTransport(Protocol):
    async def __call__(
        self, path: str, body: bytes, *, deadline: float, max_response_bytes: int
    ) -> HostedResponse: ...


def _require(condition: bool) -> None:
    if not condition:
        raise ValueError("invalid")


def _keys(value: Any, required: list[str], optional: tuple[str, ...] = ()) -> bool:
    return type(value) is dict and set(required) <= value.keys() <= set(required) | set(optional)


def _text(value: Any, maximum: int) -> bool:
    return type(value) is str and len(value.encode("utf-16-le", "surrogatepass")) // 2 <= maximum


def _integer(value: Any, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value <= MAX_SAFE_INTEGER


def _unit(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def _hex(value: Any) -> bool:
    return type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _https(value: Any, maximum: int = 280) -> bool:
    if not _text(value, maximum) or re.search(r"[\x00-\x1f\x7f\\]", value):
        return False
    authority = re.match(r"https://([^/?#]+)", value, re.I)
    if not authority or re.search(r"\s", authority[1]):
        return False
    try:
        url = urlsplit(value)
        port = url.port  # Access validates malformed and out-of-range ports.
        return (
            url.scheme == "https"
            and bool(url.hostname)
            and url.username is None
            and url.password is None
            and (port is None or 0 <= port <= 65535)
        )
    except ValueError:
        return False


def _reference(value: Any) -> None:
    _require(_keys(value, ["handle", "requestDigest", "expiresAt"]))
    _require(
        _hex(value["handle"]) and _hex(value["requestDigest"]) and _integer(value["expiresAt"])
    )


def _assessment(value: Any) -> None:
    _require(_keys(value, ASSESSMENT_FIELDS))
    status, score, verdict = value["status"], value["score"], value["verdict"]
    _require(status in ("ok", "unavailable", "timeout") and _unit(score))
    _require(verdict in ("ALLOW_UNDER_POLICY", "DENY", "UNKNOWN"))
    _require(
        type(value["proceed"]) is bool and value["proceed"] == (verdict == "ALLOW_UNDER_POLICY")
    )
    _require(status == "ok" or (score == 0 and verdict == "UNKNOWN"))
    _require(
        (verdict == "DENY" and score == 0)
        or (verdict == "UNKNOWN" and score < 0.8)
        or (verdict == "ALLOW_UNDER_POLICY" and score >= 0.8 and status == "ok")
    )
    _require(value["label"] is None or value["label"] in LABELS)
    _require(value["rating"] is None or _unit(value["rating"]))
    _require(_text(value["note"], 280))
    _require(type(value["reasons"]) is list and len(value["reasons"]) <= 64)
    for reason in value["reasons"]:
        _require(_keys(reason, ["source", "code", "text"], ("canonicalAsset",)))
        _require(reason["source"] in ("check", "model") and _text(reason["text"], 280))
        _require(
            type(reason["code"]) is str
            and re.fullmatch(r"[A-Z0-9_]{1,64}", reason["code"]) is not None
        )
        if "canonicalAsset" in reason:
            _require(
                reason["source"] == "check" and reason["code"] == "SWAP_TOKEN_OUT_NOT_CANONICAL"
            )
            asset = reason["canonicalAsset"]
            _require(_keys(asset, ["chainId", "symbol", "contractAddress", "issuerSource"]))
            _require(asset["chainId"] == "eip155:143" and asset["symbol"] == "USDC")
            _require(
                type(asset["contractAddress"]) is str
                and re.fullmatch(r"0x[0-9a-fA-F]{40}", asset["contractAddress"]) is not None
            )
            issuer = asset["issuerSource"]
            _require(_keys(issuer, ["origin", "url", "retrievedAt"]))
            _require(
                issuer["origin"] == "circle.com"
                and issuer["url"]
                == "https://developers.circle.com/stablecoins/usdc-contract-addresses"
            )
            _require(_integer(issuer["retrievedAt"], 1))
    _require(type(value["citations"]) is list and len(value["citations"]) <= 32)
    for citation in value["citations"]:
        _require(_keys(citation, ["lane", "source"]))
        _require(
            citation["lane"] in ("defi", "payments", "security", "opsec")
            and _https(citation["source"])
        )


def _score_envelope(value: Any) -> None:
    _require(_keys(value, ["version", "assessment", "reference"]))
    _require(type(value["version"]) is int and value["version"] == 1)
    _assessment(value["assessment"])
    if value["reference"] is not None:
        _require(value["assessment"]["status"] != "timeout")
        _reference(value["reference"])
    else:
        _require(value["assessment"]["score"] == 0 and value["assessment"]["proceed"] is False)


def _capture(value: Any) -> bytes:
    nodes = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        _require(nodes <= 4096 and depth <= 8)
        if item is None or type(item) is bool:
            return
        if type(item) is str:
            _require(
                len(item) <= MAX_BYTES
                and len(item.encode("utf-8", "backslashreplace")) <= MAX_BYTES
            )
        elif type(item) is int:
            _require(abs(item) <= MAX_SAFE_INTEGER)
        elif type(item) is float:
            _require(math.isfinite(item))
        elif type(item) is list:
            _require(len(item) <= 4096)
            for child in item:
                visit(child, depth + 1)
        elif type(item) is dict:
            _require(len(item) <= 4096)
            for key, child in item.items():
                _require(type(key) is str)
                visit(key, depth + 1)
                visit(child, depth + 1)
        else:
            raise ValueError("invalid")

    visit(value, 0)
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode(
        "utf-8", "backslashreplace"
    )
    _require(len(raw) <= MAX_BYTES)
    return raw


def _address(value: Any) -> bool:
    return (
        type(value) is str
        and re.fullmatch(r"0x[0-9a-fA-F]{40}", value) is not None
        and int(value, 16) > 0
    )


def _amount(value: Any, *, positive: bool = False) -> bool:
    return (
        type(value) is str
        and len(value) <= 78
        and re.fullmatch(r"0|[1-9][0-9]*", value) is not None
        and (0 < int(value) if positive else 0 <= int(value))
        and int(value) < 2**256
    )


def _request(body: Any) -> None:
    _require(
        _keys(body, ["version", "request"])
        and type(body["version"]) is int
        and body["version"] == 1
    )
    r = body["request"]
    _require(
        _keys(
            r,
            ["chainId", "action", "transaction", "contracts", "amounts", "setup", "swapIntent"],
            ("question",),
        )
    )
    _require(r["chainId"] == "eip155:143" and r["action"] == "swap")
    _require("question" not in r or _text(r["question"], 2000))
    tx, intent, setup, contracts = r["transaction"], r["swapIntent"], r["setup"], r["contracts"]
    _require(_keys(tx, ["from", "to", "data", "value"]))
    _require(_address(tx["from"]) and int(tx["from"], 16) > 2 and _address(tx["to"]))
    _require(tx["to"].lower() == "0xfe31f71c1b106eac32f1a19239c9a9a72ddfb900")
    _require(_amount(tx["value"], positive=True) and int(tx["value"]) < 2**255)
    _require(
        _text(tx["data"], 16384) and re.fullmatch(r"0x(?:[0-9a-fA-F]{2})+", tx["data"]) is not None
    )
    _require(
        _keys(contracts, ["target", "token_out"]) and all(_address(v) for v in contracts.values())
    )
    _require(contracts["target"].lower() == tx["to"].lower())
    _require(type(r["amounts"]) is list and len(r["amounts"]) == 1)
    amount = r["amounts"][0]
    _require(_keys(amount, ["asset", "amount", "direction"]))
    _require(amount == {"asset": "MON", "amount": tx["value"], "direction": "in"})
    _require(
        _keys(
            intent,
            ["tokenIn", "tokenOutSymbol", "recipient", "quotedOut", "minOut", "approvalAmount"],
        )
    )
    _require(
        _keys(intent["tokenIn"], ["kind", "symbol"])
        and intent["tokenIn"] == {"kind": "native", "symbol": "MON"}
    )
    _require(intent["tokenOutSymbol"] == "USDC" and intent["approvalAmount"] == "0")
    _require(_address(intent["recipient"]) and intent["recipient"].lower() == tx["from"].lower())
    _require(
        _amount(intent["quotedOut"], positive=True) and _amount(intent["minOut"], positive=True)
    )
    _require(_keys(setup, ["slippageBps", "deadline"]) and _integer(setup["deadline"], 1))
    _require(_integer(setup["slippageBps"]) and setup["slippageBps"] <= 10000)
    quote, minimum = int(intent["quotedOut"]), int(intent["minOut"])
    _require(minimum <= quote and setup["slippageBps"] == (quote - minimum) * 10000 // quote)


class HedwigHostedError(Exception):
    """A fixed client error, never a fabricated assessment."""

    def __init__(self, code: str, *, retry_after: int | None = None) -> None:
        allowed = tuple(HTTP_ERRORS.values()) + (
            "HEDWIG_DISABLED",
            "HEDWIG_CONFIG_INVALID",
            "HEDWIG_REQUEST_INVALID",
            "HEDWIG_RESPONSE_INVALID",
            "HEDWIG_PAYMENT_REQUIRED",
            "HEDWIG_REDIRECT",
            "HEDWIG_HTTP_ERROR",
            "HEDWIG_TIMEOUT",
            "HEDWIG_TRANSPORT_FAILED",
        )
        self.code = code if type(code) is str and code in allowed else "HEDWIG_TRANSPORT_FAILED"
        self.retry_after = (
            retry_after
            if self.code == "rate_limited"
            and type(retry_after) is int
            and 0 <= retry_after <= 86400
            else None
        )
        super().__init__(self.code)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _parse(raw: bytes) -> Any:
    value = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=lambda _: _require(False),
    )
    _capture(value)
    return value


def _report(value: Any, original: Any = None) -> None:
    _require(_keys(value, ["status", "assessment", "explanation", "sources"], ("reason",)))
    _require(value["status"] in ("ok", "unavailable", "timeout"))
    assessment = value["assessment"]
    if assessment is not None:
        _assessment(assessment)
        _require(original is None or assessment == original)
    _require(type(value["sources"]) is list and len(value["sources"]) <= 32)
    _require(all(_https(source, 1024) for source in value["sources"]))
    if value["status"] != "ok":
        _require(
            type(value.get("reason")) is str
            and re.fullmatch(r"[A-Z0-9_]{1,64}", value["reason"]) is not None
        )
        _require(value["explanation"] is None and value["sources"] == [])
        return
    _require("reason" not in value and assessment is not None)
    prose = value["explanation"]
    _require(_text(prose, 2400) and 0 < len(prose.split()) <= 80)
    if not assessment["proceed"]:
        expected = (
            "This request was denied. Do not sign or submit it."
            if assessment["verdict"] == "DENY"
            else "This request could not be approved. Do not sign or submit it."
        )
        allowed: list[tuple[str, list[str]]] = [(expected, [])]
        reasons = assessment["reasons"]
        if assessment["verdict"] == "DENY":
            mismatch = next(
                (
                    reason
                    for reason in reasons
                    if reason["source"] == "check"
                    and reason["code"] == "SWAP_TOKEN_OUT_NOT_CANONICAL"
                ),
                None,
            )
            if mismatch is not None:
                prefix = "This request was denied. Its output token differs from USDC on Monad. "
                suffix = " Do not sign or submit it."
                allowed.append(
                    (prefix + "The replacement address is unavailable in this report." + suffix, [])
                )
                asset = mismatch.get("canonicalAsset")
                # _assessment already validated all issuer fields at this wire boundary.
                if asset and _address(asset["contractAddress"]):
                    allowed.append(
                        (
                            prefix + f"Verified USDC: {asset['contractAddress']}." + suffix,
                            [asset["issuerSource"]["url"]],
                        )
                    )
        elif any(
            reason["source"] == "check"
            and reason["code"] in ("CHECKS_UNAVAILABLE", "RETRIEVAL_UNAVAILABLE")
            for reason in reasons
        ):
            allowed.append(
                (
                    "This request could not be approved. Required evidence is unavailable. "
                    "Do not sign or submit it.",
                    [],
                )
            )
        _require((prose, value["sources"]) in allowed)


def _live(deadline: float) -> None:
    if asyncio.get_running_loop().time() >= deadline:
        raise HedwigHostedError("HEDWIG_TIMEOUT")


def _close_abandoned(response: HostedResponse) -> None:
    # Close an unused body once, off the caller's path, with its own bounded
    # cooperative cleanup budget.
    try:
        task = asyncio.ensure_future(response.body.aclose())
        timer = asyncio.get_running_loop().call_later(0.1, task.cancel)

        def settled(done: asyncio.Future[None]) -> None:
            timer.cancel()
            if not done.cancelled():
                done.exception()

        task.add_done_callback(settled)
    except Exception:
        pass


async def _bounded(
    operation: Awaitable[T], deadline: float, abandon: Callable[[T], None] | None = None
) -> T:
    task = asyncio.ensure_future(operation)
    delivered = False
    try:
        remaining = max(0, deadline - asyncio.get_running_loop().time())
        done, _ = await asyncio.wait({task}, timeout=remaining)
        _live(deadline)
        if not done:
            raise HedwigHostedError("HEDWIG_TIMEOUT")
        result = task.result()
        delivered = True
        return result
    finally:
        if not task.done():
            task.cancel()

        def settled(done: asyncio.Future[T]) -> None:
            if not done.cancelled() and done.exception() is None and not delivered and abandon:
                abandon(done.result())

        # Observe late failures and reclaim unused transport results without
        # waiting for a transport that suppresses cancellation.
        task.add_done_callback(settled)


class HedwigHostedClient:
    """Captured JSON over an injected transport; no HTTP/auth/environment wiring.

    The operator's transport owns origin and credentials, must disable redirect
    following/retries, and must cooperate with cancellation and bounded buffering.
    It returns metadata plus an async byte iterator with async aclose(). Deadlines
    use the running event loop's monotonic clock. Outputs are detached plain JSON;
    this client caches no assessment and supplies no execution or payment hooks.
    """

    def __init__(
        self,
        transport: HostedTransport | None = None,
        *,
        enabled: bool = False,
        assessment_timeout: float = 7.0,
        report_timeout: float = 35.0,
    ) -> None:
        self._transport = transport
        self._enabled = enabled
        self._assessment_timeout = assessment_timeout
        self._report_timeout = report_timeout

    def _deadline(self, report: bool = False) -> float:
        if self._enabled is not True:
            raise HedwigHostedError("HEDWIG_DISABLED")
        for value, maximum in [(self._assessment_timeout, 7), (self._report_timeout, 35)]:
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not 0 < value <= maximum
            ):
                raise HedwigHostedError("HEDWIG_CONFIG_INVALID")
        if not callable(self._transport):
            raise HedwigHostedError("HEDWIG_CONFIG_INVALID")
        return asyncio.get_running_loop().time() + (
            self._report_timeout if report else self._assessment_timeout
        )

    async def assess(self, body: Any) -> dict[str, Any]:
        """Capture the complete version-1 unsigned request and return its score envelope."""
        deadline = self._deadline()
        try:
            captured = _capture(body)
            _request(json.loads(captured))
        except (ValueError, TypeError, KeyError, RecursionError):
            raise HedwigHostedError("HEDWIG_REQUEST_INVALID") from None
        return await self._exchange("/v1/assess", captured, _score_envelope, deadline)

    async def report(self, reference: Any, *, original_assessment: Any = None) -> dict[str, Any]:
        """Send only handle/digest; optionally bind the returned assessment to a local copy.

        expiresAt is accepted from a saved reference but never transmitted or extended.
        The optional original stays local. Owner/digest verification belongs to Hedwig.
        """
        deadline = self._deadline(report=True)
        try:
            ref = json.loads(_capture(reference))
            _require(_keys(ref, ["handle", "requestDigest"], ("expiresAt",)))
            _require(_hex(ref["handle"]) and _hex(ref["requestDigest"]))
            _require("expiresAt" not in ref or _integer(ref["expiresAt"]))
            captured = _capture({"handle": ref["handle"], "requestDigest": ref["requestDigest"]})
            original = None
            if original_assessment is not None:
                original = json.loads(_capture(original_assessment))
                _assessment(original)
        except (ValueError, TypeError, KeyError, RecursionError):
            raise HedwigHostedError("HEDWIG_REQUEST_INVALID") from None
        return await self._exchange(
            "/v1/report", captured, lambda value: _report(value, original), deadline
        )

    async def _exchange(
        self, path: str, captured: bytes, validate: Callable[[Any], None], deadline: float
    ) -> dict[str, Any]:
        response = None
        completed = False
        try:
            _live(deadline)
            assert self._transport is not None
            response = await _bounded(
                self._transport(path, captured, deadline=deadline, max_response_bytes=MAX_BYTES),
                deadline,
                _close_abandoned,
            )
            status = response.status
            _require(type(status) is int and type(response.redirected) is bool)
            if response.redirected or 300 <= status < 400:
                raise HedwigHostedError("HEDWIG_REDIRECT")
            if status == 402:
                raise HedwigHostedError("HEDWIG_PAYMENT_REQUIRED")
            if status != 200 and status not in HTTP_ERRORS:
                raise HedwigHostedError("HEDWIG_HTTP_ERROR")
            _require(
                type(response.content_type) is str
                and re.fullmatch(
                    r"application/json(?:\s*;\s*charset=utf-8)?", response.content_type, re.I
                )
                is not None
            )
            raw = bytearray()
            while True:
                try:
                    chunk = await _bounded(anext(response.body), deadline)
                except StopAsyncIteration:
                    break
                _require(type(chunk) is bytes and 0 < len(chunk) <= MAX_BYTES - len(raw))
                raw.extend(chunk)
            value = _parse(bytes(raw))
            if status != 200:
                _require(_keys(value, ["error"]) and _keys(value["error"], ["code", "message"]))
                _require(
                    value["error"]["code"] == HTTP_ERRORS[status]
                    and _text(value["error"]["message"], 280)
                )
                retry = None
                if status == 429:
                    header = response.retry_after
                    if not isinstance(header, str):
                        raise ValueError("invalid")
                    _require(
                        re.fullmatch(r"[0-9]{1,5}", header) is not None and int(header) <= 86400
                    )
                    retry = int(header)
                raise HedwigHostedError(HTTP_ERRORS[status], retry_after=retry)
            validate(value)
            _live(deadline)
            completed = True
            return dict(value)
        except HedwigHostedError as error:
            raise HedwigHostedError(error.code, retry_after=error.retry_after) from None
        except (ValueError, TypeError, KeyError, RecursionError, AttributeError):
            raise HedwigHostedError("HEDWIG_RESPONSE_INVALID") from None
        except Exception:
            raise HedwigHostedError("HEDWIG_TRANSPORT_FAILED") from None
        finally:
            if (
                response is not None
                and not completed
                and asyncio.get_running_loop().time() >= deadline
            ):
                _close_abandoned(response)
            elif response is not None:
                try:
                    await _bounded(response.body.aclose(), deadline)
                except Exception:
                    if completed:
                        if asyncio.get_running_loop().time() >= deadline:
                            raise HedwigHostedError("HEDWIG_TIMEOUT") from None
                        raise HedwigHostedError("HEDWIG_TRANSPORT_FAILED") from None
