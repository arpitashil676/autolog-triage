"""Core domain models shared across the pipeline.

These dataclasses define the contracts between the data layer, the
detection layer, the agents, and the reporting layer. Keeping them in one
place makes the data flow explicit and type-checked end to end. Stdlib
dataclasses are used (no third-party dependency) so the core is lightweight.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum


class Severity(str, Enum):
    """Severity of a detected irregularity, loosely aligned with how an
    automotive test engineer would triage findings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


@dataclass
class LogEntry:
    """A single parsed line from an infotainment testbench trace log."""

    line_no: int
    timestamp: datetime
    level: LogLevel
    component: str
    message: str
    raw: str
    test_case: str | None = None


@dataclass
class Finding:
    """An irregularity detected in a run, with enough context to be triaged."""

    finding_id: str
    test_case: str | None
    component: str
    severity: Severity
    category: str
    summary: str
    detector: str
    evidence_line_nos: list[int] = field(default_factory=list)
    first_timestamp: datetime | None = None
    confidence: float = 1.0

    def as_kwargs(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "test_case": self.test_case,
            "component": self.component,
            "severity": self.severity,
            "category": self.category,
            "summary": self.summary,
            "detector": self.detector,
            "evidence_line_nos": list(self.evidence_line_nos),
            "first_timestamp": self.first_timestamp,
            "confidence": self.confidence,
        }


@dataclass
class TriagedFinding(Finding):
    """A finding after the analyzer agent has reasoned about it."""

    probable_root_cause: str = ""
    recommended_action: str = ""
    is_likely_false_positive: bool = False
    agent_rationale: str = ""


@dataclass
class RunReport:
    """The final artifact: a structured report over one test run."""

    run_id: str
    source_file: str
    generated_at: datetime
    total_log_lines: int
    findings: list[TriagedFinding] = field(default_factory=list)
    summary_text: str = ""

    @property
    def n_critical(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def n_error(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.ERROR)

    def to_json(self, indent: int = 2) -> str:
        def _default(o):
            if isinstance(o, datetime):
                return o.isoformat()
            if isinstance(o, Enum):
                return o.value
            return str(o)

        return json.dumps(asdict(self), default=_default, indent=indent)
