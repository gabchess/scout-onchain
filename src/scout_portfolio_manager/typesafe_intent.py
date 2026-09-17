"""Optional TypeSafe (Jev) DCA intent resolution, off by default (ADR 0004 D-9).

Runs only when the MCP server environment sets ``SCOUT_TYPESAFE=1`` and an absolute
``SCOUT_DOTENV`` path, and that file holds ``TYPESAFE_API_KEY``. Otherwise
``resolve_dca_request`` returns the 0.6.1 regex result unchanged.

Code finds every candidate. Jev only chooses among candidates the text already
contains, and any value not produced by the 0.6.1 regex returns
``needs_confirmation``, never ``ready``. Only redacted candidate windows, option
labels and the model id leave the machine. No key, request text or response body
is ever logged, raised or returned.
"""

from __future__ import annotations

import json
import os
import re
import stat
import sys
import threading
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .dca import DcaIntent, DcaParseResult, parse_dca_request

ENABLE_ENV = "SCOUT_TYPESAFE"
DOTENV_ENV = "SCOUT_DOTENV"
KEY_NAME = "TYPESAFE_API_KEY"
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
#: From the TypeSafe cookbook, 2026-09-16. Availability is UNVERIFIED: no key exists.
MODEL = "jev-1.12"
DEADLINE_SECONDS = 3.0
SOCKET_TIMEOUT_SECONDS = 2.5
MAX_DOTENV_BYTES = 65536
WINDOW_CHARS = 24
NONE_OPTION = "none"

FILL_MARGIN = 0.3
THRESHOLDS = {"amount_usd": 0.9, "asset": 0.9, "chain": 0.8, "schedule": 0.8}
COMPLETE_THRESHOLD = 0.9
PROBABILITY_SUM_TOLERANCE = 0.01

#: Failure counts by kind. Never holds request text, keys or response bodies.
failure_counts: Counter[str] = Counter()


class TypeSafeUnavailable(Exception):
    """The call failed; the caller falls back to the 0.6.1 result."""


class _ApiKey:
    """Holds the key privately. Never printed, compared to other secrets, or exported."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def bearer(self) -> str:
        return f"Bearer {self._value}"

    def __repr__(self) -> str:
        return "<TypeSafe key redacted>"

    __str__ = __repr__


# --- activation and the one-variable .env reader (D-9.1) ---------------------------


def _notice(message: str) -> None:
    print(f"scout: {message}", file=sys.stderr)


def load_key(environ: Mapping[str, str]) -> Optional[_ApiKey]:
    """Return the key only when the feature is explicitly enabled and the file is safe."""
    if (environ.get(ENABLE_ENV) or "").strip() != "1":
        return None
    path = (environ.get(DOTENV_ENV) or "").strip()
    if not path or not os.path.isabs(path):
        failure_counts["dotenv_path"] += 1
        return None
    nofollow = getattr(os, "O_NOFOLLOW", None)
    getuid = getattr(os, "getuid", None)
    if nofollow is None or getuid is None:
        _notice(f"{ENABLE_ENV} is off on this platform (no O_NOFOLLOW or getuid).")
        return None
    try:
        # O_NONBLOCK: a FIFO at this path must not hang open(); S_ISREG rejects it below.
        fd = os.open(path, os.O_RDONLY | nofollow | getattr(os, "O_NONBLOCK", 0))
    except OSError:
        failure_counts["dotenv_open"] += 1
        return None
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != getuid()
            or info.st_mode & 0o077
            or info.st_size > MAX_DOTENV_BYTES
        ):
            failure_counts["dotenv_checks"] += 1
            return None
        raw = os.read(fd, MAX_DOTENV_BYTES)
    except OSError:
        failure_counts["dotenv_read"] += 1
        return None
    finally:
        os.close(fd)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        failure_counts["dotenv_decode"] += 1
        return None
    value = parse_dotenv_key(text)
    return _ApiKey(value) if value else None


def _parse_value(raw: str) -> str:
    raw = raw.strip()
    if raw[:1] in ("'", '"'):
        end = raw.find(raw[0], 1)
        if end != -1:
            return raw[1:end]
    comment = raw.find(" #")
    if comment != -1:
        raw = raw[:comment]
    return raw.strip()


def parse_dotenv_key(text: str) -> Optional[str]:
    """Return the last non-empty TYPESAFE_API_KEY value; other keys' values are never read."""
    if text.startswith("\ufeff"):
        text = text[1:]
    found: Optional[str] = None
    for line in text.split("\n"):
        line = line.rstrip("\r").strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, rest = line.partition("=")
        if not sep or key.strip() != KEY_NAME:
            continue
        found = _parse_value(rest) or None
    return found


# --- redaction and candidate windows (D-9.3) ---------------------------------------

REDACTED = "[addr]"
_REDACTIONS = [
    re.compile(r"\b(?:wallet|rail):\S+", re.I),
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.(?:eth|sol)\b", re.I),
    re.compile(r"0x[0-9a-fA-F]{40,}"),
    re.compile(r"\b[0-9a-fA-F]{64}\b"),
    re.compile(r"\b[a-z]{1,83}1[02-9ac-hj-np-z]{20,}\b", re.I),
    # Base58 runs of 32+ characters with no upper bound, including runs joined by "_".
    re.compile(
        r"(?<![0-9A-Za-z_])(?=[1-9A-HJ-NP-Za-km-z_]*[1-9A-HJ-NP-Za-km-z]{32})"
        r"[1-9A-HJ-NP-Za-km-z_]+(?![0-9A-Za-z_])"
    ),
]


def redact(text: str) -> str:
    for pattern in _REDACTIONS:
        text = pattern.sub(REDACTED, text)
    return text


def candidate_windows(redacted: str, spans: Sequence[Tuple[int, int]]) -> List[str]:
    """Cut at most WINDOW_CHARS each side of each span, then shrink to word boundaries."""
    ranges: List[Tuple[int, int]] = []
    for start, end in sorted(spans):
        lo = max(0, start - WINDOW_CHARS)
        hi = min(len(redacted), end + WINDOW_CHARS)
        if lo > 0 and not redacted[lo - 1].isspace():
            while lo < start and not redacted[lo].isspace():
                lo += 1
        if hi < len(redacted) and not redacted[hi].isspace():
            while hi > end and not redacted[hi - 1].isspace():
                hi -= 1
        if ranges and lo <= ranges[-1][1]:
            ranges[-1] = (ranges[-1][0], max(ranges[-1][1], hi))
        else:
            ranges.append((lo, hi))
    return [redacted[lo:hi].strip() for lo, hi in ranges]


# --- candidates, synonyms and negation (D-9.4) -------------------------------------


@dataclass(frozen=True)
class Candidate:
    value: str
    span: Tuple[int, int]
    negated: bool


ASSET_SYNONYMS = {
    "eth": "ETH",
    "ether": "ETH",
    "ethereum": "ETH",
    "btc": "BTC",
    "bitcoin": "BTC",
    "sol": "SOL",
    "solana": "SOL",
    "usdc": "USDC",
}
CHAIN_SYNONYMS = {
    "ethereum": "ethereum",
    "base": "base",
    "arbitrum": "arbitrum",
    "arb": "arbitrum",
    "op mainnet": "optimism",
    "optimism": "optimism",
    "polygon": "polygon",
    "avalanche": "avalanche",
    "arc": "arc",
}
SCHEDULE_SYNONYMS = {
    "daily": "daily",
    "every day": "daily",
    "weekly": "weekly",
    "every week": "weekly",
    "each week": "weekly",
    "monthly": "monthly",
    "every month": "monthly",
    "one-time": "one_time",
    "one time": "one_time",
    "onetime": "one_time",
}
_NEGATION = re.compile(r"\b(?:not|no|except|excluding|without|instead\s+of|rather\s+than)\b", re.I)


def _alternation(words: Sequence[str]) -> str:
    ordered = sorted(words, key=len, reverse=True)
    return "|".join(re.escape(word).replace(r"\ ", r"\s+") for word in ordered)


def _negated(text: str, start: int) -> bool:
    """True if a negation word is among the 3 tokens before start, within the same clause."""
    clause = re.split(r"[,;]", text[:start])[-1]
    before = re.findall(r"[^\s.:!?]+", clause)[-3:]
    return bool(_NEGATION.search(" ".join(before)))


def _find(text: str, pattern: str, mapping: Mapping[str, str], group: int = 0) -> List[Candidate]:
    found = []
    for match in re.finditer(pattern, text, re.I):
        word = re.sub(r"\s+", " ", match.group(group).lower())
        value = mapping.get(word, word)
        found.append(Candidate(value, match.span(), _negated(text, match.start())))
    return found


def find_candidates(redacted: str) -> Dict[str, List[Candidate]]:
    chain_pattern = (
        rf"\bon\s+({_alternation(list(CHAIN_SYNONYMS))}|[a-z][a-z0-9-]{{0,19}})(?![\w-])"
    )
    chains = []
    for match in re.finditer(chain_pattern, redacted, re.I):
        word = re.sub(r"\s+", " ", match.group(1).lower())
        negated = _negated(redacted, match.start())
        chains.append(Candidate(CHAIN_SYNONYMS.get(word, word), match.span(1), negated))
    amounts = [
        Candidate(m.group(0).strip(), m.span(), _negated(redacted, m.start()))
        for m in re.finditer(r"\$\d+(?:\.\d+)?", redacted)
    ]
    assets = [
        c
        for c in _find(redacted, rf"\b(?:{_alternation(list(ASSET_SYNONYMS))})\b", ASSET_SYNONYMS)
        if not any(c.span[0] >= chain.span[0] and c.span[1] <= chain.span[1] for chain in chains)
    ]
    return {
        "asset": assets,
        "amount_usd": amounts,
        "chain": chains,
        "schedule": _find(
            redacted, rf"\b(?:{_alternation(list(SCHEDULE_SYNONYMS))})\b", SCHEDULE_SYNONYMS
        ),
    }


# --- transport (D-9.2) -------------------------------------------------------------


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _urllib_transport(bearer: str, body: bytes, socket_timeout: float, *extra: Any) -> Any:
    opener = build_opener(_NoRedirect, *extra)
    request = Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={"Authorization": bearer, "Content-Type": "application/json"},
    )
    with opener.open(request, timeout=socket_timeout) as response:
        if response.status != 200:
            raise TypeSafeUnavailable("unexpected_status")
        return json.loads(response.read(1_000_000).decode("utf-8"))


def call_with_deadline(
    bearer: str,
    body: bytes,
    *,
    transport: Optional[Callable[..., Any]] = None,
    deadline: float = DEADLINE_SECONDS,
) -> Any:
    """One attempt, one total deadline covering DNS through read. A late result is dropped."""
    send = transport or _urllib_transport
    box: Dict[str, Any] = {}

    def run() -> None:
        try:
            box["result"] = send(bearer, body, min(SOCKET_TIMEOUT_SECONDS, deadline))
        except BaseException as exc:  # noqa: BLE001 - classified below, never re-raised raw
            box["error"] = exc

    worker = threading.Thread(target=run, name="scout-typesafe", daemon=True)
    worker.start()
    worker.join(deadline)
    if worker.is_alive():
        raise TypeSafeUnavailable("deadline")
    if "error" in box:
        error = box["error"]
        kind = f"http_{error.code}" if isinstance(error, HTTPError) else type(error).__name__
        raise TypeSafeUnavailable(kind) from None
    return box["result"]


# --- response validation -----------------------------------------------------------


def _choice(answers: Mapping[str, Any], name: str, options: Sequence[str]) -> Optional[str]:
    """Return the chosen option only if the answer passes every validation and fill rule."""
    answer = answers.get(name)
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        return None
    choice = answer.get("choice")
    confidence = answer.get("confidence")
    probabilities = answer.get("probabilities")
    if choice not in options or not isinstance(probabilities, dict):
        return None
    if set(probabilities) != set(options):
        return None
    values = list(probabilities.values())
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return None
    if any(not 0.0 <= v <= 1.0 for v in values):
        return None
    if abs(sum(values) - 1.0) > PROBABILITY_SUM_TOLERANCE:
        return None
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        return None
    if not 0.0 <= confidence <= 1.0 or confidence < THRESHOLDS[name]:
        return None
    ranked = sorted(values, reverse=True)
    if probabilities[choice] != ranked[0] or ranked[0] - ranked[1] < FILL_MARGIN:
        return None
    return None if choice == NONE_OPTION else str(choice)


def _complete(answers: Mapping[str, Any]) -> bool:
    answer = answers.get("complete")
    if not isinstance(answer, dict) or answer.get("type") != "noul":
        return False
    value = answer.get("noul")
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and COMPLETE_THRESHOLD <= value <= 1.0
    )


def _amount(span: str) -> Optional[float]:
    try:
        amount = Decimal(span.lstrip("$"))
    except InvalidOperation:
        return None
    exponent = amount.as_tuple().exponent
    if not amount.is_finite() or not isinstance(exponent, int) or exponent < -2 or amount <= 0:
        return None
    converted = float(amount)
    if Decimal(str(converted)) != amount:
        return None
    return converted


# --- resolution (D-9.4, D-9.5) -----------------------------------------------------

_DESCRIPTIONS = {
    "asset": "The asset the user wants to buy: {option}",
    "amount_usd": "The amount in US dollars to spend per purchase: {option}",
    "chain": "The chain the user wants to buy on: {option}",
    "schedule": "How often the user wants to buy: {option}",
}


def resolve_dca_request(
    text: str,
    environ: Optional[Mapping[str, str]] = None,
    *,
    transport: Optional[Callable[..., Any]] = None,
) -> DcaParseResult:
    base = parse_dca_request(text)
    key = load_key(os.environ if environ is None else environ)
    if key is None:
        return base

    redacted = redact(text)
    candidates = find_candidates(redacted)
    values: Dict[str, Any] = {}
    sources: Dict[str, str] = {}
    options: Dict[str, List[str]] = {}
    spans: List[Tuple[int, int]] = []
    base_values = base.intent.model_dump()

    for field, found in candidates.items():
        kept = [c for c in found if not c.negated]
        distinct = list(dict.fromkeys(c.value for c in kept))
        contrastive = len(distinct) == 1 and len(kept) < len(found)
        if len(distinct) == 1 and not contrastive:
            value: Any = distinct[0]
            if field == "amount_usd":
                value = float(value.lstrip("$"))
                if not value > 0:
                    continue
            values[field] = value
            sources[field] = "regex" if base_values[field] == value else "synonym"
        elif distinct:
            options[field] = distinct + [NONE_OPTION]
            spans.extend(c.span for c in found)

    if options:
        body = json.dumps(
            {
                "model": MODEL,
                "state": "\n".join(candidate_windows(redacted, spans)),
                "questions": {
                    **{
                        field: {
                            "type": "choice",
                            "instructions": f"Which {field.replace('_', ' ')} does the user want?",
                            "criteria": {
                                option: (
                                    "None of the other options"
                                    if option == NONE_OPTION
                                    else _DESCRIPTIONS[field].format(option=option)
                                )
                                for option in opts
                            },
                        }
                        for field, opts in options.items()
                    },
                    "complete": {
                        "type": "noul",
                        "instructions": "The request is complete and unambiguous.",
                    },
                },
            }
        ).encode("utf-8")
        try:
            response = call_with_deadline(key.bearer(), body, transport=transport)
        except TypeSafeUnavailable as exc:
            failure_counts[str(exc)] += 1
            response = None
        answers = response.get("answers") if isinstance(response, dict) else None
        if isinstance(answers, dict) and _complete(answers):
            for field, opts in options.items():
                picked = _choice(answers, field, opts)
                value = _amount(picked) if (picked and field == "amount_usd") else picked
                if value is not None:
                    values[field] = value
                    sources[field] = "model_selected"
        elif response is not None:
            failure_counts["invalid_response"] += 1

    for field in ("source", "destination"):
        if base_values[field] is not None:
            values[field] = base_values[field]
            sources[field] = "regex"

    intent = DcaIntent(**values)
    order = ("asset", "amount_usd", "chain", "schedule", "source", "destination")
    missing = [name for name in order if getattr(intent, name) is None]
    if missing:
        status = "needs_clarification"
        question: Optional[str] = f"Which {missing[0].replace('_', ' ')} should I use?"
    elif any(source != "regex" for source in sources.values()):
        status = "needs_confirmation"
        read = ", ".join(
            _describe(name, getattr(intent, name)) for name in order if sources[name] != "regex"
        )
        question = f"I read {read}. Confirm or restate."
    else:
        status, question = "ready", None
    return DcaParseResult(
        intent=intent,
        status=status,
        missing=missing,
        question=question,
        field_sources={name: sources[name] for name in order if name in sources},
    )


def _describe(name: str, value: Any) -> str:
    if name == "amount_usd":
        return f"${value:g}"
    return str(value)
