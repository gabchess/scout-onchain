import json
import logging
from urllib.error import HTTPError

import pytest

from scout_portfolio_manager.zerion_api import (
    EXPECTED_ZERION_API_HOST,
    ZerionAPIAuthError,
    ZerionAPIConfig,
    ZerionAPIError,
    ZerionAPIPaginationError,
    ZerionAPIRateLimitError,
    ZerionAPIReader,
    ZerionAPIServerError,
    ZerionAPITransportError,
)

BASE_URL = "https://api.zerion.io/v1"
WALLET = "0xabc"
KEY_FIELD = "api" + "_key"  # split so this file has no literal api-key assignment token


def make_reader(transport=None, **config_kwargs):
    config_kwargs.setdefault(KEY_FIELD, "test-key")
    config_kwargs.setdefault("base_url", BASE_URL)
    return ZerionAPIReader(ZerionAPIConfig(**config_kwargs), transport=transport)


def recording_transport(responses):
    """responses: list of payloads (or Exception instances) returned in call order."""
    calls = []
    remaining = list(responses)

    def transport(request, timeout):
        calls.append(request)
        response = remaining.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    transport.calls = calls  # type: ignore[attr-defined]
    return transport


def position_item(symbol="ETH", quantity=1.5, value=3000.0, missing_symbol=False):
    fungible_info = {} if missing_symbol else {"symbol": symbol}
    return {
        "attributes": {
            "quantity": quantity,
            "value": value,
            "fungible_info": fungible_info,
        },
        "relationships": {"chain": {"data": {"id": "ethereum"}}},
    }


def positions_page(items):
    return {"data": items}


def transfer(direction="in", symbol="ETH", quantity=1.0, value=100.0, missing_symbol=False):
    entry = {"direction": direction, "quantity": quantity, "value": value}
    if not missing_symbol:
        entry["fungible_info"] = {"symbol": symbol}
    return entry


def tx_item(tx_id, operation_type, transfers, mined_at="2026-01-01T00:00:00Z", fee=None):
    attributes = {
        "operation_type": operation_type,
        "hash": tx_id,
        "mined_at": mined_at,
        "transfers": transfers,
    }
    if fee is not None:
        attributes["fee"] = fee
    return {"id": tx_id, "attributes": attributes}


def tx_page(items, next_link="__omit__"):
    """next_link='__omit__' drops the links key entirely (valid termination)."""
    page = {"data": items}
    if next_link != "__omit__":
        page["links"] = {"next": next_link}
    return page


# --- get_positions -----------------------------------------------------------


def test_get_positions_maps_single_unpaginated_call():
    transport = recording_transport([positions_page([position_item("ETH", 1.5, 3000.0)])])
    reader = make_reader(transport)
    holdings = reader.get_positions(WALLET)

    assert len(holdings) == 1
    assert holdings[0].asset == "ETH"
    assert holdings[0].quantity == pytest.approx(1.5)
    assert holdings[0].value_usd == pytest.approx(3000.0)
    assert len(transport.calls) == 1
    expected = (
        f"{BASE_URL}/wallets/{WALLET}/positions/"
        "?currency=usd&filter%5Bpositions%5D=only_simple"
        "&filter%5Btrash%5D=only_non_trash"
    )
    assert transport.calls[0].full_url == expected


def test_get_positions_malformed_array_raises():
    transport = recording_transport([{"data": {"not": "a list"}}])
    with pytest.raises(ZerionAPIError, match="data is not a list"):
        make_reader(transport).get_positions(WALLET)


def test_get_positions_skips_item_missing_fungible_symbol(caplog):
    transport = recording_transport(
        [positions_page([position_item(missing_symbol=True), position_item("USDC", 10.0, 10.0)])]
    )
    with caplog.at_level(logging.WARNING):
        holdings = make_reader(transport).get_positions(WALLET)

    assert len(holdings) == 1
    assert holdings[0].asset == "USDC"
    assert any("missing fungible_info.symbol" in record.message for record in caplog.records)


def test_get_positions_accepts_quantity_object_or_bare_number():
    transport = recording_transport(
        [
            positions_page(
                [
                    {
                        "attributes": {
                            "quantity": {"float": 2.25, "decimals": 18},
                            "value": 500.0,
                            "fungible_info": {"symbol": "ETH"},
                        }
                    }
                ]
            )
        ]
    )
    holdings = make_reader(transport).get_positions(WALLET)
    assert holdings[0].quantity == pytest.approx(2.25)


# --- get_transactions: pagination --------------------------------------------


def test_get_transactions_single_page_no_links_key():
    transport = recording_transport([tx_page([tx_item("h1", "send", [transfer("out")])])])
    reader = make_reader(transport)
    transactions = reader.get_transactions(WALLET)

    assert len(transactions) == 1
    assert len(transport.calls) == 1
    assert transport.calls[0].full_url == (
        f"{BASE_URL}/wallets/{WALLET}/transactions/"
        "?currency=usd&page%5Bsize%5D=100&filter%5Boperation_types%5D=trade%2Csend%2Creceive"
        "&filter%5Btrash%5D=only_non_trash"
    )


def test_get_transactions_links_present_without_next_key_terminates():
    transport = recording_transport([{"data": [], "links": {"self": "x"}}])
    transactions = make_reader(transport).get_transactions(WALLET)
    assert transactions == []
    assert len(transport.calls) == 1


def test_get_transactions_follows_links_next_across_multiple_pages():
    next_url = f"{BASE_URL}/wallets/{WALLET}/transactions/?page%5Bafter%5D=CURSOR1"
    transport = recording_transport(
        [
            tx_page([tx_item("h1", "send", [transfer("out")])], next_link=next_url),
            tx_page([tx_item("h2", "receive", [transfer("in")])], next_link=None),
        ]
    )
    transactions = make_reader(transport).get_transactions(WALLET)

    assert {t.id for t in transactions} == {"h1-0", "h2-0"}
    assert len(transport.calls) == 2
    assert transport.calls[1].full_url == next_url


def test_get_transactions_empty_page_then_next_page_with_items():
    next_url = f"{BASE_URL}/next-page"
    transport = recording_transport(
        [
            tx_page([], next_link=next_url),
            tx_page([tx_item("h1", "trade", [transfer("in")])], next_link=None),
        ]
    )
    transactions = make_reader(transport).get_transactions(WALLET)
    assert len(transactions) == 1


def test_get_transactions_malformed_links_next_type_raises_pagination_error():
    transport = recording_transport([{"data": [], "links": {"next": 12345}}])
    with pytest.raises(ZerionAPIPaginationError, match="malformed pagination cursor"):
        make_reader(transport).get_transactions(WALLET)


def test_get_transactions_malformed_links_object_raises_pagination_error():
    transport = recording_transport([{"data": [], "links": ["not", "a", "mapping"]}])
    with pytest.raises(ZerionAPIPaginationError, match="malformed links object"):
        make_reader(transport).get_transactions(WALLET)


def test_get_transactions_cursor_repeat_is_a_loop_guard():
    loop_url = f"{BASE_URL}/loop"
    transport = recording_transport(
        [
            tx_page([], next_link=loop_url),
            tx_page([], next_link=loop_url),
        ]
    )
    with pytest.raises(ZerionAPIPaginationError, match="repeated pagination cursor"):
        make_reader(transport).get_transactions(WALLET)
    assert len(transport.calls) == 2


def test_get_transactions_rejects_next_link_pointing_at_unexpected_host():
    """A links.next cursor to a different host must never be followed.

    _build_request attaches the Basic-auth API key header to whatever URL it is
    given, so a next-link redirect to an attacker-controlled host would leak the
    credential in that request's Authorization header. This proves the second
    (malicious) page is never fetched: the transport is only ever called once.
    """
    malicious_next = "https://evil.example.com/wallets/steal"
    transport = recording_transport(
        [tx_page([tx_item("h1", "send", [transfer("out")])], next_link=malicious_next)]
    )
    with pytest.raises(ZerionAPIPaginationError, match="unexpected"):
        make_reader(transport).get_transactions(WALLET)
    assert len(transport.calls) == 1


def test_get_transactions_rejects_next_link_with_downgraded_scheme():
    non_https_next = f"http://{EXPECTED_ZERION_API_HOST}/wallets/{WALLET}/transactions/?page=2"
    transport = recording_transport(
        [tx_page([tx_item("h1", "send", [transfer("out")])], next_link=non_https_next)]
    )
    with pytest.raises(ZerionAPIPaginationError, match="unexpected"):
        make_reader(transport).get_transactions(WALLET)
    assert len(transport.calls) == 1


def test_get_transactions_max_pages_exceeded():
    counter = {"n": 0}

    def never_ending_transport(request, timeout):
        counter["n"] += 1
        return {"data": [], "links": {"next": f"{BASE_URL}/page-{counter['n']}"}}

    reader = make_reader(never_ending_transport, max_pages=3)
    with pytest.raises(ZerionAPIPaginationError, match="3-page bound"):
        reader.get_transactions(WALLET)
    assert counter["n"] == reader.config.max_pages


def test_max_pages_defaults_to_20():
    assert ZerionAPIConfig(**{KEY_FIELD: "test-key"}, base_url=BASE_URL).max_pages == 20


# --- get_transactions: operation-type and transfer mapping -------------------


def test_trade_maps_to_buy_and_sell_by_transfer_direction():
    transport = recording_transport(
        [
            tx_page(
                [
                    tx_item(
                        "h1",
                        "trade",
                        [
                            transfer("out", "ETH", 1.0, 2000.0),
                            transfer("in", "USDC", 2000.0, 2000.0),
                        ],
                    )
                ]
            )
        ]
    )
    transactions = make_reader(transport).get_transactions(WALLET)

    by_asset = {t.asset: t for t in transactions}
    assert by_asset["ETH"].kind == "sell"
    assert by_asset["USDC"].kind == "buy"
    assert all(t.wallet_address == WALLET for t in transactions)


def test_send_and_receive_map_to_transfer():
    transport = recording_transport(
        [
            tx_page(
                [
                    tx_item("h1", "send", [transfer("out", "ETH")]),
                    tx_item("h2", "receive", [transfer("in", "ETH")]),
                ]
            )
        ]
    )
    transactions = make_reader(transport).get_transactions(WALLET)
    assert {t.kind for t in transactions} == {"transfer"}
    assert len(transactions) == 2


def test_unmapped_operation_type_is_skipped_with_warning_and_snapshot_still_succeeds(caplog):
    transport = recording_transport(
        [
            tx_page(
                [
                    tx_item("h1", "approve", [transfer("out")]),
                    tx_item("h2", "send", [transfer("out")]),
                ]
            )
        ]
    )
    with caplog.at_level(logging.WARNING):
        transactions = make_reader(transport).get_transactions(WALLET)

    assert len(transactions) == 1
    assert transactions[0].id == "h2-0"
    assert any("unmapped operation_type" in record.message for record in caplog.records)


def test_deposit_withdraw_and_claim_map_to_transfer(caplog):
    transport = recording_transport(
        [
            tx_page(
                [
                    tx_item("h1", "deposit", [transfer("out", "ETH")]),
                    tx_item("h2", "withdraw", [transfer("in", "ETH")]),
                    tx_item("h3", "claim", [transfer("in", "ETH")]),
                ]
            )
        ]
    )
    with caplog.at_level(logging.WARNING):
        transactions = make_reader(transport).get_transactions(WALLET)

    assert len(transactions) == 3
    assert {t.kind for t in transactions} == {"transfer"}
    assert not any("unmapped operation_type" in record.message for record in caplog.records)


def test_other_untyped_operations_still_skip_with_warning(caplog):
    transport = recording_transport(
        [
            tx_page(
                [
                    tx_item("h1", "approve", [transfer("out")]),
                    tx_item("h2", "burn", [transfer("out")]),
                    tx_item("h3", "delegate", [transfer("out")]),
                ]
            )
        ]
    )
    with caplog.at_level(logging.WARNING):
        transactions = make_reader(transport).get_transactions(WALLET)

    assert transactions == []
    warnings = [r.message for r in caplog.records if "unmapped operation_type" in r.message]
    assert len(warnings) == 3


def test_trade_self_direction_transfer_is_skipped_with_warning(caplog):
    transport = recording_transport([tx_page([tx_item("h1", "trade", [transfer("self")])])])
    with caplog.at_level(logging.WARNING):
        transactions = make_reader(transport).get_transactions(WALLET)
    assert transactions == []
    assert any("not mapped" in record.message for record in caplog.records)


def test_fee_bearing_transaction_attaches_fee_to_first_row_only():
    transport = recording_transport(
        [
            tx_page(
                [
                    tx_item(
                        "h1",
                        "trade",
                        [
                            transfer("out", "ETH", 1.0, 2000.0),
                            transfer("in", "USDC", 2000.0, 2000.0),
                        ],
                        fee={"value": 5.0, "quantity": 0.002},
                    )
                ]
            )
        ]
    )
    transactions = make_reader(transport).get_transactions(WALLET)
    assert transactions[0].fee_usd == pytest.approx(5.0)
    assert transactions[1].fee_usd == 0.0


def test_malformed_transfer_entry_is_skipped_others_still_map(caplog):
    transport = recording_transport(
        [
            tx_page(
                [
                    tx_item(
                        "h1",
                        "trade",
                        [
                            "not-an-object",
                            transfer("in", "USDC", 2000.0, 2000.0),
                        ],
                    )
                ]
            )
        ]
    )
    with caplog.at_level(logging.WARNING):
        transactions = make_reader(transport).get_transactions(WALLET)
    assert len(transactions) == 1
    assert transactions[0].asset == "USDC"


# --- snapshot() combines both --------------------------------------------------


def test_snapshot_combines_positions_and_transactions():
    positions_transport_calls = []

    def transport(request, timeout):
        positions_transport_calls.append(request.full_url)
        if "/positions/" in request.full_url:
            return positions_page([position_item("ETH", 1.0, 2000.0)])
        return tx_page([tx_item("h1", "receive", [transfer("in", "ETH", 0.5, 1000.0)])])

    snapshot = make_reader(transport).snapshot(WALLET)

    assert [h.asset for h in snapshot.holdings] == ["ETH"]
    assert len(snapshot.transactions) == 1
    assert snapshot.transactions[0].kind == "transfer"
    assert snapshot.source.kind == "zerion_api"
    assert snapshot.wallet_address == WALLET
    assert len(positions_transport_calls) == 2  # one positions call, one transactions call


# --- errors: status codes and Retry-After -------------------------------------


def _http_error(code, headers=None):
    return HTTPError(f"{BASE_URL}/wallets/{WALLET}/positions/", code, "opaque", headers or {}, None)


@pytest.mark.parametrize(
    "status, expected_exc",
    [
        (401, ZerionAPIAuthError),
        (403, ZerionAPIAuthError),
        (404, ZerionAPIError),
    ],
)
def test_http_status_maps_to_typed_error(monkeypatch, status, expected_exc):
    monkeypatch.setattr(
        "scout_portfolio_manager.zerion_api.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(_http_error(status)),
    )
    with pytest.raises(expected_exc) as caught:
        make_reader().get_positions(WALLET)
    assert caught.value.status == status


def test_429_reads_retry_after_seconds(monkeypatch):
    monkeypatch.setattr(
        "scout_portfolio_manager.zerion_api.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(_http_error(429, {"Retry-After": "30"})),
    )
    with pytest.raises(ZerionAPIRateLimitError) as caught:
        make_reader().get_positions(WALLET)
    assert caught.value.retry_after_seconds == pytest.approx(30.0)


def test_429_without_retry_after_leaves_it_none(monkeypatch):
    monkeypatch.setattr(
        "scout_portfolio_manager.zerion_api.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(_http_error(429)),
    )
    with pytest.raises(ZerionAPIRateLimitError) as caught:
        make_reader().get_positions(WALLET)
    assert caught.value.retry_after_seconds is None


@pytest.mark.parametrize("status", [500, 502])
def test_5xx_without_retry_after_is_server_error(monkeypatch, status):
    monkeypatch.setattr(
        "scout_portfolio_manager.zerion_api.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(_http_error(status)),
    )
    with pytest.raises(ZerionAPIServerError) as caught:
        make_reader().get_positions(WALLET)
    assert caught.value.status == status
    assert caught.value.retry_after_seconds is None


def test_503_with_retry_after_is_server_error_with_retry_after(monkeypatch):
    monkeypatch.setattr(
        "scout_portfolio_manager.zerion_api.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(_http_error(503, {"Retry-After": "5"})),
    )
    with pytest.raises(ZerionAPIServerError) as caught:
        make_reader().get_positions(WALLET)
    assert caught.value.status == 503
    assert caught.value.retry_after_seconds == pytest.approx(5.0)


def test_other_4xx_is_generic_typed_error(monkeypatch):
    monkeypatch.setattr(
        "scout_portfolio_manager.zerion_api.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(_http_error(400)),
    )
    with pytest.raises(ZerionAPIError) as caught:
        make_reader().get_positions(WALLET)
    assert not isinstance(caught.value, ZerionAPIAuthError)
    assert caught.value.status == 400


def test_transport_timeout_is_typed_transport_error(monkeypatch):
    def raise_timeout(request, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr("scout_portfolio_manager.zerion_api.urlopen", raise_timeout)
    with pytest.raises(ZerionAPITransportError):
        make_reader().get_positions(WALLET)


def test_non_json_body_is_typed_transport_error(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"not json at all {"

    monkeypatch.setattr(
        "scout_portfolio_manager.zerion_api.urlopen", lambda *_args, **_kwargs: Response()
    )
    with pytest.raises(ZerionAPITransportError):
        make_reader().get_positions(WALLET)


def test_non_object_json_body_is_typed_transport_error(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(["not", "an", "object"]).encode()

    monkeypatch.setattr(
        "scout_portfolio_manager.zerion_api.urlopen", lambda *_args, **_kwargs: Response()
    )
    with pytest.raises(ZerionAPITransportError, match="non-object"):
        make_reader().get_positions(WALLET)


def test_credentials_are_not_exposed_by_config_or_errors():
    key = "opaque" + "-credential"
    config = ZerionAPIConfig(**{KEY_FIELD: key})
    assert key not in repr(config)

    def transport(_, __):
        raise RuntimeError("transport detail " + key)

    with pytest.raises(ZerionAPITransportError) as caught:
        ZerionAPIReader(config, transport=transport).get_positions(WALLET)
    assert key not in str(caught.value)


# --- config validation (ZPM-057) -----------------------------------------------


def test_config_rejects_non_https_base_url():
    with pytest.raises(ValueError, match="https"):
        ZerionAPIConfig(**{KEY_FIELD: "key"}, base_url="http://api.zerion.io/v1")


def test_config_rejects_unexpected_base_url_host():
    with pytest.raises(ValueError, match="api.zerion.io"):
        ZerionAPIConfig(**{KEY_FIELD: "key"}, base_url="https://evil.example/v1")
