"""Standalone harness for the SIGTERM-cleanup test. Not collected by pytest
(no `test_`/`_test` in the filename): it must run as a real child process so
a real SIGTERM can be delivered to it from the test.

Builds a Hedwig client against the fake server: build_hedwig_client's own
version-handshake consult (M8) already forces a real spawn, so there is a
live child to verify gets cleaned up without a separate call here. Prints
the policy file path and the child's pid on one line, then sleeps so the
test can send SIGTERM.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from scout_portfolio_manager.x402_source import HEDWIG_SERVER_PATH_ENV, build_hedwig_client


def main() -> None:
    server_path = sys.argv[1]
    pay_to = sys.argv[2]
    environ = {**os.environ, HEDWIG_SERVER_PATH_ENV: server_path}
    client = build_hedwig_client(
        environ,
        pay_to=pay_to,
        max_usd_per_call="$0.05",
        command=[sys.executable, server_path],
    )
    assert client is not None

    assert client._process is not None  # noqa: SLF001 - test harness only
    print(f"{client._policy_file} {client._process.pid}", flush=True)  # noqa: SLF001
    time.sleep(30)


if __name__ == "__main__":
    main()
