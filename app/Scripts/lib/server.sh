# Sourced by test.sh and flows.sh: the local server of docs/NATIVE.md 6.2.
#
#   start_server   seeds a template database and starts `polished serve` on a free port with
#                  POLISHED_AUTH_MODE=none, POLISHED_DEV_TOKEN, POLISHED_TEST_RESET_FROM and
#                  POLISHED_SYNC_ENABLED=false; sets SERVER_BASE and SERVER_PID
#   stop_server    stops it and removes its scratch directory

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

start_server() {
  SERVER_WORK="$(mktemp -d /tmp/polished-native.XXXXXX)"
  (cd "$ROOT" && uv run python app/Scripts/native_server.py "$SERVER_WORK" >"$SERVER_WORK/server.log" 2>&1 &)
  i=0
  while [ ! -f "$SERVER_WORK/server.json" ]; do
    i=$((i + 1))
    if [ "$i" -gt 300 ]; then
      echo "the local server did not start; its log:" >&2
      cat "$SERVER_WORK/server.log" >&2
      return 1
    fi
    sleep 0.5
  done
  SERVER_BASE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["base"])' "$SERVER_WORK/server.json")"
  SERVER_PID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["pid"])' "$SERVER_WORK/server.json")"
  echo "server: $SERVER_BASE (pid $SERVER_PID)"
}

stop_server() {
  [ -n "${SERVER_PID:-}" ] && kill "$SERVER_PID" 2>/dev/null || true
  [ -n "${SERVER_WORK:-}" ] && rm -rf "$SERVER_WORK" || true
}
