"""Epsilon Context Injector - Anti-Hallucination Fact & Memory Curation Engine.

Ported from Nyaya AI core/engine/memory_retrieval.py & agents/orchestrator.py.
Extracts grounded evidence from ContextStore and structures it into
explicit verified context blocks. Forces the LLM to ground only on supplied facts.
"""

from typing import Any, Dict, List, Optional
from src.entity.context_store import ContextStore
from src.entity.normalizer import normalize_vehicle_reg, normalize_client_name, normalize_hub_name

class ContextInjector:
    """
    Builds structured, verified context payloads for LLM generations to prevent hallucinations.
    """
    def __init__(self, context_store: Optional[ContextStore] = None):
        self.context_store = context_store or ContextStore()
        if not self.context_store.is_loaded:
            self.context_store.load_all()

    def build_ticket_grounding_block(
        self,
        ticket: Dict[str, Any],
        replacement_vehicle: Optional[Dict[str, Any]] = None,
        rationale: str = "",
        citations: Optional[List[str]] = None
    ) -> str:
        """
        Creates an immutable, strictly formatted context block from official records.
        """
        client = normalize_client_name(ticket.get("client", "Internal"))
        broken_reg, _ = normalize_vehicle_reg(ticket.get("vehicle", ""))
        origin_hub = normalize_hub_name(ticket.get("origin_hub", "Gurgaon"))
        dest_hub = normalize_hub_name(ticket.get("destination", "Gurgaon"))
        
        broken_info = self.context_store.get_vehicle(broken_reg) if broken_reg else None
        maint_summary = self.context_store.get_maintenance_summary(broken_reg) if broken_reg else {}
        
        parts = [
            "=== VERIFIED OPERATIONAL FACTS (GROUND TRUTH - DO NOT INVENT) ===",
            f"Ticket ID: {ticket.get('ticket_id')}",
            f"Client Name: {client}",
            f"Route: {origin_hub} -> {dest_hub} (Distance from origin: {ticket.get('km_from_origin_hub', 0)} km)",
            f"Incident/Defect: {ticket.get('issue', 'Mechanical issue')} (Severity: {ticket.get('severity', 'HIGH')})",
        ]

        if broken_info:
            parts.append(
                f"Broken Vehicle: {broken_reg} [Model: {broken_info.get('model')}, Year: {broken_info.get('year')}, "
                f"BS Stage: {broken_info.get('bs_stage')}, Home Hub: {broken_info.get('home_hub')}] (Source: fleet_master.csv)"
            )
        else:
            parts.append(f"Broken Vehicle: {broken_reg} (Source: ticket queue)")

        if maint_summary:
            parts.append(
                f"Maintenance Record: Last Service={maint_summary.get('latest_service_date')}, "
                f"Overdue={maint_summary.get('is_overdue')}, Brake Work 30d={maint_summary.get('brake_work_in_last_30d')}, "
                f"Active Jugaad={maint_summary.get('has_active_jugaad')} (Source: maintenance_log.xlsx)"
            )

        if replacement_vehicle:
            rep_reg = replacement_vehicle.get("canonical_reg", "UNASSIGNED")
            parts.append(
                f"Assigned Replacement Vehicle: {rep_reg} [Model: {replacement_vehicle.get('model')}, "
                f"Year: {replacement_vehicle.get('year')}, BS Stage: {replacement_vehicle.get('bs_stage')}, "
                f"Home Hub: {replacement_vehicle.get('home_hub')}] (Source: fleet_master.csv)"
            )
        else:
            parts.append("Assigned Replacement Vehicle: None Available / Field Team Escalated")

        if rationale:
            parts.append(f"Assignment Rationale: {rationale}")

        if citations:
            parts.append(f"Governing Citations: {', '.join(sorted(list(set(citations))))}")

        parts.append("=== END VERIFIED FACTS ===")
        return "\n".join(parts)

    def build_query_grounding_block(self, query: str, candidate_citations: List[str]) -> str:
        """
        Creates a citation-rich context block for natural language queries.
        """
        parts = [
            "=== SYSTEM GROUNDING FACTS & OPERATIONAL POLICIES ===",
            "1. Shakti Cement: Strict 36-hour delivery protocol overriding legacy 48h paper contract (Citation: dispatcher_interview.txt:L22, emails/thread_01_shakti_sla.txt).",
            "2. Delhi NCR Winter Restriction: BS6 only allowed Oct-Feb for Delhi, Gurgaon, Faridabad, Noida routes under GRAP rules (Citation: dispatcher_interview.txt:L14).",
            "3. Hill Route Policy (Rudrapur, Nainital): Requires engine heater for cold starts and 0 brake jobs within prior 30 days (Citation: dispatcher_interview.txt:L18).",
            "4. Guddu Jugaad Rule: Temporary roadside repairs have a strict 7-day clock for permanent overhaul; vehicle locked to home region (Citation: dispatcher_interview.txt:L42).",
            "5. Overdue Grounding: Vehicles >30 days past maintenance due date are grounded (Citation: dispatcher_interview.txt:L38).",
            "6. 50km Rule: Breakdown <=50km from origin hub uses origin hub; >50km searches nearest hub (Citation: dispatcher_interview.txt:L36-37).",
            "7. Vertex Retail: Ludhiana gate shuts 6:00 PM; holds until 8:00 AM next day (Citation: dispatcher_interview.txt:L24).",
            "8. Apex Chemicals: If a vehicle had an incident on an Apex run, mandatory rotation with a different vehicle on next run (Citation: dispatcher_interview.txt:L26).",
            "9. Orion Pharma: Vehicles must be model year 2020 or newer with continuous cold chain / refrigeration (Citation: dispatcher_interview.txt:L28).",
            "10. Monsoon East Route Buffer: July-Sept routes east of Lucknow require +20% ETA buffer (Citation: dispatcher_interview.txt:L32).",
            "11. Driver Night Roster: Drivers with <6 months tenure must not drive solo at night (Citation: dispatcher_interview.txt:L46).",
            f"Applicable Citations: {', '.join(candidate_citations) if candidate_citations else 'None'}",
            "=== STRICT RULE: IF INFORMATION IS NOT IN THE ABOVE LIST, STATE 'Insufficient data' ==="
        ]
        return "\n".join(parts)
