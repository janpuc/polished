"""The app under test: a template database seeded once, and a server on a fresh copy of it for
every flow, so no flow sees what another one did."""

import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
STARTUP_TIMEOUT_S = 30


def project_python() -> list[str]:
    """The command that runs Python inside the project's environment."""
    venv = REPO / ".venv" / "bin" / "python"
    if venv.exists():
        return [str(venv)]
    uv = shutil.which("uv")
    if uv is None:
        sys.exit("run_flows.py needs the project's .venv or uv on PATH to start the app")
    return [uv, "run", "--project", str(REPO), "python"]


def clean_env() -> dict[str, str]:
    """The environment without any POLISHED_* variable of the developer's shell."""
    return {k: v for k, v in os.environ.items() if not k.startswith("POLISHED_")}


def seed_template(directory: Path) -> Path:
    """The seeded database every flow starts from."""
    path = directory / "template.db"
    subprocess.run(
        [*project_python(), str(REPO / "tests/e2e/flows/seed.py"), str(path)],
        cwd=REPO,
        env=clean_env(),
        check=True,
        capture_output=True,
    )
    return path


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Server:
    """`with Server(template) as server:` runs the app on a copy of the template database with
    sign-in off; `server.base` is its address."""

    def __init__(self, template: Path):
        self.template = template
        self.directory = Path(tempfile.mkdtemp(prefix="polished-flow-"))
        self.process: subprocess.Popen | None = None
        self.base = ""

    def __enter__(self) -> "Server":
        db = self.directory / "polished.db"
        source = sqlite3.connect(self.template)
        target = sqlite3.connect(db)
        source.backup(target)
        source.close()
        target.close()
        port = free_port()
        self.base = f"http://127.0.0.1:{port}"
        env = clean_env() | {
            "POLISHED_DB_PATH": str(db),
            "POLISHED_AUTH_MODE": "none",
            "POLISHED_PUBLIC_URL": self.base,
            "POLISHED_PORT": str(port),
            "POLISHED_SYNC_ENABLED": "false",
            "POLISHED_RELEASE_SHEET_URL": "",
        }
        self.process = subprocess.Popen(
            [*project_python(), "-m", "polished", "serve"],
            cwd=REPO,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self._wait_until_up()
        return self

    def _wait_until_up(self) -> None:
        deadline = time.monotonic() + STARTUP_TIMEOUT_S
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                error = self.process.stderr.read().decode(errors="replace")[-800:]
                raise RuntimeError(f"the app exited while starting: {error}")
            try:
                with urllib.request.urlopen(f"{self.base}/healthz", timeout=1):
                    return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError(f"the app did not answer on {self.base} in {STARTUP_TIMEOUT_S}s")

    def __exit__(self, *exc) -> None:
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            if self.process.stderr:
                self.process.stderr.close()
        shutil.rmtree(self.directory, ignore_errors=True)
