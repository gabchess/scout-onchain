#!/usr/bin/env bash
# Install the built wheel and start it over stdio with the network cut.
# Expects dist/*.whl and wheelhouse/ from the prep step. Run from the repo root.
#
# Network isolation, in order: `unshare -rn`, then `sudo unshare -n`. If neither
# works, or the namespace can still reach the internet, the job fails. It never
# runs the smoke with network.
set -euo pipefail

if [[ "${SCOUT_SMOKE_INSIDE_NETNS:-}" != "1" ]]; then
  export SCOUT_SMOKE_INSIDE_NETNS=1
  if unshare -rn true 2>/dev/null; then
    exec unshare -rn -- "$0" "$@"
  fi
  echo "unshare -rn unavailable; trying sudo unshare -n" >&2
  if sudo -n unshare -n true 2>/dev/null; then
    exec sudo -n unshare -n -- env PATH="$PATH" SCOUT_SMOKE_INSIDE_NETNS=1 "$0" "$@"
  fi
  echo "cannot isolate the network (unshare -rn and sudo unshare -n both failed)" >&2
  exit 1
fi

if python - <<'PY'
import socket
try:
    socket.create_connection(("pypi.org", 443), timeout=3).close()
except OSError:
    raise SystemExit(1)
PY
then
  echo "network is still reachable inside the namespace; refusing to run" >&2
  exit 1
fi

export UV_OFFLINE=1 PIP_NO_INDEX=1
wheel=$(ls dist/*.whl)
work=$(mktemp -d)

python -m venv "$work/venv"
"$work/venv/bin/pip" install --no-index --find-links wheelhouse "$wheel"
python -m scripts.wheel_smoke --wheel "$wheel" -- "$work/venv/bin/scout-portfolio-manager"

python -m scripts.wheel_smoke --wheel "$wheel" -- \
  uvx --offline --no-index --find-links "$PWD/wheelhouse" --from "$PWD/$wheel" \
  scout-portfolio-manager
