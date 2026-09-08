"""MCP stdio server for Scout's portfolio host.

Requires the optional dependency: pip install -e '.[mcp]'

No trade, signing, or submission tool is registered. Network access belongs to an
explicitly configured Zerion source. API-key mode reads analytics. x402 mode pays for
analytics through a separate wallet and a bounded process budget.
"""

from __future__ import annotations

import json
import os
from typing import Mapping

from .host import ReadOnlyHost, default_host
from .zerion_api import ZerionConfigError, reader_from_env


def build_host(environ: Mapping[str, str] | None = None) -> ReadOnlyHost:
    """Pick the source from the environment.

    A complete API-key or x402 configuration selects Zerion. A partial or conflicting
    configuration raises ZerionConfigError. Otherwise use ZPM_FIXTURE_PATH, then the
    packaged fixture.
    """
    env = os.environ if environ is None else environ
    reader = reader_from_env(env)
    if reader is not None:
        return ReadOnlyHost(reader)
    fixture = env.get("ZPM_FIXTURE_PATH")
    if fixture:
        return ReadOnlyHost(fixture)
    return default_host()


def _require_mcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised via import error path in tests
        raise SystemExit("MCP extra is not installed. Run: pip install -e '.[mcp]'") from exc
    return FastMCP


def create_server(host: ReadOnlyHost | None = None):
    FastMCP = _require_mcp()
    host = host or build_host()
    server = FastMCP(
        "scout-portfolio",
        instructions=(
            "Act as an onchain portfolio manager. Route each request to the smallest useful "
            "combination of portfolio, PnL, DCA proposal, analysis, or local alert tools. "
            "Market indicators use synthetic history. DCA ends at approval-required preview. "
            "There is no observed-wallet signer, trade execution, or submission tool."
        ),
    )

    @server.tool(name="get_portfolio_snapshot")
    def get_portfolio_snapshot() -> str:
        """Observe the current portfolio snapshot from the configured read-only
        source (fixture-backed by default, or a Zerion-backed read when one
        complete authorization mode is configured). Read-only.
        """
        return json.dumps(host.get_portfolio_snapshot(), indent=2, default=str)

    @server.tool(name="get_pnl")
    def get_pnl(asset: str | None = None) -> str:
        """Calculate explainable USD PnL. Optional asset filter. Read-only."""
        return json.dumps(host.get_pnl(asset=asset), indent=2, default=str)

    @server.tool(name="parse_dca_request")
    def parse_dca_request(text: str) -> str:
        """Parse a DCA request. Asks for missing fields instead of inferring them."""
        return json.dumps(host.parse_dca_request(text), indent=2, default=str)

    @server.tool(name="preview_dca")
    def preview_dca(
        text: str,
        expected_output: float | None = None,
        fees_usd: float | None = None,
        slippage_pct: float | None = None,
        quote_expiry: str | None = None,
        max_fee_usd: float | None = None,
    ) -> str:
        """Build an approval-required DCA proposal. Optional quote fields come from
        the caller; Scout does not fetch a swap quote or execute a trade.
        """
        return json.dumps(
            host.preview_dca(
                text,
                expected_output=expected_output,
                fees_usd=fees_usd,
                slippage_pct=slippage_pct,
                quote_expiry=quote_expiry,
                max_fee_usd=max_fee_usd,
            ),
            indent=2,
            default=str,
        )

    @server.tool(name="analyze_asset")
    def analyze_asset(asset: str) -> str:
        """Heuristic SMA/EMA/RSI/range/drawdown indicators for one asset. Read-only."""
        return json.dumps(host.analyze_asset(asset), indent=2, default=str)

    @server.tool(name="dca_windows")
    def dca_windows(
        asset: str,
        risk_profile: str = "balanced",
        amount_usd: float | None = None,
    ) -> str:
        """Classify the current window for a DCA buy. Proposes only; not financial advice."""
        return json.dumps(
            host.dca_windows(asset, risk_profile=risk_profile, amount_usd=amount_usd),
            indent=2,
            default=str,
        )

    @server.tool(name="set_alert")
    def set_alert(asset: str, kind: str, threshold: float) -> str:
        """Store a user-defined alert rule locally. No daemon, no cron, no push."""
        return json.dumps(host.set_alert(asset, kind, threshold), indent=2, default=str)

    @server.tool(name="check_alerts")
    def check_alerts(asset: str | None = None) -> str:
        """Evaluate stored alert rules on demand. Never runs in the background."""
        return json.dumps(host.check_alerts(asset=asset), indent=2, default=str)

    return server


def main() -> None:
    try:
        server = create_server()
    except ZerionConfigError as exc:
        raise SystemExit(f"zpm-mcp: {exc}") from None
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
