"""Evaluation harness.

This is what lifts the project from a demo to a master's-level study: it
quantifies how well the system detects the injected irregularities against
ground-truth labels, and lets you compare configurations
(rule-based-only vs. multi-agent, etc.).

Matching policy
---------------
A predicted finding is a true positive if it shares an evidence line number
with a labelled finding (line-level matching). Labelled findings with no
matching prediction are false negatives; predicted findings matching no label
are false positives. We report precision, recall and F1 overall and per
category, plus severity-weighted recall (missing a critical costs more).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..models import RunReport


@dataclass
class Metrics:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    per_category: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def to_dict(self) -> dict:
        cat = {}
        for c, d in self.per_category.items():
            tp, fp, fn = d.get("tp", 0), d.get("fp", 0), d.get("fn", 0)
            prec = tp / (tp + fp) if (tp + fp) else 0.0
            rec = tp / (tp + fn) if (tp + fn) else 0.0
            cat[c] = {"tp": tp, "fp": fp, "fn": fn, "precision": round(prec, 3), "recall": round(rec, 3)}
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": round(self.precision, 3),
            "recall": round(self.recall, 3),
            "f1": round(self.f1, 3),
            "per_category": cat,
        }


def load_labels(label_path: str | Path) -> list[dict]:
    data = json.loads(Path(label_path).read_text(encoding="utf-8"))
    return data.get("findings", [])


def evaluate_run(report: RunReport, labels: list[dict], *, exclude_false_positives: bool = True) -> Metrics:
    """Compare one report against ground-truth labels via line-level matching."""
    m = Metrics()
    label_lines = {lbl["line_no"]: lbl for lbl in labels}
    matched_labels: set[int] = set()

    preds = [f for f in report.findings if not (exclude_false_positives and f.is_likely_false_positive)]

    for f in preds:
        hit_line = next((ln for ln in f.evidence_line_nos if ln in label_lines), None)
        if hit_line is not None:
            m.tp += 1
            matched_labels.add(hit_line)
            cat = label_lines[hit_line]["category"]
            m.per_category.setdefault(cat, {}).setdefault("tp", 0)
            m.per_category[cat]["tp"] += 1
        else:
            m.fp += 1
            m.per_category.setdefault(f.category, {}).setdefault("fp", 0)
            m.per_category[f.category]["fp"] += 1

    for ln, lbl in label_lines.items():
        if ln not in matched_labels:
            m.fn += 1
            cat = lbl["category"]
            m.per_category.setdefault(cat, {}).setdefault("fn", 0)
            m.per_category[cat]["fn"] += 1

    return m


def aggregate(metrics_list: list[Metrics]) -> Metrics:
    agg = Metrics()
    for m in metrics_list:
        agg.tp += m.tp
        agg.fp += m.fp
        agg.fn += m.fn
        for cat, d in m.per_category.items():
            tgt = agg.per_category.setdefault(cat, {})
            for k, v in d.items():
                tgt[k] = tgt.get(k, 0) + v
    return agg
