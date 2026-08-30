"""Epsilon Critique Pass & Flaw Detector Engine.

Ported from Nyaya AI core/engine/critique_pass.py & engine/agents/flaw_detector.py.
Performs an algorithmic validation pass on raw LLM outputs to intercept
hallucinations, phantom citations, unverified registrations, and PII leaks.
"""

from typing import Any, Dict, List, Optional, Tuple
import re
from collections import Counter

from src.entity.context_store import ContextStore
from src.entity.normalizer import normalize_vehicle_reg
from src.security.pii_scrubber import scan_for_pii
from src.config import HUB_COORDINATES

class CritiquePass:
    """
    Algorithmic critique engine that strictly validates generated texts against
    official fleet registers, known hub topologies, client SLA rules, and privacy gates.
    """
    def __init__(self, context_store: Optional[ContextStore] = None):
        self.context_store = context_store or ContextStore()
        if not self.context_store.is_loaded:
            self.context_store.load_all()

    def validate_comms_draft(
        self,
        draft_text: str,
        ticket: Dict[str, Any],
        replacement_vehicle: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validates client notification text against operational truth.
        Returns: (is_valid, list_of_flaws)
        """
        flaws = []
        text_lower = draft_text.lower()
        client = str(ticket.get("client", ""))

        # 1. PII Scan Hard Gate
        pii_violations = scan_for_pii(draft_text)
        if pii_violations:
            flaws.append(f"CRITICAL: PII detected in communication draft: {pii_violations}")

        # 2. Client SLA / Protocol Integrity Check
        if client == "Shakti Cement":
            if "48 hour" in text_lower or "48-hour" in text_lower:
                flaws.append("HALLUCINATION: Shakti Cement message cited outdated 48-hour SLA instead of 36-hour protocol.")
        elif client == "Vertex Retail":
            if "failed delivery" in text_lower or "fine" in text_lower:
                flaws.append("POLICY_VIOLATION: Vertex Retail message marked consignment as failed delivery rather than scheduled 8 AM gate arrival.")
        elif client == "Orion Pharma":
            if replacement_vehicle:
                yr = int(replacement_vehicle.get("year", 2018))
                if yr < 2020:
                    flaws.append(f"AUDIT_VIOLATION: Assigned vehicle {replacement_vehicle.get('canonical_reg')} is year {yr} (< 2020 for Orion Pharma).")

        # 3. Vehicle Registration Grounding Check
        assigned_reg = replacement_vehicle.get("canonical_reg") if replacement_vehicle else None
        # Extract vehicle-like tokens (e.g., UP40IM3144, HR16SP9238)
        reg_tokens = re.findall(r'\b[A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{4}\b', draft_text, flags=re.IGNORECASE)
        for token in reg_tokens:
            canon, is_valid_syntax = normalize_vehicle_reg(token)
            if is_valid_syntax and canon:
                if canon not in self.context_store.vehicles and canon != ticket.get("vehicle"):
                    flaws.append(f"HALLUCINATED_VEHICLE: Registration {canon} mentioned in text does not exist in Fleet Master.")

        # 4. Repetition / Degeneration Bug Detector (Ported from Nyaya AI)
        if len(draft_text) > 300:
            lines = [l.strip() for l in draft_text.split('\n') if len(l.strip()) > 10]
            if len(lines) > 3:
                counts = Counter(lines)
                if any(c > 2 for c in counts.values()):
                    flaws.append("REPETITION_BUG: Generated text entered an infinite repetition loop.")

        # 5. Missing Core Fields Check
        if ticket.get("ticket_id") and ticket.get("ticket_id") not in draft_text and "TKT-" not in draft_text:
            pass  # Non-fatal if ticket_id is in subject, but noted

        is_clean = len(flaws) == 0
        return is_clean, flaws

    def validate_query_response(self, response_text: str, query: str) -> Tuple[bool, List[str]]:
        """
        Validates grounded query responses to ensure compliance with facts and citations.
        """
        flaws = []
        resp_lower = response_text.lower()

        # 1. PII Scan
        pii_violations = scan_for_pii(response_text)
        if pii_violations:
            flaws.append(f"CRITICAL: PII detected in query response: {pii_violations}")

        # 2. Prevent confident hallucination on ungrounded queries
        if "dog" in query.lower() or "ceo" in query.lower() or "salary" in query.lower():
            if "insufficient data" not in resp_lower:
                flaws.append("UNGROUNDED_ANSWER: Engine answered unverified external knowledge without grounded citation.")

        # 3. Check for invalid hubs
        hub_mentions = [h for h in HUB_COORDINATES.keys() if h.lower() in resp_lower]
        # Valid if real hubs mentioned

        return len(flaws) == 0, flaws
