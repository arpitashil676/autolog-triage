"""Command-line interface (stdlib argparse; no third-party CLI deps).

Examples
--------
    python -m autolog_triage.cli generate-data --runs 12
    python -m autolog_triage.cli triage data/raw/run_000.log
    python -m autolog_triage.cli experiment
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .agents.orchestrator import TriageOrchestrator
from .data.parser import parse_log_file
from .data.synthetic import generate_dataset
from .evaluation.experiment import format_results_table, run_experiment
from .reporting.render import write_report


def _cmd_generate_data(args: argparse.Namespace) -> None:
    ids = generate_dataset(args.out_dir, n_runs=args.runs)
    print(f"Generated {len(ids)} runs in {args.out_dir}/raw with labels in {args.out_dir}/labels")


def _cmd_triage(args: argparse.Namespace) -> None:
    path = Path(args.log_file)
    entries = parse_log_file(path)
    orch = TriageOrchestrator()
    report = orch.run(run_id=path.stem, source_file=str(path), entries=entries)
    paths = write_report(report, args.out_dir)
    print(f"Run {report.run_id}: {len(report.findings)} findings "
          f"({report.n_critical} critical, {report.n_error} error) over {report.total_log_lines} lines")
    for i, f in enumerate(report.findings[:20], start=1):
        print(f"  {i:2d}. [{f.severity.value:8s}] {f.component:16s} {f.category:18s} {f.summary[:50]}")
    print(f"Reports written: {paths['markdown']} | {paths['html']} | {paths['json']}")


def _cmd_experiment(args: argparse.Namespace) -> None:
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    output = run_experiment(args.data_dir, out_path=args.out)
    print(format_results_table(output))
    print(f"\nFull results: {args.out}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="autolog", description="Automotive test-log triage system")
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate-data", help="Generate a labelled synthetic dataset")
    g.add_argument("--out-dir", default="data")
    g.add_argument("--runs", type=int, default=12)
    g.set_defaults(func=_cmd_generate_data)

    t = sub.add_parser("triage", help="Triage a single run")
    t.add_argument("log_file")
    t.add_argument("--out-dir", default="reports")
    t.set_defaults(func=_cmd_triage)

    e = sub.add_parser("experiment", help="Run the configuration-comparison benchmark")
    e.add_argument("--data-dir", default="data")
    e.add_argument("--out", default="reports/experiment_results.json")
    e.set_defaults(func=_cmd_experiment)
    return p


def app() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    app()
