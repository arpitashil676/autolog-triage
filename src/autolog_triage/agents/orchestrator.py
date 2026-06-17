"""Multi-agent triage system.

The pipeline is deliberately decomposed into specialised agents that
communicate through typed models, mirroring how a multi-agent design is
argued for in the thesis:

* :class:`DetectionAgent` -- wraps the detector(s) and deduplicates raw
  findings. (Tool-using step: it "calls" detectors as tools.)
* :class:`AnalyzerAgent` -- for each finding, queries the LLM to add a
  probable root cause, a recommended action, and a false-positive judgement.
* :class:`ReporterAgent` -- asks the LLM for an executive summary and
  assembles the final :class:`RunReport`.

:class:`TriageOrchestrator` wires them together. The whole flow is provider
agnostic and runs offline with the mock LLM.
"""

from __future__ import annotations

import json
from datetime import datetime

from ..detection.detectors import RuleBasedDetector, StatisticalAnomalyDetector
from ..models import Finding, LogEntry, RunReport, Severity, TriagedFinding
from .llm import LLMProvider, get_provider

_ANALYZER_SYSTEM = (
    "You are an automotive infotainment test analyst. Given one detected log "
    "irregularity, respond ONLY with a JSON object containing keys: "
    "probable_root_cause, recommended_action, is_likely_false_positive (bool), "
    "rationale. Be concise and concrete."
)

_REPORTER_SYSTEM = (
    "You are a test report writer. Given run statistics, respond ONLY with a "
    "JSON object containing a single key 'summary' with a short executive "
    "summary for a test engineer."
)


def _safe_json(text: str) -> dict:
    """Parse a JSON object from model output, tolerating fences/preamble."""
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                return {}
        return {}


class DetectionAgent:
    """Runs detectors as tools and merges/deduplicates their findings."""

    def __init__(self, use_statistical: bool = True) -> None:
        self._detectors = [RuleBasedDetector()]
        if use_statistical:
            self._detectors.append(StatisticalAnomalyDetector())

    def run(self, entries: list[LogEntry]) -> list[Finding]:
        raw: list[Finding] = []
        for det in self._detectors:
            raw.extend(det.detect(entries))
        return self._dedupe(raw)

    @staticmethod
    def _dedupe(findings: list[Finding]) -> list[Finding]:
        """Collapse findings that point at the same line, keeping the most
        confident. Statistical findings on a component already covered by a
        rule-based line are merged by evidence overlap."""
        by_line: dict[int, Finding] = {}
        leftover: list[Finding] = []
        for f in findings:
            if f.evidence_line_nos:
                ln = f.evidence_line_nos[0]
                if ln not in by_line or f.confidence > by_line[ln].confidence:
                    by_line[ln] = f
            else:
                leftover.append(f)
        return list(by_line.values()) + leftover


class AnalyzerAgent:
    """Adds root-cause reasoning to each finding via the LLM."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def analyze(self, finding: Finding) -> TriagedFinding:
        prompt = (
            "ANALYZE_FINDING\n"
            f"<component>{finding.component}</component>\n"
            f"<category>{finding.category}</category>\n"
            f"<severity>{finding.severity.value}</severity>\n"
            f"<summary>{finding.summary}</summary>\n"
            f"<test_case>{finding.test_case or 'unknown'}</test_case>\n"
            "Respond with the JSON object only."
        )
        data = _safe_json(self._llm.complete(_ANALYZER_SYSTEM, prompt))
        return TriagedFinding(
            **finding.as_kwargs(),
            probable_root_cause=data.get("probable_root_cause", ""),
            recommended_action=data.get("recommended_action", ""),
            is_likely_false_positive=bool(data.get("is_likely_false_positive", False)),
            agent_rationale=data.get("rationale", ""),
        )


class ReporterAgent:
    """Produces the executive summary for the run."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def summarize(self, findings: list[TriagedFinding]) -> str:
        n_crit = sum(1 for f in findings if f.severity == Severity.CRITICAL)
        prompt = (
            "SUMMARIZE_RUN\n"
            f"<n_findings>{len(findings)}</n_findings>\n"
            f"<n_critical>{n_crit}</n_critical>\n"
            "Respond with the JSON object only."
        )
        data = _safe_json(self._llm.complete(_REPORTER_SYSTEM, prompt))
        return data.get("summary", "")


class TriageOrchestrator:
    """Coordinates the agents end to end over one run."""

    def __init__(self, llm: LLMProvider | None = None, use_statistical: bool = True) -> None:
        self._llm = llm or get_provider()
        self._detector = DetectionAgent(use_statistical=use_statistical)
        self._analyzer = AnalyzerAgent(self._llm)
        self._reporter = ReporterAgent(self._llm)

    def run(self, run_id: str, source_file: str, entries: list[LogEntry]) -> RunReport:
        raw_findings = self._detector.run(entries)
        triaged = [self._analyzer.analyze(f) for f in raw_findings]
        # Keep findings the analyzer did not rule out as false positives at top.
        triaged.sort(key=lambda f: (f.is_likely_false_positive, _sev_rank(f.severity)))
        summary = self._reporter.summarize(triaged)
        return RunReport(
            run_id=run_id,
            source_file=source_file,
            generated_at=datetime.utcnow(),
            total_log_lines=len(entries),
            findings=triaged,
            summary_text=summary,
        )


def _sev_rank(sev: Severity) -> int:
    order = {Severity.CRITICAL: 0, Severity.ERROR: 1, Severity.WARNING: 2, Severity.INFO: 3}
    return order.get(sev, 4)
