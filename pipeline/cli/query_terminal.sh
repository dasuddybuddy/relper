#!/bin/sh
# Opens a fresh Terminal window running the interactive query CLI.
ROOT="$(cd "$(dirname "$0")"/../.. && pwd)"
osascript <<EOF
tell application "Terminal"
    activate
    do script "cd \"$ROOT\" && ./venv/bin/python pipeline/cli/query_cli.py"
end tell
EOF