# Test Run Triage Report — sample_run

**Source:** `sample/data/raw/sample_run.log`
**Generated:** 2026-06-16 12:29:05 UTC
**Log lines analysed:** 129
**Findings:** 9 (2 critical, 2 error)

## Executive Summary

Run analysis complete: 9 finding(s), 2 critical. Critical and error findings should be triaged first; see the table below for per-finding root cause and actions.

## Findings

| # | Severity | Component | Test Case | Category | Summary | Probable Root Cause | Recommended Action | FP? |
|---|----------|-----------|-----------|----------|---------|---------------------|--------------------|-----|
| 1 | critical | BluetoothStack | TC_BLUET_003 | crash | segmentation fault in BluetoothStack | Unhandled exception or memory fault in BluetoothStack. | Capture core dump; retest in isolation; file blocking defect. | no |
| 2 | critical | RearCamera | TC_REARC_002 | crash | RearCamera process terminated unexpectedly | Unhandled exception or memory fault in RearCamera. | Capture core dump; retest in isolation; file blocking defect. | no |
| 3 | error | AppFramework | TC_APPFR_002 | timeout | no response from AppFramework within deadline | AppFramework dependency unresponsive or deadlock. | Increase trace verbosity on the dependency; check deadlines. | no |
| 4 | error | MediaPlayer | TC_MEDIA_002 | assertion | ASSERT(MediaPlayer_ready) failed | MediaPlayer reached an invalid state precondition. | Review state machine and preconditions around the assert. | no |
| 5 | warning | RearCamera | TC_REARC_001 | anomalous_latency | RearCamera slow frame: 410ms | RearCamera resource contention or slow I/O. | Profile the component; compare against latency budget. | no |
| 6 | warning | ClimateControl | TC_CLIMA_002 | unknown | deprecated API used, non-blocking | Insufficient signal to determine a specific cause. | Re-run with debug logging to gather more evidence. | yes |
| 7 | warning | ClimateControl | TC_CLIMA_002 | unknown | transient cache miss, retried successfully | Insufficient signal to determine a specific cause. | Re-run with debug logging to gather more evidence. | yes |
| 8 | warning | BluetoothStack | TC_BLUET_003 | unknown | clock drift 2ms within tolerance | Insufficient signal to determine a specific cause. | Re-run with debug logging to gather more evidence. | yes |
| 9 | warning | BluetoothStack | TC_BLUET_002 | unknown | config value missing, using default | Insufficient signal to determine a specific cause. | Re-run with debug logging to gather more evidence. | yes |
