# Thesis companion: AutoLog Triage

This document frames the repository as a master's-level study so the code and
the academic write-up stay aligned. It is intentionally concise; expand each
section in the actual thesis.

## 1. Problem statement

Automotive infotainment testbenches emit large volumes of trace/logging data.
Triaging that data — distinguishing genuine defects from benign noise,
attributing probable cause, and producing a report — is manual, slow, and
inconsistent across engineers. Automating it could reduce effort and improve
consistency, but naive automation risks flooding engineers with false
positives.

## 2. Research question

> Does adding a multi-agent LLM reasoning layer on top of classical log
> detection improve triage **precision** without sacrificing **recall**,
> compared to detection alone?

Secondary questions:
- How much does a statistical anomaly detector add over fixed rules?
- How reliable is automated root-cause attribution and report generation?

## 3. Hypotheses

- **H1**: A rule-based detector tuned for recall over-flags (low precision)
  in the presence of benign warnings.
- **H2**: An LLM analyzer agent that judges false positives recovers
  precision while preserving the recall of the underlying detector.

## 4. System design

Four cooperating stages communicating through typed models:

1. **Parser** — robust line parsing; unparseable lines are retained.
2. **DetectionAgent** — runs detectors as tools and deduplicates findings.
3. **AnalyzerAgent** — per finding, an LLM produces probable root cause,
   recommended action, and a false-positive judgement.
4. **ReporterAgent** — an LLM produces an executive summary; the orchestrator
   assembles the final report.

A provider abstraction allows a deterministic offline mock (for reproducible
experiments) or a real model (for live-quality results).

## 5. Dataset and ground truth

Real testbench logs are proprietary and unlabelled, so the study uses a
**seeded synthetic generator** that injects a known set of irregularities
(crash, timeout, assertion, anomalous latency) plus **unlabelled benign
warnings** ("noise") that a naive detector will wrongly flag. Each run ships
with a ground-truth label file. This makes the evaluation fully reproducible
and lets us measure precision degradation from noise directly.

*Threat to validity*: synthetic data may not capture the messiness of real
logs. The generator is therefore designed to be replaceable; the evaluation
harness accepts any run + label pair in the same schema.

## 6. Evaluation methodology

- **Matching**: line-level — a predicted finding is a true positive if it
  cites a labelled fault line.
- **Metrics**: precision, recall, F1, overall and per category.
- **Configurations compared**:
  - `rule_only` — rule-based detector only.
  - `rule_stat` — rule-based + statistical detector.
  - `multi_agent` — full pipeline with analyzer false-positive filtering.
- **Reproducibility**: fixed seeds; deterministic mock LLM; results written
  to `reports/experiment_results.json`.

## 7. Results (template)

Fill in from `autolog experiment`. Expected qualitative pattern:

| Config      | Precision | Recall | F1   |
|-------------|-----------|--------|------|
| rule_only   | low       | high   | mid  |
| rule_stat   | low       | high   | mid  |
| multi_agent | high      | high   | high |

Discuss: which categories the analyzer filters well, where it errs, and the
precision/recall trade-off.

## 8. Extending to real data and real models

- Replace the synthetic generator with a loader for real labelled logs.
- Set `AUTOLOG_LLM=anthropic` and re-run the benchmark; report mock vs. real.
- Add a human-baseline study: time-to-triage and agreement vs. the agent.

## 9. Limitations

Synthetic data; mock default LLM; line-level (not span-level) matching;
single-language logs; not safety-certified. Each is a clear avenue for
future work, which strengthens rather than weakens the contribution.
