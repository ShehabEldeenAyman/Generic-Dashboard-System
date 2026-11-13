#!/usr/bin/env python3
"""Start Semantic Pipeline Studio with one command.

    python run.py          Build the frontend when needed, then serve the UI and
                           API together on http://localhost:8000
    python run.py --dev    Hot-reloading backend (port 8000) and Vite dev server
                           (port 5173) side by side; Ctrl+C stops both.

Fuseki is an external service and still has to be started separately.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
DIST_INDEX = FRONTEND / "dist" / "index.html"


BACKEND_MODULES = ("fastapi", "uvicorn", "multipart", "rdflib", "pyshacl", "openpyxl", "dateutil", "requests")


def check_backend_dependencies() -> None:
    missing = [name for name in BACKEND_MODULES if importlib.util.find_spec(name) is None]
    if missing:
        sys.exit(
            f"Missing Python packages for {sys.executable}: {', '.join(missing)}\n"
            "Create and activate a virtual environment, then install the requirements:\n"
            "  python3 -m venv .venv\n"
            "  source .venv/bin/activate        (Windows: .\\.venv\\Scripts\\Activate.ps1)\n"
            "  python -m pip install -r requirements.txt"
        )


def npm() -> str:
    executable = shutil.which("npm")  # resolves npm.cmd on Windows
    if not executable:
        sys.exit("npm was not found on PATH. Install Node.js to build the frontend.")
    return executable


def ensure_frontend_dependencies() -> None:
    if not (FRONTEND / "node_modules").is_dir():
        print("Installing frontend dependencies...")
        subprocess.run([npm(), "install"], cwd=FRONTEND, check=True)


def frontend_is_stale() -> bool:
    if not DIST_INDEX.is_file():
        return True
    built_at = DIST_INDEX.stat().st_mtime
    sources = [
        FRONTEND / "index.html",
        FRONTEND / "vite.config.js",
        FRONTEND / "package.json",
        *(FRONTEND / "src").rglob("*"),
    ]
    return any(path.is_file() and path.stat().st_mtime > built_at for path in sources)


def build_frontend(force: bool) -> None:
    if not force and not frontend_is_stale():
        print("Frontend build is up to date.")
        return
    ensure_frontend_dependencies()
    print("Building frontend...")
    subprocess.run([npm(), "run", "build"], cwd=FRONTEND, check=True)


def uvicorn_command(host: str, port: int, reload: bool) -> list[str]:
    command = [
        sys.executable, "-m", "uvicorn", "pipeline.playground_server:app",
        "--host", host, "--port", str(port),
    ]
    return command + ["--reload"] if reload else command


def run_together(commands: list[tuple[list[str], Path]]) -> int:
    """Run processes side by side; stop all of them when one exits or on Ctrl+C."""
    processes = [subprocess.Popen(command, cwd=cwd) for command, cwd in commands]
    try:
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
    return max((process.returncode or 0) for process in processes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Start Semantic Pipeline Studio.")
    parser.add_argument("--dev", action="store_true", help="run backend and Vite dev server with hot reload")
    parser.add_argument("--rebuild", action="store_true", help="force a fresh frontend build")
    parser.add_argument("--host", default="127.0.0.1", help="backend host (use 0.0.0.0 to expose on the network)")
    parser.add_argument("--port", type=int, default=8000, help="backend port")
    arguments = parser.parse_args()
    check_backend_dependencies()

    if arguments.dev:
        ensure_frontend_dependencies()
        proxy_host = "127.0.0.1" if arguments.host in {"0.0.0.0", "::"} else arguments.host
        os.environ["PIPELINE_API_URL"] = f"http://{proxy_host}:{arguments.port}"  # read by vite.config.js
        print(f"Backend: http://{arguments.host}:{arguments.port}   Frontend: http://localhost:5173")
        return run_together([
            (uvicorn_command(arguments.host, arguments.port, reload=True), ROOT),
            ([npm(), "run", "dev"], FRONTEND),
        ])

    build_frontend(force=arguments.rebuild)
    print(f"Semantic Pipeline Studio: http://{arguments.host}:{arguments.port}")
    try:
        return subprocess.run(
            uvicorn_command(arguments.host, arguments.port, reload=False), cwd=ROOT
        ).returncode
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
