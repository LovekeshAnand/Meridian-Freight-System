"""Epsilon Context Injector - Anti-Hallucination Fact & Targeted Context Curation Engine.

Extracts grounded evidence from ContextStore and structures it into
explicit verified context blocks. Filters context precisely to eliminate noise
and forces the LLM to ground strictly on domain facts.
"""

from typing import Any, Dict, List, Optional
import re
from src.entity.context_store import ContextStore
from src.entity.normalizer import (
    normalize_vehicle_reg,
    normalize_client_name,
    normalize_hub_name,
    extract_vehicle_reg_from_text,
    normalize_driver_id
)

class ContextInjector:
    """
    Builds structured, targeted context payloads for LLM generations to prevent hallucinations.
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
        Creates a targeted, citation-rich context block for natural language queries with domain filtering.
        """
        q_low = query.lower()
        parts = ["=== VERIFIED OPERATIONAL RULES & POLICIES (Preserved from 18y Dispatch Memory) ==="]

        # 1. 50km Origin Hub Proximity Heuristic
        if "50" in q_low or "km" in q_low or "breakdown" in q_low or "outside" in q_low or "nearest" in q_low:
            parts.append(
                "• 50KM ORIGIN HUB RULE (RULE-DISP-01): If a breakdown occurs within 50 km (<= 50 km) of its origin hub, "
                "the replacement vehicle MUST be dispatched directly from that ORIGIN HUB. "
                "If the breakdown occurs beyond 50 km (> 50 km, e.g. 54 km), the dispatch system is NOT restricted to the origin hub and evaluates the nearest hub with available vehicles. (Citation: dispatcher_interview.txt:L36-37)"
            )

        # 2. Shakti Cement Protocol
        if "shakti" in q_low or "cement" in q_low or "36" in q_low or "48" in q_low or "contract" in q_low or "precedence" in q_low:
            parts.append(
                "• SHAKTI CEMENT 36-HOUR PROTOCOL (RULE-CLI-01 / PRECEDENCE-01): While the legacy 2021 master service agreement mentions 48 hours, "
                "active operational agreement with plant management firmly established a strict 36-hour delivery commitment. "
                "Under Meridian Freight Precedence Rule 1 (Active Operational Email Agreements supersede legacy contracts), "
                "all dispatches must be resolved and planned to the 36-hour window. (Citation: dispatcher_interview.txt:L22, emails/thread_01_shakti_sla.txt:L5-7)"
            )

        # 3. Vertex Retail Gate Hold Protocol
        if "vertex" in q_low or "ludhiana" in q_low or "gate" in q_low or "6" in q_low or "hold" in q_low:
            parts.append(
                "• VERTEX RETAIL LUDHIANA GATE RULE (RULE-CLI-02): The Ludhiana warehouse gate closes sharp at 6:00 PM. "
                "If computed arrival is past 6:00 PM (e.g. 6:45 PM), the driver MUST be directed to HOLD OVERNIGHT at the last authorized halt "
                "and deliver at 8:00 AM the next morning. It must NEVER be marked as a failed delivery in the system to prevent automatic contractual penalties. (Citation: dispatcher_interview.txt:L24, emails/thread_09_vertex_gate.txt:L9-12)"
            )

        # 4. Driver Night Pairing Rule
        if "driver" in q_low or "drv" in q_low or "night" in q_low or "solo" in q_low or "tenure" in q_low or "month" in q_low or "hired" in q_low or "joined" in q_low:
            parts.append(
                "• DRIVER TENURE NIGHT ROSTER RULE (RULE-DRV-01): Drivers with less than 6 months tenure at Meridian Freight (e.g. 2 or 3 months) "
                "must NEVER drive solo on night runs (after 8:00 PM, such as a 9:30 PM or 11:30 PM leg). "
                "They are allowed to drive solo during daytime, but for night driving they MUST be paired with an experienced senior co-driver. (Citation: dispatcher_interview.txt:L46, emails/thread_24_internal_nightroster.txt:L5-8)"
            )

        # 5. Monsoon Eastern Route Buffer Rule
        if "monsoon" in q_low or "august" in q_low or "july" in q_low or "september" in q_low or "lucknow" in q_low or "buffer" in q_low or "eta" in q_low:
            parts.append(
                "• MONSOON EASTERN ROUTE +20% BUFFER (RULE-DISP-07): During monsoon months (July to September), "
                "any dispatch route traveling east of Lucknow (e.g. Lucknow to Gorakhpur) requires adding a mandatory +20% time buffer "
                "to total computed transit times (Base Travel Time + Transfer Time) * 1.20 upfront due to waterlogging and diversions. (Citation: dispatcher_interview.txt:L32, emails/thread_23_internal_monsoon.txt:L8-10)"
            )

        # 6. Apex Chemicals Rotation Rule
        if "apex" in q_low or "rotation" in q_low:
            parts.append(
                "• APEX CHEMICALS INCIDENT ROTATION (RULE-CLI-03): Apex Chemicals logs vehicle plates. "
                "If a vehicle encounters any breakdown or incident on an Apex transit, that exact vehicle cannot be used for the immediate next Apex shipment and must be rotated. (Citation: dispatcher_interview.txt:L26, emails/thread_13_apex_rotation.txt:L9-12)"
            )

        # 7. Orion Pharma Age & Cold Chain Rule
        if "orion" in q_low or "pharma" in q_low or "cold" in q_low or "refrigerat" in q_low or "vaccine" in q_low or "2019" in q_low:
            parts.append(
                "• ORION PHARMA 2020+ & REFRIGERATION RULE (RULE-CLI-04): Consignments strictly require vehicles manufactured in 2020 OR NEWER (e.g. 2020, 2021, 2022). "
                "A 2019 or older vehicle is NOT compliant and will FAIL pharma audit even if refrigerated. Continuous refrigeration and verified RC copy are strictly required. (Citation: dispatcher_interview.txt:L28, emails/thread_17_orion_age.txt:L9-12)"
            )

        # 8. Delhi NCR Winter BS4 Ban
        if "delhi" in q_low or "ncr" in q_low or "bs4" in q_low or "bs6" in q_low or "grap" in q_low or "november" in q_low:
            parts.append(
                "• DELHI NCR WINTER BS4 BAN (RULE-DISP-02): From October to February (including November), BS4 commercial vehicles are strictly prohibited "
                "on all routes touching Delhi NCR (Delhi, Gurgaon, Faridabad, Noida) under GRAP pollution regulations; BS6 vehicles only. (Citation: dispatcher_interview.txt:L14)"
            )

        # 9. Hill Route Engine Heater & Brake Rule
        if "hill" in q_low or "rudrapur" in q_low or "nainital" in q_low or "heater" in q_low or "brake" in q_low:
            parts.append(
                "• HILL ROUTE WINTER HEATER & BRAKE POLICY (RULE-DISP-03 & RULE-DISP-04):\n"
                "  1) ENGINE HEATER REQUIREMENT (RULE-DISP-03): Dispatches to Rudrapur/Nainital between Nov-Feb MUST have an engine heater installed for cold starts. A vehicle without an engine heater is INELIGIBLE.\n"
                "  2) 30-DAY FLAT RUNNING BRAKE REQUIREMENT (RULE-DISP-04): A vehicle must have had ZERO brake maintenance in the prior 30 days. New brake components require at least 30 days of flat running before steep hill service. A vehicle with brake work done 18 days ago is INELIGIBLE until 30 days have elapsed. (Citation: dispatcher_interview.txt:L18)"
            )

        # 10. Guddu Jugaad Rule
        if "guddu" in q_low or "jugaad" in q_low or "patch" in q_low or "roadside" in q_low:
            parts.append(
                "• GUDDU JUGAAD 7-DAY HOME BOUNDARY (RULE-DISP-06): Temporary roadside patches by mechanic Guddu carry a strict 7-day repair clock. "
                "During this 7-day period, the vehicle is STRICTLY LOCKED TO ITS HOME REGION and cannot cross into other hubs (e.g. cannot go from Lucknow to Kanpur). A permanent overhaul must be done within 7 days. (Citation: dispatcher_interview.txt:L42, emails/thread_25_internal_jugaad.txt:L8-10)"
            )

        # Dynamic Fleet Maintenance & Repair Telemetry Injection
        needs_fleet_maint = any(w in q_low for w in ["repair", "repaired", "checked", "overdue", "maintenance", "grounded", "jugaad", "broken", "list", "which", "fast", "schedule", "when", "all 38", "38 vehicles"])
        
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
                parts.append(f"Vehicles with Temporary Guddu Jugaad (Can be dispatched locally in home region immediately; must have permanent repair within 7 days): {'; '.join(jugaad_list)}")
            else:
                parts.append("Vehicles with Temporary Guddu Jugaad: None active currently.")
            
            if overdue_list:
                parts.append(f"Vehicles Grounded for Overdue Service (>150 days since last service, strictly grounded until routine service is completed): {'; '.join(overdue_list)} (Total {len(overdue_list)} vehicles overdue)")
            
            if brake_list:
                parts.append(f"Vehicles with Recent Brake Work (<30 days, cannot take hill routes, flat runs only): {'; '.join(brake_list)}")
            parts.append("====================================================")

        # Dynamic Entity Resolution (Specific vehicle mentioned in query)
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
            parts.append(f"Driver Profile {norm_drv}: Name={drv.get('name')}, Base Hub={drv.get('home_hub')}, Joined={drv.get('joining_date')} (Tenure: Joined {drv.get('joining_date')})")

        parts.append(f"Applicable Citations: {', '.join(candidate_citations) if candidate_citations else 'None'}")
        parts.append("=== INSTRUCTIONS: Answer the dispatcher's question thoroughly and factually using ONLY the operational policies and facts above. Cite the governing rule/reasoning directly. ===")
        return "\n".join(parts)
