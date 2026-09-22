"""Harness for the SIGTERM-during-an-in-flight-call test. Not collected by
pytest (no `test_`/`_test` in the filename): it must run as a real child
process so a real SIGTERM can be delivered to it mid-call.

Prints "ready" and then, in the SAME (main) thread, calls
build_hedwig_client against the `hang` fake server on a long deadline: that
call installs the SIGTERM handler itself before it forces a real spawn and
version-handshake consult, so by the time the parent sends SIGTERM this
process is genuinely blocked inside that in-flight call, in the one thread
signal handlers actually run in.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from scout_portfolio_manager.x402_source import HEDWIG_SERVER_PATH_ENV, build_hedwig_client


def main() -> None:
    fake_server = sys.argv[1]
    pay_to = sys.argv[2]
    environ = {**os.environ, HEDWIG_SERVER_PATH_ENV: fake_server}

    print("ready", flush=True)
    try:
        build_hedwig_client(
            environ,
            pay_to=pay_to,
            max_usd_per_call="$0.05",
            command=[sys.executable, fake_server, "hang"],
            call_deadline=10.0,
        )
    except Exception:
        pass  # the point of this harness is the SIGTERM, not this outcome


if __name__ == "__main__":
    main()
