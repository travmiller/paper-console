#!/usr/bin/env python3
"""Render settings UI screenshots for debug verification.

This script starts backend + frontend (unless --reuse-servers is set),
runs browser automation captures, and refreshes the output folder.
"""

from __future__ import annotations

import argparse
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib import request
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_SCRIPT = PROJECT_ROOT / "testing" / "render_settings_ui_capture.mjs"


def _wait_http_ready(url: str, timeout_sec: int = 90) -> None:
    deadline = time.time() + timeout_sec
    last_error = None
    while time.time() < deadline:
        try:
            with request.urlopen(url, timeout=3) as resp:
                status = getattr(resp, "status", 200)
                if 200 <= status < 500:
                    return
        except Exception as exc:  # pragma: no cover - runtime helper
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}. Last error: {last_error}")


def _spawn(
    cmd: list[str],
    cwd: Path,
    stdout,
    stderr,
) -> subprocess.Popen:
    kwargs: dict = {
        "cwd": str(cwd),
        "stdout": stdout,
        "stderr": stderr,
    }
    if hasattr(os, "setsid"):
        kwargs["preexec_fn"] = os.setsid
    return subprocess.Popen(cmd, **kwargs)


def _stop_process(proc: subprocess.Popen | None) -> None:
    if not proc or proc.poll() is not None:
        return

    if hasattr(os, "killpg"):
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
    else:
        try:
            proc.terminate()
        except Exception:
            pass

    try:
        proc.wait(timeout=8)
        return
    except subprocess.TimeoutExpired:
        pass

    if hasattr(os, "killpg"):
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            return
        except Exception:
            pass

    try:
        proc.kill()
    except Exception:
        pass


def _parse_port(url: str, default_port: int) -> int:
    parsed = urlparse(url)
    return parsed.port or default_port


def _python_exec() -> str:
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render settings UI screenshot gallery using Playwright."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("testing/ui_gallery"),
        help="Output folder to refresh with screenshots.",
    )
    parser.add_argument(
        "--frontend-url",
        default="http://127.0.0.1:5173",
        help="Frontend base URL for captures.",
    )
    parser.add_argument(
        "--backend-url",
        default="http://127.0.0.1:8000",
        help="Backend URL used by Vite proxy.",
    )
    parser.add_argument(
        "--reuse-servers",
        action="store_true",
        help="Use existing running backend/frontend instead of starting subprocesses.",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Run browser with UI (default headless).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=90,
        help="Startup wait timeout in seconds.",
    )
    parser.add_argument(
        "--admin-token",
        default=os.getenv("PC1_ADMIN_TOKEN", ""),
        help="Optional admin token for privileged API calls.",
    )
    parser.add_argument(
        "--skip-module-seeding",
        action="store_true",
        help="Skip temporary module creation for module editor captures.",
    )
    parser.add_argument(
        "--install-browser",
        action="store_true",
        help="Install Playwright Chromium before running captures.",
    )
    parser.add_argument(
        "--show-server-logs",
        action="store_true",
        help="Pipe backend/frontend logs to this terminal.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not CAPTURE_SCRIPT.exists():
        print(
            f"[settings-ui] capture script missing: {CAPTURE_SCRIPT}",
            file=sys.stderr,
        )
        return 2

    backend_proc = None
    frontend_proc = None

    log_stream = None if args.show_server_logs else subprocess.DEVNULL

    try:
        if not args.reuse_servers:
            python_exec = _python_exec()
            backend_port = _parse_port(args.backend_url, 8000)
            frontend_port = _parse_port(args.frontend_url, 5173)

            backend_cmd = [
                python_exec,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(backend_port),
            ]
            frontend_cmd = [
                "npm",
                "--prefix",
                "web",
                "run",
                "dev",
                "--",
                "--host",
                "127.0.0.1",
                "--port",
                str(frontend_port),
                "--strictPort",
            ]

            print(f"[settings-ui] starting backend: {' '.join(backend_cmd)}")
            backend_proc = _spawn(
                backend_cmd,
                PROJECT_ROOT,
                stdout=log_stream,
                stderr=log_stream,
            )
            _wait_http_ready(f"{args.backend_url}/api/health", timeout_sec=args.timeout)

            print(f"[settings-ui] starting frontend: {' '.join(frontend_cmd)}")
            frontend_proc = _spawn(
                frontend_cmd,
                PROJECT_ROOT,
                stdout=log_stream,
                stderr=log_stream,
            )
            _wait_http_ready(args.frontend_url, timeout_sec=args.timeout)
        else:
            _wait_http_ready(f"{args.backend_url}/api/health", timeout_sec=args.timeout)
            _wait_http_ready(args.frontend_url, timeout_sec=args.timeout)

        if args.install_browser:
            install_cmd = [
                "npx",
                "--yes",
                "-p",
                "playwright",
                "playwright",
                "install",
                "chromium",
            ]
            print(f"[settings-ui] installing browser: {' '.join(install_cmd)}")
            install_proc = subprocess.run(install_cmd, cwd=str(PROJECT_ROOT))
            if install_proc.returncode != 0:
                return install_proc.returncode

        capture_script_cmd = [
            "node",
            str(CAPTURE_SCRIPT),
            "--base-url",
            args.frontend_url.rstrip("/"),
            "--output-dir",
            str(args.output_dir),
            "--timeout-ms",
            str(max(args.timeout * 1000, 10_000)),
        ]
        if args.headful:
            capture_script_cmd.append("--headful")
        if args.admin_token.strip():
            capture_script_cmd.extend(["--admin-token", args.admin_token.strip()])
        if args.skip_module_seeding:
            capture_script_cmd.append("--skip-module-seeding")

        shell_cmd = (
            'NODE_PATH="$(dirname "$(command -v playwright)")/.." '
            + " ".join(shlex.quote(part) for part in capture_script_cmd)
        )
        capture_cmd = [
            "npx",
            "--yes",
            "-p",
            "playwright",
            "bash",
            "-lc",
            shell_cmd,
        ]

        print(f"[settings-ui] capturing: {' '.join(capture_cmd)}")
        proc = subprocess.run(capture_cmd, cwd=str(PROJECT_ROOT))
        return proc.returncode
    finally:
        _stop_process(frontend_proc)
        _stop_process(backend_proc)


if __name__ == "__main__":
    raise SystemExit(main())
