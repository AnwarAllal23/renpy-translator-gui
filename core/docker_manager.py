"""Ren'Py Translator - Auto-manage a local LibreTranslate Docker container.

Docker is never required to use this app (Argos Translate covers the fully
offline case) - this module only kicks in once the user has configured a
localhost/127.0.0.1 LibreTranslate endpoint. Docker Desktop must already be
installed and running; from there this handles creating/starting the
`renpy_translator_libretranslate` container and waiting for the API to
answer, so the user doesn't have to run `docker run` by hand every session.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Callable
from urllib.parse import urlparse

import requests

CONTAINER_NAME = "renpy_translator_libretranslate"
IMAGE = "libretranslate/libretranslate"

# Every language this app lets you pick as source/target, loaded once so
# switching language pairs later never requires recreating the container.
DEFAULT_LANGS = "en,fr,es,de,it,pt,ja,zh,ar,ru"


class DockerError(RuntimeError):
    pass


def is_docker_installed() -> bool:
    return shutil.which("docker") is not None


def _creationflags() -> int:
    # This app is packaged windowed (console=False) - without this, spawning
    # the docker CLI would flash a console window on Windows.
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _run(args: list[str], timeout: float | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=_creationflags(),
    )


def _base_url(endpoint: str) -> str:
    u = (endpoint or "").strip().rstrip("/")
    if u.endswith("/translate"):
        u = u[: -len("/translate")]
    return u


def _port_of(endpoint: str) -> int:
    u = endpoint if "://" in endpoint else f"//{endpoint}"
    return urlparse(u, scheme="http").port or 5000


def is_reachable(endpoint: str, timeout: float = 3.0) -> bool:
    try:
        r = requests.get(f"{_base_url(endpoint)}/languages", timeout=timeout)
        return r.status_code == 200
    except requests.RequestException:
        return False


def _daemon_running() -> bool:
    try:
        r = _run(["docker", "info"], timeout=15)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return r.returncode == 0


def _container_status(name: str) -> str | None:
    """'running', 'exited' (or similar) - or None if the container doesn't exist."""
    try:
        r = _run(["docker", "inspect", "-f", "{{.State.Status}}", name], timeout=15)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def _explain_run_failure(stderr: str, port: int) -> str:
    text = (stderr or "").strip()
    lowered = text.lower()
    if "port is already allocated" in lowered or "address already in use" in lowered:
        return (
            f"Port {port} is already in use by something else, so the LibreTranslate "
            "Docker container couldn't start. Free up that port (or stop whatever is "
            "using it) and try again."
        )
    if "cannot connect to the docker daemon" in lowered:
        return "Docker Desktop doesn't seem to be running. Start it, wait for it to be fully up, then try again."
    return f"Failed to start the LibreTranslate Docker container:\n{text[:500]}"


def ensure_running(
    endpoint: str,
    langs: str = DEFAULT_LANGS,
    log_cb: Callable[[str], None] | None = None,
    ready_timeout_s: int = 900,
    pull_timeout_s: int = 1800,
) -> None:
    """Make sure a local LibreTranslate server answers at `endpoint`.

    Creates/starts the `renpy_translator_libretranslate` Docker container if
    needed, then blocks until the API responds or `ready_timeout_s` elapses.
    Meant to run off the UI thread. Raises DockerError on failure.
    """
    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    if is_reachable(endpoint):
        return

    if not is_docker_installed():
        raise DockerError("Docker is not installed ('docker' command not found).")

    log("🔎 Local LibreTranslate isn't answering yet — checking Docker…")

    if not _daemon_running():
        raise DockerError(
            "Docker is installed but Docker Desktop doesn't seem to be running. "
            "Start Docker Desktop, wait until it's fully up, then try again."
        )

    port = _port_of(endpoint)
    status = _container_status(CONTAINER_NAME)

    if status is None:
        log(f"🐳 Creating the LibreTranslate container (image {IMAGE})…")
        log("⏳ First run also downloads the image - this can take several minutes depending on your connection.")
        try:
            r = _run(
                [
                    "docker", "run", "-d",
                    "--name", CONTAINER_NAME,
                    "-p", f"{port}:5000",
                    IMAGE,
                    "--load-only", langs,
                    "--disable-web-ui",
                ],
                timeout=pull_timeout_s,
            )
        except subprocess.TimeoutExpired:
            raise DockerError(
                f"Downloading the LibreTranslate Docker image took more than {pull_timeout_s}s "
                "and was aborted. Check your internet connection, or run the docker command "
                "manually from the Local setup guide."
            )
        if r.returncode != 0:
            raise DockerError(_explain_run_failure(r.stderr, port))
    elif status != "running":
        log("🐳 Restarting the existing LibreTranslate container…")
        r = _run(["docker", "start", CONTAINER_NAME], timeout=30)
        if r.returncode != 0:
            raise DockerError(f"Could not restart the existing Docker container: {r.stderr.strip()[:400]}")
    else:
        log("🐳 The LibreTranslate container is already running — waiting for the server to answer…")

    log("⏳ Waiting for LibreTranslate to finish starting (loading language models)…")
    deadline = time.monotonic() + ready_timeout_s
    next_heartbeat = time.monotonic() + 15

    while time.monotonic() < deadline:
        if is_reachable(endpoint):
            log("✅ Local LibreTranslate is ready.")
            return
        now = time.monotonic()
        if now >= next_heartbeat:
            log("⏳ Still waiting for LibreTranslate…")
            next_heartbeat = now + 15
        time.sleep(2)

    raise DockerError(
        "LibreTranslate didn't respond in time after starting the Docker container. "
        f"Check its logs with: docker logs {CONTAINER_NAME}"
    )
