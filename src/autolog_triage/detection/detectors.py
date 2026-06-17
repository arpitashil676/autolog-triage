"""Detection layer: turn parsed log entries into raw Findings.

Two complementary detectors are provided:

* :class:`RuleBasedDetector` -- deterministic pattern/level rules. Fast,
  interpretable, high precision on known fault signatures. This is the
  classical baseline the agent pipeline is benchmarked against.
* :class:`StatisticalAnomalyDetector` -- flags components whose error rate
  or burst behaviour deviates from the run baseline, catching irregularities
  that fixed rules miss.

Both emit :class:`~autolog_triage.models.Finding` objects so downstream
stages are agnostic to how a finding was produced.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from ..models import Finding, LogEntry, LogLevel, Severity

_CATEGORY_KEYWORDS = {
    "crash": ["segmentation fault", "terminated unexpectedly", "core dumped"],
    "timeout": ["timed out", "within deadline", "no response"],
    "assertion": ["assertion failed", "assert(", "state invalid"],
    "anomalous_latency": ["latency", "slow frame", "exceeds budget"],
}

_LEVEL_SEVERITY = {
    LogLevel.FATAL: Severity.CRITICAL,
    LogLevel.ERROR: Severity.ERROR,
    LogLevel.WARNING: Severity.WARNING,
    LogLevel.INFO: Severity.INFO,
    LogLevel.DEBUG: Severity.INFO,
}


def _new_id() -> str:
    return f"F-{uuid.uuid4().hex[:8]}"


def _categorize(message: str) -> str:
    msg = message.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(k in msg for k in keywords):
            return category
    return "unknown"


class RuleBasedDetector:
    """Flag entries at WARNING level or above, classified by keyword."""

    name = "rule_based"

    def __init__(self, min_level: LogLevel = LogLevel.WARNING) -> None:
        self._order = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR, LogLevel.FATAL]
        self._min_idx = self._order.index(min_level)

    def detect(self, entries: list[LogEntry]) -> list[Finding]:
        findings: list[Finding] = []
        for e in entries:
            if self._order.index(e.level) < self._min_idx:
                continue
            category = _categorize(e.message)
            findings.append(
                Finding(
                    finding_id=_new_id(),
                    test_case=e.test_case,
                    component=e.component,
                    severity=_LEVEL_SEVERITY[e.level],
                    category=category,
                    summary=e.message,
                    evidence_line_nos=[e.line_no],
                    first_timestamp=e.timestamp,
                    detector=self.name,
                    confidence=0.9 if category != "unknown" else 0.6,
                )
            )
        return findings


class StatisticalAnomalyDetector:
    """Flag components whose error rate is an outlier for the run.

    A component is anomalous if its share of non-INFO entries exceeds the
    run mean by more than ``z_threshold`` standard deviations. This catches
    degradation that no single line would trip a rule on.
    """

    name = "statistical"

    def __init__(self, z_threshold: float = 2.0) -> None:
        self.z_threshold = z_threshold

    def detect(self, entries: list[LogEntry]) -> list[Finding]:
        by_comp: dict[str, list[LogEntry]] = defaultdict(list)
        for e in entries:
            by_comp[e.component].append(e)

        rates: dict[str, float] = {}
        for comp, es in by_comp.items():
            non_info = sum(1 for e in es if e.level not in (LogLevel.INFO, LogLevel.DEBUG))
            rates[comp] = non_info / max(len(es), 1)

        if len(rates) < 2:
            return []

        values = list(rates.values())
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / len(values)
        std = var**0.5
        if std == 0:
            return []

        findings: list[Finding] = []
        for comp, rate in rates.items():
            z = (rate - mean) / std
            if z >= self.z_threshold and rate > 0:
                first = next((e for e in by_comp[comp] if e.level not in (LogLevel.INFO, LogLevel.DEBUG)), None)
                findings.append(
                    Finding(
                        finding_id=_new_id(),
                        test_case=first.test_case if first else None,
                        component=comp,
                        severity=Severity.WARNING,
                        category="anomalous_latency",
                        summary=f"{comp} shows anomalous error rate (z={z:.1f}, rate={rate:.2f})",
                        evidence_line_nos=[first.line_no] if first else [],
                        first_timestamp=first.timestamp if first else None,
                        detector=self.name,
                        confidence=min(0.5 + 0.1 * z, 0.95),
                    )
                )
        return findings
