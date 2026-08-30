"""FastAPI Backend Server for Meridian Freight Dispatch Platform.

Exposes REST APIs for:
- Rajender's Brain (Epsilon Engine grounded queries with exact citations)
- Breakdown resolution pipeline execution
- Human approval gate (comms_pending -> comms_sent)
- Fleet inventory & maintenance status
- Immutable audit ledger & hash verification
- Surprise format ingestion & testing sandbox
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import (
    WORK_ORDERS_FILE,
    COMMS_PENDING_FILE,
    COMMS_SENT_FILE,
    QUARANTINE_FILE,
    AUDIT_FILE,
    TICKETS_FILE,
    HUB_ROAD_DISTANCES,
    HUB_COORDINATES
)
from src.entity.context_store import ContextStore
from src.pipeline.processor import BreakdownPipeline
from src.ui.dashboard import ApprovalGate
from src.llm.local_llm import LocalLLM
from src.surprise.drift_adapter import SurpriseDriftAdapter

app = FastAPI(
    title="Meridian Freight Automation API",
    description="Backend API supporting Rajender's Dispatch Brain and Breakdown Resolution Cockpit",
    version="2.0.0"
)

# Enable CORS for frontend development and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton Context Store and Epsilon LLM
context_store = ContextStore()
context_store.load_all()
local_llm = LocalLLM(context_store)

# Request Models
class QueryRequest(BaseModel):
    question: str

class TicketInput(BaseModel):
    ticket_id: str
    vehicle: str
    origin_hub: str
    km_from_origin_hub: float
    client: str
    created_at: Optional[str] = None
    issue: Optional[str] = "mechanical issue"
    destination: Optional[str] = None
    severity: Optional[str] = "HIGH"

class ApproveRequest(BaseModel):
    message_id: Optional[str] = None
    approve_all: bool = False
    approved_by: str = "dispatch_lead"

class RejectRequest(BaseModel):
    message_id: str
    reason: str
    rejected_by: str = "dispatch_lead"

class EditCommsRequest(BaseModel):
    message_id: str
    edited_body: str

# Helper functions
def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
    return records

def _write_jsonl(path: Path, records: List[Dict[str, Any]]):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/status")
def get_system_status():
    """Returns general platform health, loaded context stats, and ledger counts."""
    wo_count = len(_read_jsonl(WORK_ORDERS_FILE))
    pending_count = len(_read_jsonl(COMMS_PENDING_FILE))
    sent_count = len(_read_jsonl(COMMS_SENT_FILE))
    quarantine_count = len(_read_jsonl(QUARANTINE_FILE))
    audit_count = len(_read_jsonl(AUDIT_FILE))

    return {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "epsilon_llm_online": local_llm.is_available,
        "context_store": {
            "vehicles_loaded": len(context_store.vehicles),
            "drivers_loaded": len(context_store.drivers),
            "maintenance_records": len(context_store.maintenance_records),
            "email_threads": len(context_store.email_threads)
        },
        "counts": {
            "work_orders": wo_count,
            "comms_pending": pending_count,
            "comms_sent": sent_count,
            "quarantine": quarantine_count,
            "audit_entries": audit_count
        }
    }

@app.post("/api/query")
def ask_rajender_brain(req: QueryRequest):
    """Submits a natural language query to Rajender's Brain / Epsilon Engine."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    res = local_llm.query(req.question)
    return res

@app.get("/api/pipeline/results")
def get_pipeline_results():
    """Retrieves all pipeline outputs for display."""
    return {
        "work_orders": _read_jsonl(WORK_ORDERS_FILE),
        "comms_pending": _read_jsonl(COMMS_PENDING_FILE),
        "comms_sent": _read_jsonl(COMMS_SENT_FILE),
        "quarantine": _read_jsonl(QUARANTINE_FILE)
    }

@app.post("/api/pipeline/run")
def run_pipeline():
    """Executes the standard tickets.json pipeline."""
    pipeline = BreakdownPipeline(context_store=context_store)
    result = pipeline.process_ticket_queue(TICKETS_FILE)
    return result

@app.post("/api/pipeline/submit_ticket")
def submit_single_ticket(ticket: TicketInput):
    """Processes a custom interactive ticket submitted by dispatcher."""
    ticket_dict = ticket.dict()
    if not ticket_dict.get("created_at"):
        ticket_dict["created_at"] = datetime.now().isoformat()

    temp_path = Path("d:/meridian/data/interactive_queue.json")
    temp_path.write_text(json.dumps([ticket_dict]), encoding="utf-8")

    pipeline = BreakdownPipeline(context_store=context_store)
    result = pipeline.process_ticket_queue(temp_path)
    return result

@app.post("/api/surprise/upload")
async def upload_surprise_file(file: UploadFile = File(...)):
    """Uploads and processes a surprise file with format drift adaptation."""
    upload_dir = Path("d:/meridian/data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename
    
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    records, alerts = SurpriseDriftAdapter.adapt_file(file_path)
    
    # Process through pipeline
    temp_adapted = upload_dir / f"adapted_{file.filename}.json"
    temp_adapted.write_text(json.dumps(records), encoding="utf-8")

    pipeline = BreakdownPipeline(context_store=context_store)
    result = pipeline.process_ticket_queue(temp_adapted)

    return {
        "filename": file.filename,
        "records_parsed": len(records),
        "drift_alerts": alerts,
        "pipeline_result": result
    }

# ── Human Approval Gate Endpoints ─────────────────────────────────────────────

@app.get("/api/comms/pending")
def get_pending_comms():
    """Returns all notifications currently awaiting human gate approval."""
    return _read_jsonl(COMMS_PENDING_FILE)

@app.post("/api/comms/approve")
def approve_communications(req: ApproveRequest):
    """Approves pending communications and commits them to comms_sent.jsonl."""
    gate = ApprovalGate()
    if req.approve_all:
        count = gate.approve_all(approved_by=req.approved_by)
        return {"status": "success", "approved_count": count, "mode": "all"}
    elif req.message_id:
        count = gate.approve_single(req.message_id, approved_by=req.approved_by)
        return {"status": "success", "approved_count": count, "message_id": req.message_id}
    else:
        raise HTTPException(status_code=400, detail="Must specify message_id or approve_all=true")

@app.post("/api/comms/edit")
def edit_communication(req: EditCommsRequest):
    """Allows dispatcher to tweak drafted message before final approval."""
    pending = _read_jsonl(COMMS_PENDING_FILE)
    found = False
    for p in pending:
        if p.get("message_id") == req.message_id:
            p["body"] = req.edited_body
            p["is_edited"] = True
            p["edited_at"] = datetime.now().isoformat()
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail=f"Message {req.message_id} not found")
    _write_jsonl(COMMS_PENDING_FILE, pending)
    return {"status": "success", "message_id": req.message_id}

@app.post("/api/comms/reject")
def reject_communication(req: RejectRequest):
    """Rejects a drafted communication."""
    pending = _read_jsonl(COMMS_PENDING_FILE)
    new_pending = [p for p in pending if p.get("message_id") != req.message_id]
    if len(new_pending) == len(pending):
        raise HTTPException(status_code=404, detail="Message not found")
    _write_jsonl(COMMS_PENDING_FILE, new_pending)
    return {"status": "success", "rejected_id": req.message_id, "reason": req.reason}

# ── Fleet & Knowledge Explorer Endpoints ──────────────────────────────────────

@app.get("/api/fleet")
def get_fleet_directory():
    """Returns the full 100-vehicle fleet enriched with real-time maintenance signals."""
    fleet = []
    for reg, v in context_store.vehicles.items():
        maint = context_store.get_maintenance_summary(reg)
        fleet.append({
            "reg": reg,
            "model": v.get("model"),
            "year": v.get("year"),
            "bs_stage": v.get("bs_stage"),
            "home_hub": v.get("home_hub"),
            "status": v.get("status"),
            "engine_heater": v.get("engine_heater"),
            "is_overdue": maint.get("is_overdue", False),
            "latest_service": maint.get("latest_service_date"),
            "has_jugaad": maint.get("has_active_jugaad", False),
            "brake_work_30d": maint.get("brake_work_in_last_30d", False),
            "apex_incident": reg in context_store.apex_incident_vehicles
        })
    return fleet

@app.get("/api/topology")
def get_topology():
    """Returns road distances and geographic hub coordinates."""
    distances = [{"origin": k[0], "destination": k[1], "distance_km": v} for k, v in HUB_ROAD_DISTANCES.items()]
    return {
        "coordinates": HUB_COORDINATES,
        "distances": distances
    }

# ── Audit & Tests Endpoints ───────────────────────────────────────────────────

@app.get("/api/audit")
def get_audit_ledger():
    """Returns immutable hash-chained audit ledger records."""
    records = _read_jsonl(AUDIT_FILE)
    return {
        "total_records": len(records),
        "records": records[-100:]  # Return latest 100 entries for performance
    }

@app.post("/api/tests/run")
def run_automated_tests():
    """Runs pytest test suites and returns pass/fail metrics."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=45
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "passed": proc.returncode == 0
        }
    except Exception as e:
        return {"error": str(e), "passed": False}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
