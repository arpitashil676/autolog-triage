"""Test suite. Runs fully offline against the mock LLM provider."""

from __future__ import annotations

from pathlib import Path

from autolog_triage.agents.llm import MockLLMProvider
from autolog_triage.agents.orchestrator import TriageOrchestrator, _safe_json
from autolog_triage.data.parser import parse_line, parse_log_file
from autolog_triage.data.synthetic import write_run
from autolog_triage.detection.detectors import RuleBasedDetector, StatisticalAnomalyDetector
from autolog_triage.evaluation.metrics import evaluate_run, load_labels
from autolog_triage.models import LogLevel, Severity


def test_parser_handles_well_formed_line():
    e = parse_line(1, "2026-03-01T09:15:02.412 [ERROR] MediaPlayer (TC_MEDIA_004): timed out after 5000ms")
    assert e.level == LogLevel.ERROR
    assert e.component == "MediaPlayer"
    assert e.test_case == "TC_MEDIA_004"
    assert "timed out" in e.message


def test_parser_never_drops_unparseable_line():
    e = parse_line(2, "this is not a valid log line")
    assert e.component == "UNPARSED"
    assert e.raw == "this is not a valid log line"


def test_rule_based_detector_flags_errors():
    entries = [
        parse_line(1, "2026-03-01T09:00:00 [INFO] MediaPlayer (TC_A_001): ok"),
        parse_line(2, "2026-03-01T09:00:01 [FATAL] MediaPlayer (TC_A_001): segmentation fault in MediaPlayer"),
    ]
    findings = RuleBasedDetector().detect(entries)
    assert len(findings) == 1
    assert findings[0].severity == Severity.CRITICAL
    assert findings[0].category == "crash"


def test_statistical_detector_returns_list():
    entries = parse_log_file_from_lines(
        ["2026-03-01T09:00:00 [INFO] A (TC_A_001): ok"] * 5
        + ["2026-03-01T09:00:01 [ERROR] B (TC_B_001): timed out"] * 5
    )
    out = StatisticalAnomalyDetector(z_threshold=0.5).detect(entries)
    assert isinstance(out, list)


def parse_log_file_from_lines(lines):
    return [parse_line(i, ln) for i, ln in enumerate(lines, start=1)]


def test_safe_json_tolerates_fences():
    assert _safe_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _safe_json('preamble {"b": 2} trailing') == {"b": 2}
    assert _safe_json("not json at all") == {}


def test_orchestrator_end_to_end_offline():
    lines = [
        "2026-03-01T09:00:00 [INFO] MediaPlayer (TC_A_001): playback started",
        "2026-03-01T09:00:01 [FATAL] MediaPlayer (TC_A_001): segmentation fault in MediaPlayer",
        "2026-03-01T09:00:02 [ERROR] Navigation (TC_N_001): request timed out after 5000ms",
    ]
    entries = parse_log_file_from_lines(lines)
    orch = TriageOrchestrator(llm=MockLLMProvider())
    report = orch.run("t1", "inline", entries)
    assert report.total_log_lines == 3
    assert len(report.findings) == 2
    # Analyzer populated root cause / action for each finding.
    assert all(f.probable_root_cause for f in report.findings)
    assert report.summary_text


def test_evaluation_matches_injected_faults(tmp_path: Path):
    log_path, label_path = write_run(tmp_path, "run_test", seed=42, n_normal=80, n_faults=4)
    entries = parse_log_file(log_path)
    report = TriageOrchestrator(llm=MockLLMProvider()).run("run_test", str(log_path), entries)
    labels = load_labels(label_path)
    m = evaluate_run(report, labels, exclude_false_positives=False)
    # All injected faults are at WARNING+ level, so recall should be high.
    assert m.recall >= 0.75
    assert m.tp >= 3


def test_api_health_and_triage():
    from fastapi.testclient import TestClient

    from autolog_triage.api import app

    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    resp = client.post(
        "/triage",
        json={"run_id": "api1", "log_text": "2026-03-01T09:00:01 [FATAL] X (TC_X_001): segmentation fault in X"},
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["run_id"] == "api1"
    assert len(body["findings"]) == 1
