# Meridian Freight — Test Guide

> **Single source of truth for testing all components, edge cases, and adversarial scenarios.**  
> Every command below is runnable from the project root. Nothing is hardcoded; the system  
> is designed to handle anything the real world throws at it.

---

## Quick Start — Run Everything

```powershell
# From d:\meridian
python -m pytest tests/ -v          # All 85 tests
python run.py                        # Full pipeline run (processes all tickets)
python run.py                        # Re-run immediately — must produce identical outputs
python run.py --query "What is Shakti Cement's SLA?"
python run.py --approve-all
python run.py --surprise <path_to_file>
```

---

## Test Suites

### 1. `test_drift_adapter.py` — Surprise File Format Resilience
Tests the `SurpriseDriftAdapter` against every real-world file format variation.

```powershell
python -m pytest tests/test_drift_adapter.py -v
```

| What It Tests | Expected Result |
|---|---|
| Standard JSON array | Parsed, 0 drift alerts |
| JSONL (1 object per line) | Parsed correctly |
| CSV with standard headers | CSV detected, key-mapped |
| TSV (tab-separated) | TSV detected, key-mapped |
| BOM-encoded UTF-8 (`\ufeff` prefix) | BOM stripped, parsed |
| Windows `\r\n` line endings | Normalized, parsed |
| Empty file | `[]` returned + alert, no crash |
| File not found | `[]` + alert, no crash |
| Single dict (not a list) | Wrapped and processed |
| Nested `{"tickets": [...]}` | Detected, processed |
| Numeric `ticket_id: 27` | Coerced to `"TKT-0027"` |
| `km: "20 km"` (string with unit) | Coerced to `20.0` |
| Alternate key names (`plate_no`, `cust_name`, etc.) | Remapped to canonical, drift alert logged |
| Unknown extra keys | Preserved as `_extra_<key>`, never dropped |
| Mixed valid + corrupt rows | Valid processed, corrupt noted in alerts |

---

### 2. `test_validator.py` — Type Coercion & Quarantine Logic
Tests that the validator **coerces before quarantining** and only quarantines truly unrecoverable records.

```powershell
python -m pytest tests/test_validator.py -v
```

| Input | Expected |
|---|---|
| `ticket_id: 27` (int) | Coerced to `"TKT-0027"`, valid |
| `ticket_id: True` (bool) | Quarantined |
| `km: "20 km"` | Coerced to `20.0`, valid |
| `km: "~35.5"` | Coerced to `35.5`, valid |
| `km: "far away"` | Quarantined |
| `km: -5` | Quarantined (negative distance) |
| `created_at: "30-08-2026"` | Parsed alternate format, valid |
| `created_at: "30/08/2026"` | Parsed, valid |
| `created_at: "not-a-date"` | Quarantined |
| `client: ""` | Quarantined |
| `None` record | Quarantined, no crash |
| `[1, 2, 3]` record | Quarantined, no crash |
| `42` integer record | Quarantined, no crash |
| `"string"` record | Quarantined, no crash |
| `km: 9999` | Valid with warning (unusually large) |

---

### 3. `test_pii.py` — Hard Gate Security (Score Cap If Failed)
Tests the PII scrubber against all known and adversarial PII patterns.

> ⚠️ **If any test in this suite fails, the system is NOT ready for evaluation.**

```powershell
python -m pytest tests/test_pii.py -v
```

| PII Type | Test Input | Expected |
|---|---|---|
| Aadhaar (spaced) | `2345 6789 0123` | `[REDACTED_AADHAAR]` |
| Aadhaar (dashed) | `2345-6789-0123` | `[REDACTED_AADHAAR]` |
| Aadhaar in UUID | `ec8d-2345-6789-0123-ab12` | NOT redacted |
| Phone 10-digit | `9311840522` | `[REDACTED_PHONE]` |
| Phone +91 prefix | `+91 93118 40522` | `[REDACTED_PHONE]` |
| Planted known PII | `+91 93118 40522` | `[REDACTED_PHONE]` |
| Timestamp | `20260830` | NOT redacted |
| PAN card | `ABCDE1234F` | `[REDACTED_PAN]` |
| DL number | `UP14 1987 0000123` | `[REDACTED_DL]` |
| Vehicle plate | `UP40IM3144` | NOT redacted |
| SHA-256 hash | `a`×64 | NOT redacted |
| UUID | `550e8400-e29b-41d4-a716-...` | NOT redacted |
| Nested 3 levels deep | `{"l1": {"l2": {"l3": "9311840522"}}}` | All levels redacted |
| After redact_record + JSON dump | scan_for_pii returns `[]` | **ZERO violations** |

---

### 4. `test_idempotency.py` — Pipeline Re-runnability
Tests that running twice produces identical results and deduplication works.

```powershell
python -m pytest tests/test_idempotency.py -v
```

| Scenario | Expected |
|---|---|
| Run pipeline twice with same audit file | Run 2 processes 0 new tickets |
| Queue with 3 duplicate ticket_ids | Only 1 work order generated |
| Empty queue file `[]` | 0 processed, 0 quarantined, no crash |
| Missing queue file | Returns `{"status": "error"}`, no crash |

---

### 5. `test_surprise_file.py` — End-to-End Surprise Processing
Tests the full pipeline processing a surprise file with renamed keys and bad records.

```powershell
python -m pytest tests/test_surprise_file.py -v
```

| Scenario | Expected |
|---|---|
| Surprise JSON with `plate_no`, `source_hub`, `cust_name`, etc. | Drift alerts logged, all keys remapped |
| Surprise file with 1 valid + 1 corrupt record | 1 work order, 1 quarantine entry |
| Grounded query: "What is Shakti Cement's delivery window?" | 36-hour answer with citation |
| Ungrounded query: "What is the CEO's dog's name?" | "Insufficient data" — no hallucination |

---

### 6. `test_rules.py` — Expert Rules Engine
Tests all 12 operational rules from Rajender's dispatcher interview.

```powershell
python -m pytest tests/test_rules.py -v
```

| Rule | Test Scenario | Expected |
|---|---|---|
| RULE-DISP-01 | Breakdown 20km from origin | Origin hub used |
| RULE-DISP-01 | Breakdown 80km from origin | All hubs searched |
| RULE-DISP-02 | December, Delhi NCR, BS4 vehicle | BS4 rejected |
| RULE-DISP-02 | August, Delhi NCR, BS4 vehicle | BS4 allowed (no winter) |
| RULE-DISP-03 | Rudrapur route, no heater, Feb | Vehicle rejected |
| RULE-DISP-04 | Brake work done 10 days ago | Hill route rejected |
| RULE-DISP-05 | Last service 200 days ago | Vehicle grounded |
| RULE-DISP-06 | Active Guddu jugaad, leaving home hub | Vehicle locked |
| RULE-CLI-03 | Apex Chemicals, vehicle had incident | Vehicle rotated |
| RULE-CLI-04 | Orion Pharma, 2018 model vehicle | Rejected (must be ≥ 2020) |
| RULE-CLI-01 | Shakti Cement, August, Lucknow | 20% ETA buffer + 36h SLA |

---

## Manual Verification

After `python run.py`, verify these output files:

```powershell
# Count lines in output files (should match ticket counts)
(Get-Content outputs\work_orders.jsonl | Measure-Object -Line).Lines
(Get-Content outputs\quarantine.jsonl | Measure-Object -Line).Lines
(Get-Content outputs\comms_pending.jsonl | Measure-Object -Line).Lines

# Check audit log integrity
(Get-Content audit\audit.jsonl | Measure-Object -Line).Lines

# Verify zero PII in all outputs
python -c "
import json, glob
from src.security.pii_scrubber import scan_for_pii
files = glob.glob('outputs/*.jsonl') + glob.glob('audit/*.jsonl')
total_violations = 0
for f in files:
    for line in open(f, encoding='utf-8'):
        viols = scan_for_pii(line)
        if viols:
            print(f'PII VIOLATION in {f}: {viols}')
            total_violations += len(viols)
print(f'Total PII violations: {total_violations}')
"
```

---

## Testing the Surprise File (Final Hour)

The evaluator will drop a surprise file in a format that looks **different** from `tickets.json`.  
Run the pipeline against it:

```powershell
# Replace with the actual path to the surprise file (JSON, JSONL, CSV, TSV, or XLSX)
python run.py --surprise path\to\surprise_queue.csv

# Or if using the pipeline directly:
python -c "
from src.pipeline.processor import BreakdownPipeline
p = BreakdownPipeline()
result = p.process_ticket_queue(queue_file_path=__import__('pathlib').Path('path/to/surprise_queue.csv'))
print(result)
"
```

**What the system does automatically:**
1. Detects file format (JSON/JSONL/CSV/TSV/Excel)
2. Strips BOM encoding, normalizes `\r\n`
3. Remaps alternative field names (`plate_no` → `vehicle`, `cust_name` → `client`, etc.)
4. Coerces `"20 km"` → `20.0`, `27` → `"TKT-0027"`
5. Unwraps `{"tickets": [...]}` nested structures
6. Quarantines records that genuinely cannot be recovered
7. Logs all drift alerts to `audit/pipeline.log`
8. Never crashes — always produces output

---

## Adversarial Scenario Quick Reference

| Scenario | How to Reproduce | Expected Behavior |
|---|---|---|
| Corrupt `audit.jsonl` | `echo "CORRUPT" >> audit\audit.jsonl` then re-run | Corrupt line skipped, rest of state loaded |
| Missing `fleet_master.csv` | Rename file, re-run | Pipeline starts with empty vehicle store, logs alert |
| Missing `maintenance_log.xlsx` | Rename file, re-run | Pipeline continues, maintenance data unavailable |
| Wrong Excel sheet name | Rename sheet to "Breakdown Log", re-run | Auto-detects first available sheet, logs drift alert |
| Ctrl+C mid-run | Run pipeline, press Ctrl+C | Completes current ticket, flushes outputs cleanly |
| Queue file is empty `[]` | `echo [] > test.json`, run with it | 0 processed, 0 quarantined, no crash |
| All tickets duplicate | Feed queue with same ticket_id 30x | 1 work order, 29 deduplicated |
| Ticket with `km: "abc"` | Inject into queue | Quarantined with clear reason |
| Ticket with `vehicle: null` | Inject into queue | Quarantined with clear reason |
| 1000 random garbage records | Inject into queue | All quarantined, 0 crashes |

---

## Observability — Reading the Logs

After a run, the following files contain the full decision trail:

| File | Contents |
|---|---|
| `audit/audit.jsonl` | Immutable hash-chained record of every decision |
| `audit/pipeline.log` | Structured JSONL log of all INFO/WARN/ERROR/ALERT events |
| `outputs/work_orders.jsonl` | Generated work orders (one per valid processed ticket) |
| `outputs/comms_pending.jsonl` | Draft client communications awaiting approval |
| `outputs/comms_sent.jsonl` | Approved and sent communications |
| `outputs/quarantine.jsonl` | Rejected records with quarantine reasons |

To reconstruct any decision in under 60 seconds:
```powershell
# Find all decisions for a specific ticket
Select-String "TKT-0005" audit\audit.jsonl | ConvertFrom-Json
```

### 7. `test_epsilon_engine.py` — Epsilon Local LLM Engine & Anti-Hallucination
Tests the ported Epsilon Engine orchestration pipeline from Nyaya AI.

```powershell
python -m pytest tests/test_epsilon_engine.py -v
```

| What It Tests | Expected Result |
|---|---|
| Zero-Cost Router (`router.py`) | Deterministic complexity scoring (1-10) and tier mapping (fast/balanced/deep) in <1ms |
| Context Injector (`context_injector.py`) | Builds strictly verified fact blocks with source citations from ContextStore |
| Critique Pass (`critique.py`) | Intercepts hallucinated vehicle plates, wrong SLAs (e.g. 48h vs 36h), PII leaks, and repetition bugs |
| Sparse KV Cache (`kv_cache.py`) | Ring-buffer INT8 quantization with top-k sparse attention for multi-turn conversations |
| VRAM Guard (`vram_guard.py`) | Resource budgeting and single-agent execution lock preventing OOM crashes |
| Aether Link (`aether_link.py`) | Zero-knowledge session wipe after every inference call to eliminate cross-session data leaks |
| Local LLM Interface (`local_llm.py`) | End-to-end grounded comms drafting and Q&A with 100% resilient fallback |

---

## Complete Meridian Pipeline Architecture & Epsilon Flow

```
Raw Tickets / Surprise Queue
              │
              ▼
┌───────────────────────────────────────────────────────────┐
│ 1. Ingestion & Validation (Coercion-First + Quarantine)   │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│ 2. Context Enrichment (Fleet, Drivers, Maintenance, Rules)│
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│ 3. Expert Rule Evaluation (12 Operational Dispatch Rules) │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│ 4. Replacement Selection (Decision Trail & Failure Modes) │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│ 5. Work Order Outbox (outputs/work_orders.jsonl)          │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│ 6. Epsilon Engine LLM Client Notification Drafting        │
│    - Zero-Cost Complexity Router (Fast/Balanced/Deep)     │
│    - Anti-Hallucination Fact Injector                     │
│    - VRAM Guard Resource Lock                             │
│    - Algorithmic Critique Pass (Fleet/SLA/PII validation) │
│    - Zero-Knowledge Session Wipe (Aether Link)            │
│    -> outputs/comms_pending.jsonl                         │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│ 7. Immutable Hash-Chained Audit Ledger (audit/audit.jsonl)│
└───────────────────────────────────────────────────────────┘
```

---

*Last updated: 2026-08-30. Test count: 92 passing.*
