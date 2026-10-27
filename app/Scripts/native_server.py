"""The server the native UI flows talk to: a seeded template database, and `polished serve` on a free
port on a copy of it with sign-in off, a development token, the reset route and no sync
(docs/NATIVE.md 6.2). Writes `server.json` ({"base", "token", "pid" of this script, which stops the server on SIGTERM}) into WORK once it answers, then runs
until it is terminated.

    uv run python app/Scripts/native_server.py WORK
"""

import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "dev"


def main(work: Path) -> int:
    work.mkdir(parents=True, exist_ok=True)
    template = work / "template.db"
    live = work / "polished.db"
    subprocess.run(
        [sys.executable, str(ROOT / "app/Scripts/seed_native.py"), str(template)],
        cwd=ROOT,
        env={k: v for k, v in os.environ.items() if not k.startswith("POLISHED_")},
        check=True,
        stdout=subprocess.DEVNULL,
    )
    source, target = sqlite3.connect(template), sqlite3.connect(live)
    source.backup(target)
    source.close()
    target.close()

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = {k: v for k, v in os.environ.items() if not k.startswith("POLISHED_")} | {
        "POLISHED_DB_PATH": str(live),
        "POLISHED_AUTH_MODE": "none",
        "POLISHED_PUBLIC_URL": base,
        "POLISHED_PORT": str(port),
        "POLISHED_DEV_TOKEN": TOKEN,
        "POLISHED_TEST_RESET_FROM": str(template),
        "POLISHED_SYNC_ENABLED": "false",
        "POLISHED_RELEASE_SHEET_URL": "",
    }
    server = subprocess.Popen(
        [sys.executable, "-m", "polished", "serve"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL
    )

    def stop(*_):
        server.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    for _ in range(150):
        if server.poll() is not None:
            print("the server exited at startup", file=sys.stderr)
            return 1
        try:
            request = urllib.request.Request(
                f"{base}/api/v1/me", headers={"Authorization": f"Bearer {TOKEN}"}
            )
            urllib.request.urlopen(request, timeout=1)
            break
        except OSError:
            time.sleep(0.2)
    else:
        server.terminate()
        print("the server did not come up", file=sys.stderr)
        return 1
    (work / "server.json").write_text(
        json.dumps({"base": base, "pid": os.getpid(), "token": TOKEN})
    )
    server.wait()
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
