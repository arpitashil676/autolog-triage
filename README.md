# AutoLog Triage

**An autonomous multi-agent system for automotive test-log triage and report generation — with a quantitative evaluation against ground truth.**

AutoLog Triage ingests raw infotainment-testbench trace logs, detects
irregularities, uses a multi-agent LLM pipeline to reason about probable
root cause and filter false positives, and generates a structured triage
report. A built-in evaluation harness measures detection quality against
labelled ground truth and benchmarks several pipeline configurations.

> This project was built as a master's-level study. The research question it
> answers: *does a multi-agent LLM layer on top of classical log detection
> improve triage precision without sacrificing recall?* See
> [`docs/THESIS.md`](docs/THESIS.md).

---

## Why this exists

Automotive test teams generate large volumes of trace/logging data from
testbenches. Manually triaging that data — separating real defects from
benign noise, assigning probable cause, and writing up findings — is slow
and repetitive. This project explores automating that loop with cooperating
agents, and, crucially, *measuring how well the automation works*.

## Key features

- **Log parsing** that never silently drops a line.
- **Two complementary detectors**: a deterministic rule-based detector
  (classical baseline) and a statistical anomaly detector.
- **Multi-agent pipeline**: a detection agent, an analyzer agent (root-cause
  reasoning + false-positive judgement), and a reporter agent (executive
  summary), coordinated by an orchestrator.
- **Provider abstraction**: runs fully offline against a deterministic mock
  LLM (default, no API key), or against a real model when configured.
- **Evaluation harness**: precision / recall / F1 against ground-truth
  labels, overall and per category.
- **Reproducible benchmark**: compares `rule_only`, `rule_stat`, and
  `multi_agent` configurations across a labelled dataset.
- **Outputs**: Markdown, HTML, and JSON reports.
- **FastAPI service** and a stdlib **CLI**.

## Architecture

```
 raw .log ──► parser ──► DetectionAgent ──► AnalyzerAgent ──► ReporterAgent ──► RunReport
                          (rule + stat)      (LLM: cause,        (LLM: summary)    │
                                              FP filter)                           ▼
                                                                       Markdown / HTML / JSON
                          ▲                                                        │
                          └──────────────── evaluation harness ◄───── ground-truth labels
```

## Install

```bash
git clone https://github.com/<you>/autolog-triage.git
cd autolog-triage
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,api]"
```

The core depends only on `pandas`, `numpy`, `scikit-learn`, and `jinja2`.
FastAPI and the LLM SDK are optional extras (`[api]`, `[llm]`).

## Quickstart

```bash
# 1. Generate a labelled synthetic dataset (12 runs)
autolog generate-data --runs 12

# 2. Triage a single run -> writes reports/run_000.report.{md,html,json}
autolog triage data/raw/run_000.log

# 3. Run the benchmark comparing configurations
autolog experiment
```

(If you have not installed the package, prefix commands with
`PYTHONPATH=src python -m autolog_triage.cli` instead of `autolog`.)

### Example benchmark output

| Config      | Precision | Recall | F1    |
|-------------|-----------|--------|-------|
| rule_only   | 0.42      | 1.00   | 0.59  |
| rule_stat   | 0.42      | 1.00   | 0.59  |
| multi_agent | 0.97      | 1.00   | 0.99  |

The naive rule-based detector flags every warning-level line, including
benign noise, giving low precision. The multi-agent system's analyzer filters
those false positives, raising precision to ~0.97 with no loss of recall.
*(Exact numbers depend on the generated dataset seed.)*

## Using a real LLM

By default the pipeline uses a deterministic offline mock, so everything is
reproducible and CI-friendly. To use a real model:

```bash
pip install -e ".[llm]"
export AUTOLOG_LLM=anthropic
export ANTHROPIC_API_KEY=sk-...
export AUTOLOG_MODEL=claude-sonnet-4-6   # optional
autolog triage data/raw/run_000.log
```

## Run the API

```bash
pip install -e ".[api]"
uvicorn autolog_triage.api:app --reload
# POST /triage  with {"run_id": "x", "log_text": "..."}
# GET  /health
```

## Tests

```bash
pytest
```

## Project layout

```
src/autolog_triage/
  models.py            # dataclasses: LogEntry, Finding, TriagedFinding, RunReport
  data/parser.py       # log parsing
  data/synthetic.py    # labelled synthetic dataset generator
  detection/detectors.py   # rule-based + statistical detectors
  agents/llm.py        # provider abstraction (mock + Anthropic)
  agents/orchestrator.py   # multi-agent pipeline
  reporting/render.py  # Markdown / HTML / JSON reports
  evaluation/metrics.py    # precision / recall / F1
  evaluation/experiment.py # configuration benchmark
  cli.py               # command-line interface
  api.py               # FastAPI service
tests/                 # offline test suite
docs/                  # thesis writeup + design notes
```

## Limitations & honesty notes

- The dataset is **synthetic**. Results demonstrate the methodology; they are
  not a claim about real testbench performance. Swapping in real labelled
  logs is the natural next step.
- The default LLM is a deterministic mock. Real-model results will differ and
  should be reported separately.
- This is a research/portfolio project, **not** safety-certified software.

## License

MIT — see [LICENSE](LICENSE).
