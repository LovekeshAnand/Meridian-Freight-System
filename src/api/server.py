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

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
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
    history: Optional[List[Dict[str, Any]]] = None

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
            "emails_loaded": len(context_store.emails)
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
    """Submits a natural language query directly to the Local LLM via Epsilon Engine."""
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

@app.post("/api/tickets/analyze-document")
async def analyze_ticket_document(
    file: UploadFile = File(None),
    raw_text: Optional[str] = Form(None),
    question: Optional[str] = Form(None)
):
    """
    Accepts ticket files in ANY format (JSON, CSV, TXT, Excel/Log) or raw text,
    parses them through the drift adapter, executes the breakdown pipeline,
    and runs the Local LLM to analyze the ticket and generate grounded resolutions.
    """
    upload_dir = Path("d:/meridian/data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    records = []
    drift_alerts = []
    filename = "pasted_text.txt"

    if file and file.filename:
        filename = file.filename
        file_path = upload_dir / filename
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        try:
            records, drift_alerts = SurpriseDriftAdapter.adapt_file(file_path)
        except Exception as e:
            drift_alerts.append(f"Format adaptation notice: {str(e)}")
    
    if not records and raw_text and raw_text.strip():
        # Try JSON parse first
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, list):
                records = parsed
            elif isinstance(parsed, dict):
                records = [parsed]
        except Exception:
            # Fallback to single raw incident text
            records = [{
                "ticket_id": f"TKT-RAW-{datetime.now().strftime('%H%M%S')}",
                "issue": raw_text.strip(),
                "created_at": datetime.now().isoformat()
            }]

    if not records:
        raise HTTPException(status_code=400, detail="Could not parse any valid incident or ticket records from the input.")

    # Process records through the Breakdown Pipeline
    temp_adapted = upload_dir / f"adapted_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}.json"
    temp_adapted.write_text(json.dumps(records), encoding="utf-8")

    pipeline = BreakdownPipeline(context_store=context_store)
    pipeline_res = pipeline.process_ticket_queue(temp_adapted, force_reprocess=True)

    all_wos = _read_jsonl(WORK_ORDERS_FILE)
    all_quars = _read_jsonl(QUARANTINE_FILE)
    all_comms = _read_jsonl(COMMS_PENDING_FILE)

    # Now run Local LLM Analysis for each ticket to provide deep contextual reasoning
    processed_analyses = []
    for i, t in enumerate(records):
        tkt_id = t.get("ticket_id", f"TKT-{i+1}")
        # Find matching work order or quarantine from ledger
        matched_wo = next((w for w in reversed(all_wos) if w.get("ticket_id") == tkt_id), None)
        matched_quarantine = next((q for q in reversed(all_quars) if q.get("ticket_id") == tkt_id), None)
        matched_comms = next((c for c in reversed(all_comms) if c.get("ticket_id") == tkt_id), None)

        rep_veh = matched_wo.get("replacement_vehicle") if matched_wo else None
        assigned_hub = matched_wo.get("assigned_hub") if matched_wo else t.get("origin_hub")
        
        # Build prompt for LLM explanation
        llm_prompt = (
            f"An emergency breakdown ticket was processed by the dispatch automation system:\n"
            f"- Incident ID: {tkt_id}\n"
            f"- Client: {t.get('client')}\n"
            f"- Broken Vehicle: {t.get('vehicle')}\n"
            f"- Trip Route: {t.get('origin_hub')} to {t.get('destination')} (Breakdown Distance: {t.get('km_from_origin_hub')} km from origin hub)\n"
            f"- Incident Defect: {t.get('issue')}\n"
        )
        if rep_veh:
            llm_prompt += (
                f"- Automated Resolution: Assigned Replacement Truck **{rep_veh}** from **{assigned_hub}** hub.\n"
                f"- Selection Rationale: {matched_wo.get('selection_rationale')}\n"
            )
        elif matched_quarantine:
            llm_prompt += f"- Ticket Quarantined: Reason: {matched_quarantine.get('quarantine_reason', matched_quarantine.get('reason'))}\n"

        llm_prompt += (
            f"\nAs Rajender's Brain, provide a comprehensive dispatch resolution summary:\n"
            f"1. Explain why replacement vehicle {rep_veh or 'selection'} was dispatched from {assigned_hub} under RULE-DISP-01 (50km Origin Rule).\n"
            f"2. Confirm SLA compliance for {t.get('client')} (e.g. 36-hour window).\n"
            f"3. Note any policy violations found with the broken truck ({t.get('vehicle')}).\n"
            f"4. Provide concrete operational instructions for field teams."
        )

        llm_res = local_llm.query(llm_prompt)

        processed_analyses.append({
            "ticket": t,
            "work_order": matched_wo,
            "quarantine": matched_quarantine,
            "comms_pending": matched_comms,
            "llm_analysis": llm_res.get("answer"),
            "model_used": llm_res.get("model_used", "qwen2.5:3b"),
            "citations": llm_res.get("citations", []),
            "rule_code": llm_res.get("rule_code"),
            "rule_name": llm_res.get("rule_name"),
            "vehicle_data": llm_res.get("vehicle_data")
        })

    return {
        "filename": filename,
        "total_tickets": len(records),
        "drift_alerts": drift_alerts,
        "pipeline_result": pipeline_res,
        "analyses": processed_analyses
    }

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
