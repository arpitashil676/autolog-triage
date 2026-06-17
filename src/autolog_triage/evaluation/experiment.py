"""Benchmark experiment: compare pipeline configurations across the dataset.

Produces the headline result table for the thesis by running each
configuration over every labelled run and aggregating metrics. Configurations:

* ``rule_only``       -- rule-based detector, no statistical detector.
* ``rule_stat``       -- rule-based + statistical detector (multi-detector).
* ``multi_agent``     -- rule + statistical + LLM analyzer false-positive
                         filtering (the full multi-agent system).

The contrast between ``rule_only`` and ``multi_agent`` is the experimental
question: does the multi-agent layer improve triage precision/recall?
"""

from __future__ import annotations

import json
from pathlib import Path

from ..agents.llm import get_provider
from ..agents.orchestrator import TriageOrchestrator
from ..data.parser import parse_log_file
from .metrics import Metrics, aggregate, evaluate_run, load_labels

CONFIGS = {
    "rule_only": {"use_statistical": False, "exclude_fp": False},
    "rule_stat": {"use_statistical": True, "exclude_fp": False},
    "multi_agent": {"use_statistical": True, "exclude_fp": True},
}


def run_experiment(data_dir: str | Path, out_path: str | Path | None = None) -> dict:
    data_dir = Path(data_dir)
    raw_dir = data_dir / "raw"
    label_dir = data_dir / "labels"
    run_files = sorted(raw_dir.glob("*.log"))
    if not run_files:
        raise FileNotFoundError(f"No .log files in {raw_dir}. Generate the dataset first.")

    llm = get_provider()
    results: dict[str, dict] = {}

    for cfg_name, cfg in CONFIGS.items():
        orch = TriageOrchestrator(llm=llm, use_statistical=cfg["use_statistical"])
        per_run: list[Metrics] = []
        for log_path in run_files:
            run_id = log_path.stem
            entries = parse_log_file(log_path)
            report = orch.run(run_id=run_id, source_file=str(log_path), entries=entries)
            labels = load_labels(label_dir / f"{run_id}.labels.json")
            m = evaluate_run(report, labels, exclude_false_positives=cfg["exclude_fp"])
            per_run.append(m)
        agg = aggregate(per_run)
        results[cfg_name] = {
            "provider": getattr(llm, "name", "unknown"),
            "n_runs": len(run_files),
            "aggregate": agg.to_dict(),
        }

    output = {"results": results, "configs": CONFIGS}
    if out_path:
        Path(out_path).write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output


def format_results_table(output: dict) -> str:
    """Render a compact comparison table as Markdown."""
    lines = ["| Config | Precision | Recall | F1 | TP | FP | FN |", "|---|---|---|---|---|---|---|"]
    for name, data in output["results"].items():
        a = data["aggregate"]
        lines.append(
            f"| {name} | {a['precision']} | {a['recall']} | {a['f1']} | {a['tp']} | {a['fp']} | {a['fn']} |"
        )
    return "\n".join(lines)
