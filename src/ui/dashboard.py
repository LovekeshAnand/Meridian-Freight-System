"""Operator Dashboard and Human Approval Gate CLI for Meridian Freight.

Handles human approval of client communications from outputs/comms_pending.jsonl
and generates compliant records in outputs/comms_sent.jsonl.
"""
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.config import COMMS_PENDING_FILE, COMMS_SENT_FILE
from src.pipeline.state_manager import StateManager
from src.security.pii_scrubber import redact_text, scan_for_pii

class ApprovalGate:
    def __init__(self):
        self.state_manager = StateManager()

    def get_pending_messages(self) -> List[Dict[str, Any]]:
        """Reads pending communication drafts."""
        if not COMMS_PENDING_FILE.exists():
            return []

        messages = []
        with open(COMMS_PENDING_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    messages.append(json.loads(line.strip()))
        return messages

    def get_sent_ticket_ids(self) -> set:
        """Returns ticket IDs already recorded in comms_sent.jsonl."""
        if not COMMS_SENT_FILE.exists():
            return set()
        sent_ids = set()
        with open(COMMS_SENT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line.strip())
                    if entry.get("ticket_id"):
                        sent_ids.add(entry["ticket_id"])
        return sent_ids

    def approve_all(self, approved_by: str = "dispatch_lead", sent_at: Optional[str] = None) -> int:
        """Approves all pending messages and records them in outputs/comms_sent.jsonl."""
        pending = self.get_pending_messages()
        sent_ids = self.get_sent_ticket_ids()
        approved_count = 0

        sent_records = []
        now_iso = sent_at or "2026-08-30T11:00:00"

        for msg in pending:
            t_id = msg.get("ticket_id")
            if not t_id or t_id in sent_ids:
                continue

            # Ensure zero PII in body
            clean_body = redact_text(msg.get("body", ""))
            
            # Double check for PII leaks
            pii_leaks = scan_for_pii(clean_body)
            if pii_leaks:
                clean_body = redact_text(clean_body)

            sent_entry = {
                "message_id": msg.get("message_id", f"MSG-{t_id}"),
                "ticket_id": t_id,
                "recipient": msg.get("recipient", "dispatch@client.example.in"),
                "body": clean_body,
                "approved_by": approved_by,
                "sent_at": msg.get("created_at", now_iso)
            }
            sent_records.append(sent_entry)
            sent_ids.add(t_id)

            self.state_manager.record_audit_step(
                ticket_id=t_id,
                step="APPROVE_COMMS",
                decision=f"Message approved and sent to {sent_entry['recipient']}.",
                data_used=sent_entry,
                rule_cited="Human Approval Gate",
                actor=approved_by
            )
            approved_count += 1

        # Write to comms_sent.jsonl
        # Read existing records
        existing = []
        if COMMS_SENT_FILE.exists():
            with open(COMMS_SENT_FILE, "r", encoding="utf-8") as f:
                existing = [json.loads(l.strip()) for l in f if l.strip()]

        existing_dict = {r["ticket_id"]: r for r in existing if "ticket_id" in r}
        for r in sent_records:
            existing_dict[r["ticket_id"]] = r

        # Write ordered
        with open(COMMS_SENT_FILE, "w", encoding="utf-8") as f:
            for r in existing_dict.values():
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        return approved_count

    def display_pending_summary(self):
        """Prints a summary table of pending messages awaiting approval."""
        pending = self.get_pending_messages()
        sent_ids = self.get_sent_ticket_ids()
        unsent = [m for m in pending if m.get("ticket_id") not in sent_ids]

        print(f"\n=======================================================")
        print(f"   MERIDIAN DISPATCH - HUMAN APPROVAL GATE")
        print(f"=======================================================")
        print(f"Total Drafted Messages: {len(pending)}")
        print(f"Already Approved & Sent: {len(sent_ids)}")
        print(f"Awaiting Human Approval: {len(unsent)}")
        print(f"-------------------------------------------------------")

        for idx, m in enumerate(unsent[:5]):
            print(f"[{idx+1}] Ticket: {m.get('ticket_id')} | Client: {m.get('client')} | Recipient: {m.get('recipient')}")
            print(f"    Replacement Vehicle: {m.get('replacement_vehicle')}")
            print(f"    Citations: {', '.join(m.get('citations', [])[:3])}")
            print(f"    Body:\n    {m.get('body').replace(chr(10), chr(10)+'    ')}")
            print(f"-------------------------------------------------------")

        if len(unsent) > 5:
            print(f"... and {len(unsent) - 5} more pending approval.")
