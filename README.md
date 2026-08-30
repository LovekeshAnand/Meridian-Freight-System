# Meridian Freight — Breakdown-to-Resolution Automation Platform

An autonomous, fault-tolerant, and audit-compliant logistics resolution pipeline designed for North India freight networks. Built to handle unexpected format drift, ambiguous operational precedence rules, strict privacy boundaries, and zero-hallucination local LLM inference.

---

## 🌟 Key Architectural Pillars

### 1. Robust Schema Drift & Format Adaptation (`src/surprise/drift_adapter.py`)
- Automatically ingests real-world ticket queues across **JSON**, **JSONL**, **CSV**, **TSV**, and **Excel (`.xlsx`)**.
- Handles BOM encodings (`\ufeff`), Windows `\r\n` line endings, fuzzy synonym column headers (`plate_no` → `vehicle`, `cust_name` → `client`), and type coercion (e.g. `"20 km"` → `20.0`, `27` → `"TKT-0027"`).
- Quarantines only truly unrecoverable records with detailed diagnostics without crashing.

### 2. Context Foundation & Entity Resolution (`src/entity/context_store.py`)
- Ingests Fleet Master, Driver Roster, Excel Maintenance Logs, Trip Logs, and Dispatcher Email records into a unified in-memory store.
- Reconciles conflicting records via precedence rules with exact source citations.
- Includes a Hinglish mechanical notes translator (`src/llm/hinglish_parser.py`) to extract critical signals (jugaad repairs, brake work, component failures).

### 3. Expert Operational Dispatch Engine (`src/rules/`)
Enforces 12 strict operational rules:
- **RULE-DISP-01**: Breakdown ≤ 50km from origin hub dispatches from origin hub; > 50km dispatches from nearest eligible hub.
- **RULE-DISP-02**: Delhi NCR winter (Oct–Feb) BS4 restriction (BS6 only under GRAP pollution policies).
- **RULE-DISP-03 & 04**: Hill routes (Rudrapur/Nainital) require engine heaters and 0 brake jobs in prior 30 days.
- **RULE-DISP-05**: Vehicles overdue for maintenance (>30 days) are grounded.
- **RULE-DISP-06**: Guddu temporary jugaad patches locked to home region with 7-day clock.
- **RULE-CLI-01 to 04**: Client-specific rules including Shakti Cement 36-hour SLA override, Vertex Retail 6 PM gate closing, Apex Chemicals incident vehicle rotation, and Orion Pharma 2020+ model year compliance.

### 4. Epsilon Engine Local LLM Integration (`src/llm/epsilon/`)
- **Zero-Cost Router**: Classifies tasks and calculates complexity (1–10) in `<1ms` without invoking neural networks.
- **Context Injector**: Injects ground-truth verified facts directly from `ContextStore` into prompt payloads.
- **Critique Pass & Flaw Detector**: Intercepts hallucinations (phantom registrations, wrong SLAs, PII leaks, repetition loops).
- **Sparse KV Cache**: INT8 ring buffer with top-k sparse attention.
- **VRAM Guard & Aether Link**: VRAM memory allocation limits and mandatory zero-knowledge session wipes after every call.

### 5. Privacy & Hard Gate Security (`src/security/pii_scrubber.py`)
- Complete redaction of personal data (Aadhaar numbers, Phone numbers, PAN cards, Driving Licenses).
- Zero false positives on UUIDs, SHA-256 hashes, timestamps, and vehicle registration numbers.
- Depth-20 recursive dictionary and list scrubber.

### 6. Idempotency & Immutable Audit Ledger (`src/pipeline/state_manager.py`)
- Exact-once processing across duplicate queue entries and repeated pipeline runs.
- Append-only hash-chained audit logging to `audit/audit.jsonl`.
- Atomic writes (`.tmp` → rename) to eliminate corrupt lines upon sudden interruption.

---

## 🚀 Quick Start

### Installation & Prerequisites
```powershell
# Python 3.11+
pip install -r requirements.txt

# Frontend dependencies (one-time)
cd frontend
npm install
cd ..
```

### 1-Command Full-Stack Launch (Backend + Web UI)
Simply run:
```powershell
python run.py
```
This automatically launches both:
- ⚡ **FastAPI Backend**: `http://127.0.0.1:8000` (Docs at `/docs`)
- 💻 **Dispatch Web UI**: `http://localhost:5173`

---

### Headless CLI Modes
```powershell
# 1. Run unattended queue processor on tickets.json
python run.py --cli

# 2. Run pipeline and auto-approve all client communications
python run.py --approve-all

# 3. Ask grounded operational questions with source citations
python run.py --query "What is Shakti Cement's delivery window?"

# 4. Ingest and process a surprise format queue file (CSV, Excel, TSV, JSON)
python run.py --surprise path/to/surprise_tickets.csv

# 5. Launch terminal human approval dashboard
python run.py --dashboard

# 6. Run full 92-test automated verification suite
python run.py --test
```

---

## 🧪 Verification & Testing

The repository contains **92 automated adversarial tests** covering all modules:

```powershell
python -m pytest tests/ -v
```

See [TEST_GUIDE.md](TEST_GUIDE.md) for full adversarial testing scenarios, edge cases, and verification procedures.
