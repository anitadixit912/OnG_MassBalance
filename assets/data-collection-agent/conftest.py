from __future__ import annotations
import os
os.environ["IBD_TESTING"] = "1"

import json, socket, subprocess, sys, time
from pathlib import Path
from typing import Any
import pytest

AGENT_ROOT = Path(__file__).parent
SECTIONS: list[tuple[str, str, str]] = [
    ("structure", "Structure Tests", "structure"),
    ("server", "Server Tests", "server"),
    ("", "Agent Tests", "agent_tests"),
]

def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        return s.getsockname()[1]

@pytest.fixture(scope="session")
def agent_path() -> Path:
    return AGENT_ROOT

@pytest.fixture(scope="session")
def agent_app_path(agent_path: Path) -> Path:
    return agent_path / "app"

@pytest.fixture(scope="session")
def add_agent_to_path(agent_app_path: Path):
    p = str(agent_app_path)
    added = False
    if p not in sys.path:
        sys.path.insert(0, p)
        added = True
    yield
    if added and p in sys.path:
        sys.path.remove(p)

@pytest.fixture
def start_agent(agent_path: Path):
    port = _get_free_port()
    main_file = agent_path / "app" / "main.py"
    server_env = {**os.environ, "OTEL_SDK_DISABLED": "true", "IBD_TESTING": "1"}
    process = subprocess.Popen([sys.executable, str(main_file), "--port", str(port)], cwd=str(agent_path), env=server_env, stderr=None, text=True)
    deadline = time.monotonic() + 30
    ready = False
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(f"Server process exited early (exit code: {process.poll()})")
        try:
            with socket.create_connection(("localhost", port), timeout=0.5):
                ready = True
                break
        except OSError:
            time.sleep(0.5)
    if not ready:
        process.terminate()
        pytest.fail(f"Server did not become ready on port {port} within 30s")
    yield {"process": process, "port": port}
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "structure: Tests for file and module structure")
    config.addinivalue_line("markers", "server: Tests for server startup and A2A endpoints")

_results: dict[str, list[dict[str, Any]]] = {"structure": [], "server": [], "agent_tests": []}

def _section_for(item: pytest.Item) -> str:
    marker_names = {m.name for m in item.iter_markers()}
    for marker, _label, key in SECTIONS[:-1]:
        if marker in marker_names:
            return key
    return "agent_tests"

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> pytest.Generator:
    outcome = yield
    report: pytest.TestReport = outcome.get_result()
    if report.when == "call" or (report.when == "setup" and report.skipped):
        outcome_str = "passed" if report.passed else ("failed" if report.failed else "skipped")
        _results[_section_for(item)].append({"name": report.nodeid.split("::")[-1], "outcome": outcome_str, "duration": round(getattr(report, "duration", 0.0), 4)})

def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    sections_out = []
    for _marker, label, key in SECTIONS:
        tests = _results[key]
        total = len(tests)
        passed = sum(1 for t in tests if t["outcome"] == "passed")
        failed = sum(1 for t in tests if t["outcome"] == "failed")
        skipped = sum(1 for t in tests if t["outcome"] == "skipped")
        section: dict[str, Any] = {"name": label, "marker": key, "total": total, "passed": passed, "failed": failed, "skipped": skipped, "score": round(passed / total * 100, 2) if total else 0.0, "tests": tests}
        if key == "agent_tests":
            cov_path = AGENT_ROOT / "coverage.json"
            if cov_path.exists():
                try:
                    cov_data = json.loads(cov_path.read_text())
                    section["coverage"] = round(cov_data["totals"]["percent_covered"], 2)
                except Exception:
                    pass
        sections_out.append(section)
    total_all = sum(s["total"] for s in sections_out)
    passed_all = sum(s["passed"] for s in sections_out)
    failed_all = sum(s["failed"] for s in sections_out)
    report_path = AGENT_ROOT / "test_report.json"
    report_path.write_text(json.dumps({"summary": {"total": total_all, "passed": passed_all, "failed": failed_all, "score": round(passed_all / total_all * 100, 2) if total_all else 0.0}, "sections": sections_out}, indent=2))
    print(f"\nReport written to {report_path}")
