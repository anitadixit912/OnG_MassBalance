from __future__ import annotations
import os; os.environ["IBD_TESTING"] = "1"
import json, socket, subprocess, sys, time
from pathlib import Path
from typing import Any
import pytest

AGENT_ROOT = Path(__file__).parent
SECTIONS = [("structure", "Structure Tests", "structure"), ("server", "Server Tests", "server"), ("", "Agent Tests", "agent_tests")]

def _get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s: s.bind(("", 0)); s.listen(1); return s.getsockname()[1]

@pytest.fixture(scope="session")
def agent_path(): return AGENT_ROOT
@pytest.fixture(scope="session")
def agent_app_path(agent_path): return agent_path / "app"
@pytest.fixture(scope="session")
def add_agent_to_path(agent_app_path):
    p = str(agent_app_path)
    added = p not in sys.path
    if added: sys.path.insert(0, p)
    yield
    if added and p in sys.path: sys.path.remove(p)
@pytest.fixture
def start_agent(agent_path):
    port = _get_free_port()
    process = subprocess.Popen([sys.executable, str(agent_path/"app"/"main.py"), "--port", str(port)], cwd=str(agent_path), env={**os.environ, "OTEL_SDK_DISABLED": "true", "IBD_TESTING": "1"}, stderr=None, text=True)
    deadline = time.monotonic() + 30; ready = False
    while time.monotonic() < deadline:
        if process.poll() is not None: pytest.fail("Server exited early")
        try:
            with socket.create_connection(("localhost", port), timeout=0.5): ready = True; break
        except OSError: time.sleep(0.5)
    if not ready: process.terminate(); pytest.fail("Server not ready")
    yield {"process": process, "port": port}
    process.terminate()
    try: process.wait(timeout=5)
    except subprocess.TimeoutExpired: process.kill(); process.wait()

def pytest_configure(config):
    config.addinivalue_line("markers", "structure: Tests for file and module structure")
    config.addinivalue_line("markers", "server: Tests for server startup and A2A endpoints")

_results: dict[str, list] = {"structure": [], "server": [], "agent_tests": []}
def _section_for(item):
    names = {m.name for m in item.iter_markers()}
    for marker, _, key in SECTIONS[:-1]:
        if marker in names: return key
    return "agent_tests"

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield; report = outcome.get_result()
    if report.when == "call" or (report.when == "setup" and report.skipped):
        _results[_section_for(item)].append({"name": report.nodeid.split("::")[-1], "outcome": "passed" if report.passed else "failed" if report.failed else "skipped", "duration": round(getattr(report, "duration", 0.0), 4)})

def pytest_sessionfinish(session, exitstatus):
    sections_out = []
    for _, label, key in SECTIONS:
        tests = _results[key]; total = len(tests); passed = sum(1 for t in tests if t["outcome"] == "passed")
        s: dict[str, Any] = {"name": label, "marker": key, "total": total, "passed": passed, "failed": total-passed-sum(1 for t in tests if t["outcome"]=="skipped"), "skipped": sum(1 for t in tests if t["outcome"]=="skipped"), "score": round(passed/total*100, 2) if total else 0.0, "tests": tests}
        if key == "agent_tests":
            cov_path = AGENT_ROOT/"coverage.json"
            if cov_path.exists():
                try: s["coverage"] = round(json.loads(cov_path.read_text())["totals"]["percent_covered"], 2)
                except: pass
        sections_out.append(s)
    total_all = sum(s["total"] for s in sections_out); passed_all = sum(s["passed"] for s in sections_out)
    (AGENT_ROOT/"test_report.json").write_text(json.dumps({"summary": {"total": total_all, "passed": passed_all, "failed": total_all-passed_all, "score": round(passed_all/total_all*100, 2) if total_all else 0.0}, "sections": sections_out}, indent=2))
