"""Client Communication Drafter and Notification Generator — Powered by Epsilon Engine.

Generates professional, client-tailored breakdown notifications with full context,
exact citations, and ZERO raw personal data (enforcing the Hard Gate).
Uses the Epsilon Engine with deterministic safety fallback.
"""
from typing import Any, Dict, List, Optional

from src.security.pii_scrubber import redact_text
from src.llm.local_llm import LocalLLM

CLIENT_RECIPIENTS = {
    "Shakti Cement": "dispatch@shakticement.example.in",
    "Apex Chemicals": "stores@apexchem.example.in",
    "Vertex Retail": "logistics@vertexretail.example.in",
    "Orion Pharma": "scm@orionpharma.example.in",
    "Internal": "ops@meridianfreight.example.in",
}

class CommsGenerator:
    def __init__(self, local_llm: Optional[LocalLLM] = None):
        self.llm = local_llm or LocalLLM()

    def draft_client_message(
        self,
        ticket: Dict[str, Any],
        replacement_vehicle: Optional[Dict[str, Any]],
        rationale: str,
        citations: List[str]
    ) -> Dict[str, Any]:
        """
        Drafts a structured client notification for comms_pending.jsonl.
        Guarantees zero raw personal data and deterministic outputs via Epsilon Engine.
        """
        ticket_id = ticket.get("ticket_id", "UNKNOWN")
        client = ticket.get("client", "Internal")
        recipient = CLIENT_RECIPIENTS.get(client, "ops@meridianfreight.example.in")
        repl_reg = replacement_vehicle.get("canonical_reg", "a replacement vehicle") if replacement_vehicle else "roadside support team"

        # Dispatch generation through Epsilon Engine
        epsilon_result = self.llm.generate_comms(
            ticket=ticket,
            replacement_vehicle=replacement_vehicle,
            rationale=rationale,
            citations=citations
        )
        
        body_content = epsilon_result.get("result", "")
        sanitized_body = redact_text(body_content)

        msg_id = f"MSG-{ticket_id}"
        created_at = ticket.get("created_at", "2026-08-30T10:00:00")

        return {
            "message_id": msg_id,
            "ticket_id": ticket_id,
            "client": client,
            "recipient": recipient,
            "subject": f"Meridian Operational Update: Ticket {ticket_id} [{client}]",
            "body": sanitized_body,
            "replacement_vehicle": repl_reg,
            "citations": sorted(list(set(citations))),
            "created_at": created_at,
            "metadata": epsilon_result.get("metadata", {})
        }
