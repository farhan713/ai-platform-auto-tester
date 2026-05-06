#!/usr/bin/env bash
# Launch the Skylar IQ QA web UI.
# Opens http://127.0.0.1:5050/ in your default browser.
set -e
cd "$(dirname "$0")"
exec python3 -m app.server "$@"
