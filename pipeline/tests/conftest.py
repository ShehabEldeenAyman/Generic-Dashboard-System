"""Shared fixtures: a throwaway Apache Jena Fuseki for the live and browser tests.

The Fuseki server is found through FUSEKI_JAR (the fuseki-server.jar file) or
FUSEKI_HOME (the unzipped Fuseki folder), or in ~/Downloads, ~, or /opt. Tests
that need it are skipped when Java or Fuseki is missing.
"""

from __future__ import annotations

import glob
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time

import pytest
import requests

from triple_store_ingestion import ingest

ROOT = Path(__file__).resolve().parents[2]
TEST_DATA = ROOT / "test-data"


def fuseki_jar() -> Path | None:
    candidates = []
    if os.getenv("FUSEKI_JAR"):
        candidates.append(os.environ["FUSEKI_JAR"])
    if os.getenv("FUSEKI_HOME"):
        candidates.append(str(Path(os.environ["FUSEKI_HOME"]) / "fuseki-server.jar"))
    for pattern in (
        "~/Downloads/apache-jena-fuseki-*/fuseki-server.jar",
        "~/apache-jena-fuseki-*/fuseki-server.jar",
        "/opt/apache-jena-fuseki*/fuseki-server.jar",
    ):
        candidates += sorted(glob.glob(os.path.expanduser(pattern)), reverse=True)
    return next((Path(candidate) for candidate in candidates if Path(candidate).is_file()), None)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def wait_until_up(url: str, timeout: float = 90) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if requests.get(url, timeout=2).ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.3)
    raise RuntimeError(f"{url} did not answer within {timeout} seconds.")


def stop(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()


@pytest.fixture(scope="session")
def fuseki(tmp_path_factory):
    """The URL of a throwaway in-memory Fuseki dataset, such as http://127.0.0.1:41234/dataset."""
    jar = fuseki_jar()
    if jar is None or not shutil.which("java"):
        pytest.skip("Needs Java and Apache Jena Fuseki: set FUSEKI_HOME to the unzipped Fuseki folder.")
    port = free_port()
    workspace = tmp_path_factory.mktemp("fuseki")
    environment = {**os.environ, "FUSEKI_HOME": str(jar.parent), "FUSEKI_BASE": str(workspace / "run")}
    process = subprocess.Popen(
        ["java", "-Xmx2g", "-jar", str(jar), "--update", "--mem", "--port", str(port), "/dataset"],
        cwd=workspace, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}/dataset"
    try:
        wait_until_up(f"{url}/query?query=ASK%7B%7D")
        yield url
    finally:
        stop(process)


@pytest.fixture
def clean_fuseki(fuseki):
    """The throwaway Fuseki, emptied before the test."""
    response = requests.post(f"{fuseki}/update", data={"update": "DROP ALL"}, timeout=30)
    response.raise_for_status()
    return fuseki


@pytest.fixture
def live_fuseki(clean_fuseki, monkeypatch):
    """Point the app's Fuseki client at the empty throwaway Fuseki."""
    monkeypatch.delenv("FUSEKI_QUERY_URL", raising=False)
    monkeypatch.setattr(ingest, "FUSEKI_DATA_URL", f"{clean_fuseki}/data")
    return clean_fuseki
