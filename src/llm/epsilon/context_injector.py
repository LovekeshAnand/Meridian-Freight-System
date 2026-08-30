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
        Creates a citation-rich context block for natural language queries with dynamic entity injection.
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
        ]

        # Dynamic Fleet Maintenance & Repair Telemetry Injection
        q_low = query.lower()
        needs_fleet_maint = any(w in q_low for w in ["repair", "repaired", "checked", "overdue", "maintenance", "grounded", "jugaad", "broken", "list", "which", "fast", "schedule", "when"])
        
        if needs_fleet_maint:
            overdue_list = []
            jugaad_list = []
            brake_list = []
            for r, v in self.context_store.vehicles.items():
                m = self.context_store.get_maintenance_summary(r)
                if m.get("is_overdue"):
                    overdue_list.append(f"{r} ({v.get('model')}, Hub: {v.get('home_hub')}, Last Service: {m.get('latest_service_date')})")
                if m.get("has_active_jugaad"):
                    jugaad_list.append(f"{r} ({v.get('model')}, Hub: {v.get('home_hub')}, Patch Date: {m.get('jugaad_date')}, 7-Day Window)")
                if m.get("brake_work_in_last_30d"):
                    brake_list.append(f"{r} ({v.get('model')}, Hub: {v.get('home_hub')})")

            parts.append("=== FLEET MAINTENANCE & REPAIR TELEMETRY SUMMARY ===")
            if jugaad_list:
                parts.append(f"Vehicles with Temporary Guddu Jugaad (Can be dispatched locally in home region immediately; must have permanent repair within 7 days): {'; '.join(jugaad_list[:10])}")
            else:
                parts.append("Vehicles with Temporary Guddu Jugaad: None active currently.")
            
            if overdue_list:
                parts.append(f"Vehicles Grounded for Overdue Service (>150 days since last service, strictly grounded until routine service is completed): {'; '.join(overdue_list)} (Total {len(overdue_list)} vehicles overdue)")
            
            if brake_list:
                parts.append(f"Vehicles with Recent Brake Work (<30 days, cannot take hill routes, flat runs only): {'; '.join(brake_list[:10])}")
            parts.append("====================================================")

        # Dynamic Entity Resolution (Specific vehicle mentioned in query)
        from src.entity.normalizer import extract_vehicle_reg_from_text, normalize_driver_id
        norm_veh, is_reg = extract_vehicle_reg_from_text(query)
        if is_reg and norm_veh:
            veh = self.context_store.get_vehicle(norm_veh)
            maint = self.context_store.get_maintenance_summary(norm_veh)
            if veh:
                parts.append("=== SPECIFIC VEHICLE TELEMETRY & MAINTENANCE LOG ===")
                parts.append(
                    f"Vehicle: {norm_veh} | Model: {veh.get('model')} | Year: {veh.get('year')} | "
                    f"BS Stage: {veh.get('bs_stage')} | Home Hub: {veh.get('home_hub')} | Status: {veh.get('status')} | Engine Heater: {veh.get('engine_heater')}"
                )
                if maint:
                    parts.append(
                        f"Maintenance History for {norm_veh}: Last Routine Service={maint.get('latest_service_date')} | "
                        f"Service Overdue={maint.get('is_overdue')} (Grounded under RULE-DISP-05 if True) | "
                        f"Brake Work in Last 30d={maint.get('brake_work_in_last_30d')} | "
                        f"Active Temporary Guddu Jugaad={maint.get('has_active_jugaad')} (Lock to home region if True)"
                    )
                parts.append("====================================================")

        # Dynamic Driver Resolution
        norm_drv = normalize_driver_id(query)
        if norm_drv and norm_drv in self.context_store.drivers:
            drv = self.context_store.drivers[norm_drv]
            parts.append(f"Driver Profile {norm_drv}: Name={drv.get('name')}, Base Hub={drv.get('home_hub')}, Joined={drv.get('joining_date')}")

        parts.append(f"Applicable Citations: {', '.join(candidate_citations) if candidate_citations else 'None'}")
        parts.append("=== INSTRUCTIONS: Answer the question concisely and thoroughly using the operational facts above. If not in facts, state 'Insufficient data'. ===")
        return "\n".join(parts)
