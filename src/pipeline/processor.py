"""Main Breakdown-to-Resolution Pipeline Processor — Hardened Edition.

Executes the 7-step resolution workflow with universal crash guard:
1. Validate & Quarantine (coercion-first, never crashes on bad input)
2. Context Enrichment
3. Expert Rule Evaluation
4. Eligible Replacement Selection (structured result with full decision trail)
5. Work Order Generation (outputs/work_orders.jsonl)
6. Client Communication Drafting (outputs/comms_pending.jsonl)
7. Immutable Audit Trail (audit/audit.jsonl)

Key hardening:
- Each ticket is processed in its own try/except
- A ticket that slips validation and still raises will be emergency-quarantined
- All file writes use atomic tmp→rename pattern
- Queue files that fail to load are handled gracefully
- SIGINT/KeyboardInterrupt produces a clean exit summary
"""
import json
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import (
    COMMS_PENDING_FILE,
    QUARANTINE_FILE,
    TICKETS_FILE,
    WORK_ORDERS_FILE,
)
from src.entity.context_store import ContextStore
from src.entity.normalizer import normalize_client_name, normalize_hub_name
from src.llm.comms_generator import CommsGenerator
from src.pipeline.state_manager import StateManager
from src.pipeline.validator import TicketValidator
from src.rules.expert_rules import ExpertRulesEngine
from src.rules.vehicle_selector import VehicleSelector
from src.security.pii_scrubber import redact_record
from src.observability import logger as log


def _load_queue_file(queue_path: Path) -> tuple[List[Any], Optional[str]]:
    """
    Loads a ticket queue file with graceful error handling.
    Supports JSON array or JSONL format.
    Returns (records, error_message_or_None).
    """
    if not queue_path.exists():
        return [], f"Queue file not found: {queue_path}"

    try:
        content = queue_path.read_text(encoding="utf-8-sig", errors="replace").strip()
    except Exception as e:
        return [], f"Cannot read queue file: {e}"

    if not content:
        return [], "Queue file is empty."

    # Try JSON array first
    if content.startswith("["):
        try:
            records = json.loads(content)
            if isinstance(records, list):
                return records, None
        except json.JSONDecodeError as e:
            log.warn(f"JSON array parse failed for {queue_path.name}: {e}; trying JSONL.")

    # Fallback: JSONL
    records = []
    for lineno, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                records.append(obj)
        except json.JSONDecodeError:
            log.warn(f"Skipped malformed JSONL line {lineno} in {queue_path.name}.")

    if not records:
        return [], "Queue file contains no parseable records."
    return records, None


class BreakdownPipeline:
    def __init__(self, context_store: Optional[ContextStore] = None, install_signal_handlers: bool = False):
        self.context_store = context_store or ContextStore()
        if not self.context_store.is_loaded:
            self.context_store.load_all()

        self.rules_engine = ExpertRulesEngine()
        self.vehicle_selector = VehicleSelector(self.context_store)
        self.comms_generator = CommsGenerator()
        self.state_manager = StateManager()

        # Graceful SIGINT handler (only installed in standalone CLI scripts, never inside web servers)
        self._interrupted = False
        if install_signal_handlers:
            try:
                signal.signal(signal.SIGINT, self._handle_sigint)
            except (ValueError, OSError):
                pass

    def _handle_sigint(self, signum, frame):
        """Handles Ctrl+C gracefully — allows current ticket to finish, then stops."""
        log.alert("SIGINT received — pipeline will stop after current ticket finishes.", alert_type="SIGINT")
        self._interrupted = True

    def process_ticket_queue(self, queue_file_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Processes the breakdown ticket queue end-to-end with idempotency.
        Crashes are quarantined per-ticket; the loop never stops.
        """
        target_path = queue_file_path or TICKETS_FILE
        log.info(f"Processing queue: {target_path}")

        raw_tickets, load_error = _load_queue_file(target_path)
        if load_error:
            log.error(f"Queue load failed: {load_error}")
            return {"status": "error", "message": load_error}

        log.info(f"Loaded {len(raw_tickets)} raw records from queue.")

    def process_ticket_queue(self, queue_path: Path, force_reprocess: bool = False) -> Dict[str, Any]:
        """
        Executes the full pipeline on a given ticket queue file.
        Idempotent: Skips tickets that were already processed in previous runs unless force_reprocess is True.
        """
        raw_tickets, err = _load_queue_file(queue_path)
        if err and not raw_tickets:
            log.warn(f"Queue file issue: {err}")
            return {"status": "error", "error": err, "total_in_queue": 0, "work_orders_generated": 0}

        seen_ticket_ids: set = set()
        valid_processed: List[str] = []
        quarantined: List[Dict[str, Any]] = []
        work_orders: List[Dict[str, Any]] = []
        pending_comms: List[Dict[str, Any]] = []

        for raw_ticket in raw_tickets:
            if self._interrupted:
                break
            try:
                self._process_single_ticket(
                    raw_ticket,
                    seen_ticket_ids,
                    valid_processed,
                    quarantined,
                    work_orders,
                    pending_comms,
                    force_reprocess=force_reprocess
                )
            except KeyboardInterrupt:
                self._interrupted = True
                log.alert("KeyboardInterrupt during ticket processing. Flushing safe outputs.", alert_type="SIGINT")
                break
            except Exception as exc:
                # Emergency quarantine — this ticket raised unexpectedly after validation
                t_id = str(raw_ticket.get("ticket_id", "UNKNOWN")).strip() or "UNKNOWN"
                log.error(
                    f"Unexpected pipeline crash on ticket {t_id} — emergency quarantine.",
                    ticket_id=t_id, exc=exc,
                )
                emergency_entry = {
                    "ticket_id": t_id,
                    "raw_record": redact_record(raw_ticket),
                    "quarantine_reason": f"EMERGENCY: Unexpected pipeline error: {type(exc).__name__}: {exc}",
                    "quarantined_at": datetime.now().isoformat(),
                }
                quarantined.append(emergency_entry)
                try:
                    self.state_manager.record_audit_step(
                        ticket_id=t_id, step="EMERGENCY_QUARANTINE",
                        decision=emergency_entry["quarantine_reason"],
                        data_used=emergency_entry,
                        rule_cited="pipeline_crash_guard",
                    )
                except Exception:
                    pass  # Don't let audit write crash the flush

        # Flush all outputs
        self._write_jsonl(WORK_ORDERS_FILE, work_orders)
        self._write_jsonl(COMMS_PENDING_FILE, pending_comms)
        self._write_jsonl(QUARANTINE_FILE, quarantined)

        summary = {
            "status": "success" if not self._interrupted else "interrupted",
            "total_in_queue": len(raw_tickets),
            "valid_processed": len(valid_processed),
            "quarantined": len(quarantined),
            "work_orders_generated": len(work_orders),
            "comms_pending": len(pending_comms),
        }
        log.info("Pipeline run complete.", **summary)
        return summary

    def _process_single_ticket(
        self,
        raw_ticket: Any,
        seen_ticket_ids: set,
        valid_processed: List,
        quarantined: List,
        work_orders: List,
        pending_comms: List,
        force_reprocess: bool = False
    ):
        """Processes one ticket through all 7 steps."""
        ticket_id = str(raw_ticket.get("ticket_id", "")).strip() if isinstance(raw_ticket, dict) else ""

        # ── Deduplication ──────────────────────────────────────────────────────
        if ticket_id and ticket_id in seen_ticket_ids:
            self.state_manager.record_audit_step(
                ticket_id=ticket_id, step="DEDUPLICATION",
                decision=f"Duplicate in queue — skipped.",
                data_used={"ticket_id": ticket_id},
                rule_cited="CANDIDATE_README.md:Rule 1",
            )
            return

        # Skip if already processed in a previous run (idempotency guard, unless forced)
        if not force_reprocess and ticket_id and self.state_manager.is_ticket_processed(ticket_id):
            log.info(f"Ticket {ticket_id} already processed in previous run — skipping.", ticket_id=ticket_id)
            return

        if ticket_id:
            seen_ticket_ids.add(ticket_id)

        # ── Step 1: Validate ───────────────────────────────────────────────────
        val_result = TicketValidator.validate_ticket(raw_ticket)
        if not val_result.is_valid:
            q_entry = {
                "ticket_id": ticket_id or "CORRUPT_UNKNOWN",
                "raw_record": redact_record(raw_ticket),
                "quarantine_reason": val_result.quarantine_reason,
                "quarantined_at": datetime.now().isoformat(),
            }
            quarantined.append(q_entry)
            self.state_manager.record_audit_step(
                ticket_id=ticket_id or "CORRUPT_UNKNOWN", step="QUARANTINE",
                decision=f"Quarantined: {val_result.quarantine_reason}",
                data_used=q_entry,
                rule_cited="CANDIDATE_README.md:Step 1 (Quarantine)",
            )
            return

        ticket = val_result.sanitized_ticket
        ticket_id = ticket["ticket_id"]  # Use coerced canonical ID

        self.state_manager.record_audit_step(
            ticket_id=ticket_id, step="VALIDATE",
            decision="Ticket passed validation (coercion applied where needed).",
            data_used={
                "ticket_id": ticket_id,
                "vehicle": ticket.get("vehicle"),
                "warnings": val_result.warnings,
            },
            rule_cited="Step 1: Validation",
        )

        # ── Step 2: Context Enrichment ─────────────────────────────────────────
        vehicle_info = self.context_store.get_vehicle(ticket["vehicle"])
        driver_info = self.context_store.get_driver(ticket.get("driver_id", ""))
        maint_info = self.context_store.get_maintenance_summary(ticket["vehicle"], ticket["created_at"])

        self.state_manager.record_audit_step(
            ticket_id=ticket_id, step="ENRICH",
            decision="Enriched with Fleet Master, Driver Roster (PII-masked), Maintenance history.",
            data_used={"vehicle_master": vehicle_info, "driver": driver_info, "maintenance": maint_info},
            rule_cited="Step 2: Context Enrichment",
        )

        # ── Step 3: Expert Rule Evaluation ────────────────────────────────────
        try:
            t_date = datetime.strptime(str(ticket["created_at"]).split("T")[0], "%Y-%m-%d")
        except Exception:
            t_date = datetime(2026, 8, 30)

        sla_eval = self.rules_engine.get_client_sla_and_rules(
            client=ticket.get("client", ""),
            ticket_date=t_date,
            eta_hours=24.0,
            dest_hub=ticket.get("destination", ""),
        )
        self.state_manager.record_audit_step(
            ticket_id=ticket_id, step="RULE_EVAL",
            decision=f"SLA={sla_eval['sla_hours']}h. Instructions: {sla_eval['special_instructions']}",
            data_used=sla_eval,
            rule_cited=", ".join(sla_eval.get("citations", [])) or "dispatcher_interview.txt",
        )

        # ── Step 4: Select Replacement Vehicle ────────────────────────────────
        selection = self.vehicle_selector.select_replacement_vehicle(ticket)
        repl_veh = selection.selected
        all_citations = sorted(set(sla_eval.get("citations", []) + selection.citations))

        self.state_manager.record_audit_step(
            ticket_id=ticket_id, step="SELECT_REPLACEMENT",
            decision=selection.rationale,
            data_used={
                "selected": repl_veh,
                "hub_strategy": selection.hub_search_strategy,
                "failure_mode": selection.failure_mode,
                "rejections": [
                    {"vehicle": r.vehicle_reg, "rule": r.rule_failed, "reason": r.detail}
                    for r in selection.rejected_candidates[:10]
                ],
            },
            rule_cited=", ".join(selection.citations) if selection.citations else "vehicle_selector",
        )

        # ── Step 5: Work Order ─────────────────────────────────────────────────
        repl_reg = repl_veh.get("canonical_reg") if repl_veh else "UNASSIGNED"
        wo_entry = {
            "work_order_id": f"WO-{ticket_id}",
            "ticket_id": ticket_id,
            "vehicle_reg": ticket["vehicle"],
            "replacement_vehicle_reg": repl_reg,
            "hub_used": selection.hub_used,
            "hub_strategy": selection.hub_search_strategy,
            "failure_mode": selection.failure_mode,
            "created_at": ticket.get("created_at"),
            "citations": all_citations,
        }
        work_orders.append(wo_entry)
        self.state_manager.record_audit_step(
            ticket_id=ticket_id, step="GENERATE_WORK_ORDER",
            decision=f"WO-{ticket_id}: {ticket['vehicle']} → replacement {repl_reg}.",
            data_used=wo_entry,
            rule_cited="Step 5: Work Order Outbox",
        )

        # ── Step 6: Draft Client Comms ────────────────────────────────────────
        draft_comms = self.comms_generator.draft_client_message(
            ticket=ticket,
            replacement_vehicle=repl_veh,
            rationale=selection.rationale,
            citations=all_citations,
        )
        pending_comms.append(draft_comms)
        self.state_manager.record_audit_step(
            ticket_id=ticket_id, step="DRAFT_COMMS",
            decision=f"Draft queued for {draft_comms.get('recipient', 'client')} — pending human approval.",
            data_used=draft_comms,
            rule_cited="Step 6: Client Notification Gate",
        )

        valid_processed.append(ticket_id)

    def _write_jsonl(self, file_path: Path, records: List[Dict[str, Any]]):
        """Writes records to a JSONL file using atomic tmp→rename pattern."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = file_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                for rec in records:
                    f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                f.flush()
                os.fsync(f.fileno())
            # Atomic rename
            os.replace(tmp_path, file_path)
        except Exception as e:
            log.error(f"Failed to write {file_path.name}: {e}", exc=e)
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
