"""Expert Dispatcher Rules and Client Specifications.

Encodes Rajender Pal Yadav's 14 years of veteran dispatch rules
and client-specific operational constraints with exact line-level citations.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.config import (
    DELHI_NCR_REGIONS,
    HILL_REGIONS,
    MONSOON_MONTHS,
    WINTER_MONTHS_DELHI,
    WINTER_MONTHS_HILLS,
)

@dataclass
class RuleEvaluationResult:
    is_compliant: bool
    rule_id: str
    rule_name: str
    decision_reason: str
    citations: List[str] = field(default_factory=list)

class ExpertRulesEngine:
    """Evaluates tickets and dispatch operations against codified operational rules."""

    @staticmethod
    def evaluate_origin_vs_nearest_hub(km_from_origin: float, origin_hub: str) -> Tuple[str, List[str]]:
        """
        RULE-DISP-01: Within 50km of origin hub, origin hub MUST send replacement.
        Beyond 50km, nearest hub with eligible vehicle sends replacement.
        Citation: dispatcher_interview.txt:L36-37
        """
        if km_from_origin <= 50.0:
            return (
                f"Breakdown is {km_from_origin} km (<= 50 km) from origin hub '{origin_hub}'. Replacement MUST be dispatched from origin hub '{origin_hub}'.",
                ["dispatcher_interview.txt:L36-37"]
            )
        else:
            return (
                f"Breakdown is {km_from_origin} km (> 50 km) from origin hub '{origin_hub}'. Replacement to be sourced from nearest hub with eligible vehicle.",
                ["dispatcher_interview.txt:L36-37"]
            )

    @staticmethod
    def check_delhi_ncr_winter_bs_stage(route_hubs: List[str], bs_stage: str, ticket_date: datetime) -> RuleEvaluationResult:
        """
        RULE-DISP-02: October to February, no BS4 vehicle on any Delhi NCR route (Delhi, Gurgaon, Faridabad, Noida).
        BS6 only.
        Citation: dispatcher_interview.txt:L14
        """
        month = ticket_date.month
        touches_delhi_ncr = any(h in DELHI_NCR_REGIONS for h in route_hubs if h)
        
        if month in WINTER_MONTHS_DELHI and touches_delhi_ncr:
            if bs_stage.upper() != "BS6":
                return RuleEvaluationResult(
                    is_compliant=False,
                    rule_id="RULE-DISP-02",
                    rule_name="Delhi NCR Winter BS4 Restriction",
                    decision_reason=f"Route touches Delhi NCR ({[h for h in route_hubs if h in DELHI_NCR_REGIONS]}) in winter month ({month}). Vehicle is {bs_stage}; BS6 is strictly required.",
                    citations=["dispatcher_interview.txt:L14"]
                )

        return RuleEvaluationResult(
            is_compliant=True,
            rule_id="RULE-DISP-02",
            rule_name="Delhi NCR Winter BS4 Restriction",
            decision_reason=f"Vehicle {bs_stage} is compliant for route {route_hubs} in month {month}.",
            citations=["dispatcher_interview.txt:L14"]
        )

    @staticmethod
    def check_hill_route_requirements(destination_or_route: List[str], engine_heater: str, brake_work_30d: bool, ticket_date: datetime) -> RuleEvaluationResult:
        """
        RULE-DISP-03 & 04: Hill routes (Rudrapur, Nainital) in Nov to Feb:
        - Must have engine heater (Yes)
        - Must NOT have had any brake work in past 30 days.
        Citation: dispatcher_interview.txt:L18
        """
        month = ticket_date.month
        touches_hills = any(h in HILL_REGIONS for h in destination_or_route if h)

        if touches_hills:
            # Brake check applies year round or in hill terrain
            if brake_work_30d:
                return RuleEvaluationResult(
                    is_compliant=False,
                    rule_id="RULE-DISP-04",
                    rule_name="Hill Route Brake Safety Rule",
                    decision_reason="Vehicle had brake work within the last 30 days. Ineligible for hill routes (requires 30 days flat running first).",
                    citations=["dispatcher_interview.txt:L18"]
                )

            # Heater check in winter (Nov - Feb)
            if month in WINTER_MONTHS_HILLS and engine_heater.capitalize() != "Yes":
                return RuleEvaluationResult(
                    is_compliant=False,
                    rule_id="RULE-DISP-03",
                    rule_name="Hill Route Winter Engine Heater Rule",
                    decision_reason=f"Vehicle lacks engine heater for hill route ({destination_or_route}) in winter month ({month}).",
                    citations=["dispatcher_interview.txt:L18"]
                )

        return RuleEvaluationResult(
            is_compliant=True,
            rule_id="RULE-DISP-03_04",
            rule_name="Hill Route Compliance",
            decision_reason="Vehicle complies with hill route safety standards.",
            citations=["dispatcher_interview.txt:L18"]
        )

    @staticmethod
    def check_service_grounding(is_overdue: bool) -> RuleEvaluationResult:
        """
        RULE-DISP-05: Any vehicle > 30 days past due service date is grounded.
        Citation: dispatcher_interview.txt:L38
        """
        if is_overdue:
            return RuleEvaluationResult(
                is_compliant=False,
                rule_id="RULE-DISP-05",
                rule_name="Overdue Service Grounding Rule",
                decision_reason="Vehicle is > 30 days past scheduled service date and is GROUNDED. Ineligible for dispatch.",
                citations=["dispatcher_interview.txt:L38"]
            )
        return RuleEvaluationResult(
            is_compliant=True,
            rule_id="RULE-DISP-05",
            rule_name="Overdue Service Grounding Rule",
            decision_reason="Vehicle maintenance service is up-to-date.",
            citations=["dispatcher_interview.txt:L38"]
        )

    @staticmethod
    def check_jugaad_lock(has_active_jugaad: bool, is_leaving_home_region: bool) -> RuleEvaluationResult:
        """
        RULE-DISP-06: Guddu ka jugaad is a 7-day clock and vehicle cannot leave home region.
        Citation: dispatcher_interview.txt:L42, thread_25_internal_jugaad.txt
        """
        if has_active_jugaad and is_leaving_home_region:
            return RuleEvaluationResult(
                is_compliant=False,
                rule_id="RULE-DISP-06",
                rule_name="Guddu Roadside Patch Boundary Restriction",
                decision_reason="Vehicle operates under temporary roadside patch (jugaad) and cannot leave home region until permanent repair.",
                citations=["dispatcher_interview.txt:L42", "emails/thread_25_internal_jugaad.txt"]
            )
        return RuleEvaluationResult(
            is_compliant=True,
            rule_id="RULE-DISP-06",
            rule_name="Guddu Roadside Patch Rule",
            decision_reason="No temporary roadside patch restriction active.",
            citations=["dispatcher_interview.txt:L42"]
        )

    @staticmethod
    def get_client_sla_and_rules(client: str, ticket_date: datetime, eta_hours: float, dest_hub: str) -> Dict[str, Any]:
        """
        Evaluates Client Specific Operational Rules:
        - RULE-CLI-01: Shakti Cement 36h internal SLA (dispatcher_interview.txt:L22, thread_01_shakti_sla.txt)
        - RULE-CLI-02: Vertex Retail 6pm Ludhiana gate cutoff (dispatcher_interview.txt:L24, thread_09_vertex_gate.txt)
        - RULE-CLI-03: Apex Chemicals rotate problem trucks (dispatcher_interview.txt:L26, thread_13_apex_rotation.txt)
        - RULE-CLI-04: Orion Pharma >= 2020 RC year & refrigerated (dispatcher_interview.txt:L28, thread_17_orion_age.txt)
        - RULE-DISP-07: Monsoon Eastern buffer (+20%) in Jul-Sep (dispatcher_interview.txt:L32, thread_23_internal_monsoon.txt)
        """
        client_clean = client.strip() if client else "Internal"
        sla_hours = 48.0
        special_instructions = []
        citations = []

        # Shakti Cement Rule
        if client_clean == "Shakti Cement":
            sla_hours = 36.0
            special_instructions.append("Plan delivery strictly to 36 hours. Overrides 48h contract language.")
            citations.extend(["dispatcher_interview.txt:L22", "emails/thread_01_shakti_sla.txt"])

        # Vertex Retail Rule
        elif client_clean == "Vertex Retail":
            special_instructions.append("Ludhiana WH gate closes 6:00 PM sharp. If arriving after 6 PM, hold at halt and schedule 8:00 AM morning delivery. Never mark failed.")
            citations.extend(["dispatcher_interview.txt:L24", "emails/thread_09_vertex_gate.txt"])

        # Apex Chemicals Rule
        elif client_clean == "Apex Chemicals":
            special_instructions.append("Truck rotation mandatory: never assign a vehicle that had an incident/breakdown on its previous Apex dispatch.")
            citations.extend(["dispatcher_interview.txt:L26", "emails/thread_13_apex_rotation.txt"])

        # Orion Pharma Rule
        elif client_clean == "Orion Pharma":
            special_instructions.append("Pharma audit rule: vehicle model year MUST be 2020 or later per RC copy. No overnight unrefrigerated wait.")
            citations.extend(["dispatcher_interview.txt:L28", "emails/thread_17_orion_age.txt"])

        # Monsoon East Rule
        month = ticket_date.month
        is_monsoon = month in MONSOON_MONTHS
        is_eastern_route = dest_hub in ("Lucknow", "Kanpur", "Bihar", "Patna", "Guwahati", "Muzaffarpur")
        
        if is_monsoon and is_eastern_route:
            padded_eta = eta_hours * 1.20
            special_instructions.append(f"Monsoon eastern route buffer applied (+20%): ETA padded from {eta_hours:.1f}h to {padded_eta:.1f}h.")
            citations.extend(["dispatcher_interview.txt:L32", "emails/thread_23_internal_monsoon.txt"])

        return {
            "client": client_clean,
            "sla_hours": sla_hours,
            "special_instructions": special_instructions,
            "citations": list(set(citations))
        }
