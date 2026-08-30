"""Conflict Resolution and Precedence Engine.

Defines documented precedence rules where data sources conflict,
eliminating silent guesses and ensuring full auditability.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class PrecedenceRule:
    domain: str
    primary_source: str
    secondary_source: str
    precedence_rationale: str
    citation: str

PRECEDENCE_RULES = {
    "vehicle_specs": PrecedenceRule(
        domain="Vehicle Specifications & Year",
        primary_source="fleet_master.csv (Official RC Data)",
        secondary_source="Informal emails / yard notes",
        precedence_rationale="RC registration year in fleet master is official legal ground truth. Informal claims in emails are overruled.",
        citation="thread_21_internal_yearconflict.txt:L11-13"
    ),
    "odometer_maintenance": PrecedenceRule(
        domain="Odometer & Maintenance Readings",
        primary_source="maintenance_log.xlsx (Workshop Log & Photo Reference)",
        secondary_source="Yard visual check emails",
        precedence_rationale="Workshop entry with odometer photo reference is ground truth; yard estimates are discarded.",
        citation="thread_22_internal_odoconflict.txt:L11-13"
    ),
    "client_sla": PrecedenceRule(
        domain="Client Operating SLA",
        primary_source="dispatcher_interview.txt & Operational Emails",
        secondary_source="Stale Contract SOP Documents",
        precedence_rationale="Operational agreements and dispatcher rules override legacy paper contracts (e.g. Shakti 36h SLA).",
        citation="dispatcher_interview.txt:L22, thread_01_shakti_sla.txt:L5-7"
    ),
    "driver_tenure": PrecedenceRule(
        domain="Driver Night Run Eligibility",
        primary_source="drivers_roster.csv joining_date & Dispatcher Roster Rule",
        secondary_source="Ad-hoc booking slots",
        precedence_rationale="Drivers with < 6 months tenure cannot be dispatched solo on night runs.",
        citation="dispatcher_interview.txt:L46, thread_24_internal_nightroster.txt:L5-8"
    )
}

def get_precedence(domain: str) -> Optional[PrecedenceRule]:
    """Returns the documented precedence rule for a conflict domain."""
    return PRECEDENCE_RULES.get(domain)
