"""Render a RunReport to Markdown and HTML.

The report is the headline deliverable named in the job description
("automatic ... report generation"). Markdown is used for git-friendly
artifacts; HTML for a shareable standalone file.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Template

from ..models import RunReport

_MD_TEMPLATE = Template(
    """# Test Run Triage Report — {{ r.run_id }}

**Source:** `{{ r.source_file }}`
**Generated:** {{ r.generated_at.strftime('%Y-%m-%d %H:%M:%S') }} UTC
**Log lines analysed:** {{ r.total_log_lines }}
**Findings:** {{ r.findings|length }} ({{ r.n_critical }} critical, {{ r.n_error }} error)

## Executive Summary

{{ r.summary_text }}

## Findings

| # | Severity | Component | Test Case | Category | Summary | Probable Root Cause | Recommended Action | FP? |
|---|----------|-----------|-----------|----------|---------|---------------------|--------------------|-----|
{% for f in r.findings -%}
| {{ loop.index }} | {{ f.severity.value }} | {{ f.component }} | {{ f.test_case or '-' }} | {{ f.category }} | {{ f.summary }} | {{ f.probable_root_cause }} | {{ f.recommended_action }} | {{ 'yes' if f.is_likely_false_positive else 'no' }} |
{% endfor %}
"""
)

_HTML_TEMPLATE = Template(
    """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Triage Report {{ r.run_id }}</title>
<style>
 body{font-family:system-ui,Arial,sans-serif;margin:2rem;color:#1a1a1a}
 h1{font-size:1.4rem} .meta{color:#555;font-size:.9rem}
 table{border-collapse:collapse;width:100%;margin-top:1rem;font-size:.85rem}
 th,td{border:1px solid #ddd;padding:.4rem .6rem;text-align:left;vertical-align:top}
 th{background:#f4f4f4}
 .critical{color:#b00020;font-weight:600}.error{color:#c0392b}.warning{color:#a67c00}
</style></head><body>
<h1>Test Run Triage Report — {{ r.run_id }}</h1>
<p class="meta">Source: {{ r.source_file }} · Generated {{ r.generated_at.strftime('%Y-%m-%d %H:%M') }} UTC ·
{{ r.total_log_lines }} lines · {{ r.findings|length }} findings ({{ r.n_critical }} critical)</p>
<h2>Executive Summary</h2><p>{{ r.summary_text }}</p>
<h2>Findings</h2>
<table><tr><th>#</th><th>Severity</th><th>Component</th><th>Test Case</th><th>Category</th>
<th>Summary</th><th>Probable Root Cause</th><th>Recommended Action</th><th>FP?</th></tr>
{% for f in r.findings %}<tr>
<td>{{ loop.index }}</td><td class="{{ f.severity.value }}">{{ f.severity.value }}</td>
<td>{{ f.component }}</td><td>{{ f.test_case or '-' }}</td><td>{{ f.category }}</td>
<td>{{ f.summary }}</td><td>{{ f.probable_root_cause }}</td><td>{{ f.recommended_action }}</td>
<td>{{ 'yes' if f.is_likely_false_positive else 'no' }}</td></tr>{% endfor %}
</table></body></html>
"""
)


def to_markdown(report: RunReport) -> str:
    return _MD_TEMPLATE.render(r=report)


def to_html(report: RunReport) -> str:
    return _HTML_TEMPLATE.render(r=report)


def write_report(report: RunReport, out_dir: str | Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{report.run_id}.report.md"
    html_path = out_dir / f"{report.run_id}.report.html"
    json_path = out_dir / f"{report.run_id}.report.json"
    md_path.write_text(to_markdown(report), encoding="utf-8")
    html_path.write_text(to_html(report), encoding="utf-8")
    json_path.write_text(report.to_json(indent=2), encoding="utf-8")
    return {"markdown": md_path, "html": html_path, "json": json_path}
