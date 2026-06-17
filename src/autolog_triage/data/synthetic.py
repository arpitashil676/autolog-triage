"""Synthetic infotainment-testbench log generator with ground-truth labels.

A master's evaluation needs ground truth. Real testbench logs are
proprietary and unlabelled, so this module fabricates realistic runs in
which we *know* which irregularities were injected. Each generated run
produces:

  * a ``.log`` file (the input the pipeline sees), and
  * a ``.labels.json`` file (the ground truth the evaluation compares against).

Injected irregularity categories mirror what a smoke-test catalogue would
flag: crashes, timeouts, failed assertions, and anomalous latencies. The
generator is seeded so runs are reproducible.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

COMPONENTS = [
    "MediaPlayer",
    "BluetoothStack",
    "Navigation",
    "VoiceAssistant",
    "RearCamera",
    "ClimateControl",
    "AppFramework",
]

NORMAL_MESSAGES = {
    "MediaPlayer": ["playback started", "track changed", "buffering ok", "volume set"],
    "BluetoothStack": ["device paired", "a2dp connected", "phonebook synced"],
    "Navigation": ["route calculated", "gps fix acquired", "map tile loaded"],
    "VoiceAssistant": ["wake word detected", "intent resolved", "tts finished"],
    "RearCamera": ["stream started", "frame rendered", "overlay drawn"],
    "ClimateControl": ["temperature set", "fan adjusted", "zone synced"],
    "AppFramework": ["app launched", "lifecycle resumed", "ipc ok"],
}

# category -> (level, message templates)
FAULTS = {
    "crash": ("FATAL", ["segmentation fault in {comp}", "{comp} process terminated unexpectedly"]),
    "timeout": ("ERROR", ["{comp} request timed out after 5000ms", "no response from {comp} within deadline"]),
    "assertion": ("ERROR", ["assertion failed: {comp} state invalid", "ASSERT({comp}_ready) failed"]),
    "anomalous_latency": ("WARNING", ["{comp} response latency 1820ms exceeds budget", "{comp} slow frame: 410ms"]),
}

TEST_CASES = [f"TC_{c.upper()[:5]}_{i:03d}" for c in COMPONENTS for i in range(1, 4)]

# Benign, ambiguous WARNING-level messages that are NOT real faults. These
# create false positives for a naive rule-based detector (which flags all
# WARNING+ lines), giving the LLM analyzer's false-positive filter something
# real to improve on. They are deliberately phrased to look borderline.
NOISE_WARNINGS = [
    "transient cache miss, retried successfully",
    "config value missing, using default",
    "deprecated API used, non-blocking",
    "retrying connection (attempt 1/3) ok",
    "clock drift 2ms within tolerance",
]


def _ts(base: datetime, offset_s: float) -> str:
    return (base + timedelta(seconds=offset_s)).isoformat(timespec="milliseconds")


def generate_run(seed: int, n_normal: int = 400, n_faults: int = 6, n_noise: int = 8) -> tuple[list[str], list[dict]]:
    """Generate one run. Returns (log_lines, label_records).

    ``n_noise`` benign WARNING lines are interleaved. They are intentionally
    unlabelled: a naive WARNING+ rule flags them (false positives), whereas a
    well-behaved analyzer should mark them as likely false positives.
    """
    rng = random.Random(seed)
    base = datetime(2026, 3, 1, 9, 0, 0)
    lines: list[str] = []
    labels: list[dict] = []
    t = 0.0

    # Decide fault and noise line positions up front.
    total_lines = n_normal + n_faults + n_noise
    special = rng.sample(range(total_lines), n_faults + n_noise)
    fault_positions = set(special[:n_faults])
    noise_positions = set(special[n_faults:])
    fault_idx = 0

    for pos in range(total_lines):
        t += rng.uniform(0.05, 0.5)
        comp = rng.choice(COMPONENTS)
        tc = rng.choice([c for c in TEST_CASES if c.startswith(f"TC_{comp.upper()[:5]}")] or TEST_CASES)

        if pos in fault_positions:
            category = list(FAULTS.keys())[fault_idx % len(FAULTS)]
            fault_idx += 1
            level, templates = FAULTS[category]
            msg = rng.choice(templates).format(comp=comp)
            line_no = len(lines) + 1
            lines.append(f"{_ts(base, t)} [{level}] {comp} ({tc}): {msg}")
            labels.append(
                {
                    "line_no": line_no,
                    "test_case": tc,
                    "component": comp,
                    "category": category,
                    "severity": "critical" if category == "crash" else ("error" if level == "ERROR" else "warning"),
                }
            )
        elif pos in noise_positions:
            # Benign warning -- emitted but deliberately NOT added to labels.
            msg = rng.choice(NOISE_WARNINGS)
            lines.append(f"{_ts(base, t)} [WARNING] {comp} ({tc}): {msg}")
        else:
            msg = rng.choice(NORMAL_MESSAGES[comp])
            lines.append(f"{_ts(base, t)} [INFO] {comp} ({tc}): {msg}")

    return lines, labels


def write_run(out_dir: str | Path, run_id: str, seed: int, **kwargs) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    raw_dir = out_dir / "raw"
    label_dir = out_dir / "labels"
    raw_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)

    lines, labels = generate_run(seed=seed, **kwargs)
    log_path = raw_dir / f"{run_id}.log"
    label_path = label_dir / f"{run_id}.labels.json"
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    label_path.write_text(json.dumps({"run_id": run_id, "findings": labels}, indent=2), encoding="utf-8")
    return log_path, label_path


def generate_dataset(out_dir: str | Path, n_runs: int = 12, start_seed: int = 1000) -> list[str]:
    """Generate a small labelled dataset of runs."""
    run_ids = []
    for k in range(n_runs):
        run_id = f"run_{k:03d}"
        write_run(out_dir, run_id, seed=start_seed + k, n_normal=350 + 20 * k, n_faults=4 + (k % 5))
        run_ids.append(run_id)
    return run_ids
