"""Eligible Replacement Vehicle Selection Engine — Hardened Edition.

Returns a structured VehicleSelectionResult with full decision trail:
- which vehicles were evaluated
- exactly which rule rejected each candidate
- whether failure was "no vehicles at hub" vs "all rejected by rules"
- which hub the search extended to and why

Never returns an opaque None. Every decision is traceable.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.config import get_hub_distance
from src.entity.context_store import ContextStore
from src.entity.normalizer import normalize_hub_name, normalize_vehicle_reg
from src.rules.expert_rules import ExpertRulesEngine
from src.observability import logger as log


@dataclass
class CandidateRejection:
    vehicle_reg: str
    hub: str
    rule_failed: str
    detail: str


@dataclass
class VehicleSelectionResult:
    """Full structured result of vehicle selection — always returned, never None."""
    selected: Optional[Dict[str, Any]]
    rationale: str
    citations: List[str]
    hub_used: Optional[str] = None
    hub_search_strategy: str = ""
    rejected_candidates: List[CandidateRejection] = field(default_factory=list)
    failure_mode: Optional[str] = None  # None if succeeded; else one of:
    # "NO_VEHICLES_AT_HUB" | "ALL_REJECTED_BY_RULES" | "FLEET_EXHAUSTED"

    @property
    def is_success(self) -> bool:
        return self.selected is not None


class VehicleSelector:
    def __init__(self, context_store: ContextStore):
        self.context_store = context_store
        self.rules_engine = ExpertRulesEngine()

    def select_replacement_vehicle(self, ticket: Dict[str, Any]) -> VehicleSelectionResult:
        """
        Evaluates fleet and selects the best eligible replacement vehicle.
        Returns a VehicleSelectionResult with full decision trail.
        Never raises an exception.
        """
        try:
            return self._select(ticket)
        except Exception as e:
            log.error(
                "VehicleSelector crashed unexpectedly — returning FLEET_EXHAUSTED result.",
                ticket_id=ticket.get("ticket_id", "?"),
                exc=e,
            )
            return VehicleSelectionResult(
                selected=None,
                rationale=f"Vehicle selector internal error: {e}",
                citations=[],
                failure_mode="FLEET_EXHAUSTED",
            )

    def _select(self, ticket: Dict[str, Any]) -> VehicleSelectionResult:
        origin_hub = normalize_hub_name(ticket.get("origin_hub")) or "Gurgaon"
        dest_hub = normalize_hub_name(ticket.get("destination")) or origin_hub
        km_from_origin = float(ticket.get("km_from_origin_hub", 0.0))
        client = ticket.get("client", "Internal")

        try:
            ticket_date = datetime.strptime(str(ticket.get("created_at", "")).split("T")[0], "%Y-%m-%d")
        except Exception:
            ticket_date = datetime(2026, 8, 30)

        broken_reg, _ = normalize_vehicle_reg(ticket.get("vehicle", ""))
        all_citations: List[str] = []
        all_rejections: List[CandidateRejection] = []

        # ── Hub strategy (RULE-DISP-01) ──────────────────────────────────────
        origin_rule_text, origin_cits = self.rules_engine.evaluate_origin_vs_nearest_hub(
            km_from_origin, origin_hub
        )
        all_citations.extend(origin_cits)

        if km_from_origin <= 50.0:
            candidate_hubs = [origin_hub]
            hub_strategy = f"km_from_origin={km_from_origin:.1f} ≤ 50 → using origin hub only (RULE-DISP-01)"
        else:
            all_hubs = list({
                v["home_hub"] for v in self.context_store.vehicles.values() if v.get("home_hub")
            })
            candidate_hubs = sorted(all_hubs, key=lambda h: get_hub_distance(origin_hub, h))
            hub_strategy = (
                f"km_from_origin={km_from_origin:.1f} > 50 → searching all hubs by proximity to '{origin_hub}'"
            )

        # ── Search hubs in order ──────────────────────────────────────────────
        for hub in candidate_hubs:
            hub_vehicles = self.context_store.get_eligible_vehicles_at_hub(hub)

            if not hub_vehicles:
                all_rejections.append(CandidateRejection(
                    vehicle_reg="(none)",
                    hub=hub,
                    rule_failed="HUB_EMPTY",
                    detail=f"No active vehicles homed at '{hub}'",
                ))
                continue

            eligible_candidates = []

            for veh in hub_vehicles:
                reg = veh["canonical_reg"]

                if reg == broken_reg:
                    all_rejections.append(CandidateRejection(
                        vehicle_reg=reg, hub=hub,
                        rule_failed="SELF", detail="This is the broken vehicle itself",
                    ))
                    continue

                maint = self.context_store.get_maintenance_summary(reg, str(ticket.get("created_at", "")))

                # Rule DISP-05: Overdue service grounding
                grounding_eval = self.rules_engine.check_service_grounding(maint.get("is_overdue", False))
                if not grounding_eval.is_compliant:
                    all_rejections.append(CandidateRejection(
                        vehicle_reg=reg, hub=hub,
                        rule_failed="RULE-DISP-05",
                        detail=f"Overdue service (last: {maint.get('latest_service_date')})",
                    ))
                    continue

                # Rule DISP-02: Delhi NCR winter BS4 restriction
                route_hubs = [origin_hub, dest_hub, hub]
                bs_eval = self.rules_engine.check_delhi_ncr_winter_bs_stage(
                    route_hubs, veh.get("bs_stage", "BS4"), ticket_date
                )
                if not bs_eval.is_compliant:
                    all_rejections.append(CandidateRejection(
                        vehicle_reg=reg, hub=hub,
                        rule_failed="RULE-DISP-02",
                        detail=f"BS stage '{veh.get('bs_stage')}' violates Delhi NCR winter restriction",
                    ))
                    continue

                # Rule DISP-03/04: Hill route heater & brake
                hill_eval = self.rules_engine.check_hill_route_requirements(
                    [dest_hub], veh.get("engine_heater", "No"),
                    maint.get("brake_work_in_last_30d", False), ticket_date
                )
                if not hill_eval.is_compliant:
                    all_rejections.append(CandidateRejection(
                        vehicle_reg=reg, hub=hub,
                        rule_failed="RULE-DISP-03/04",
                        detail=f"Hill route: heater={veh.get('engine_heater')}, brake_30d={maint.get('brake_work_in_last_30d')}",
                    ))
                    continue

                # Rule DISP-06: Guddu jugaad boundary
                is_leaving_home = normalize_hub_name(veh.get("home_hub")) != dest_hub
                jugaad_eval = self.rules_engine.check_jugaad_lock(
                    maint.get("has_active_jugaad", False), is_leaving_home
                )
                if not jugaad_eval.is_compliant:
                    all_rejections.append(CandidateRejection(
                        vehicle_reg=reg, hub=hub,
                        rule_failed="RULE-DISP-06",
                        detail="Active Guddu jugaad — vehicle locked to home region",
                    ))
                    continue

                # Rule CLI-04: Orion Pharma >= 2020
                if client == "Orion Pharma" and int(veh.get("year", 2018)) < 2020:
                    all_rejections.append(CandidateRejection(
                        vehicle_reg=reg, hub=hub,
                        rule_failed="RULE-CLI-04",
                        detail=f"Orion Pharma requires year >= 2020; vehicle is {veh.get('year')}",
                    ))
                    continue

                # Rule CLI-03: Apex Chemicals rotation
                if client == "Apex Chemicals" and reg in self.context_store.apex_incident_vehicles:
                    all_rejections.append(CandidateRejection(
                        vehicle_reg=reg, hub=hub,
                        rule_failed="RULE-CLI-03",
                        detail="Vehicle had prior Apex Chemicals incident — rotation enforced",
                    ))
                    continue

                eligible_candidates.append(veh)

            if eligible_candidates:
                eligible_candidates.sort(
                    key=lambda v: (
                        1 if v.get("bs_stage") == "BS6" else 0,
                        int(v.get("year", 2015)),
                        -get_hub_distance(hub, origin_hub),
                    ),
                    reverse=True,
                )
                chosen = eligible_candidates[0]
                all_citations.append(chosen.get("citation", "fleet_master.csv"))
                rationale = (
                    f"Selected {chosen['canonical_reg']} ({chosen['model']}, {chosen['year']}, "
                    f"{chosen['bs_stage']}) from '{hub}'. {origin_rule_text}"
                )
                log.info(
                    f"Vehicle selected: {chosen['canonical_reg']} from {hub}",
                    ticket_id=ticket.get("ticket_id", "?"),
                    vehicle=chosen["canonical_reg"],
                    hub=hub,
                    rejections=len(all_rejections),
                )
                return VehicleSelectionResult(
                    selected=chosen,
                    rationale=rationale,
                    citations=list(set(all_citations)),
                    hub_used=hub,
                    hub_search_strategy=hub_strategy,
                    rejected_candidates=all_rejections,
                )

        # ── Exhausted hubs: emergency fleet-wide search ──────────────────────
        for reg, veh in self.context_store.vehicles.items():
            if veh.get("status") == "Active" and reg != broken_reg:
                all_citations.append(veh.get("citation", "fleet_master.csv"))
                log.alert(
                    f"Emergency fleet allocation: {reg}. All standard hubs exhausted.",
                    alert_type="EMERGENCY_ALLOCATION",
                    ticket_id=ticket.get("ticket_id", "?"),
                )
                return VehicleSelectionResult(
                    selected=veh,
                    rationale=f"Emergency allocation: {reg} from fleet (all hub-specific candidates exhausted).",
                    citations=list(set(all_citations)),
                    hub_used=veh.get("home_hub"),
                    hub_search_strategy=hub_strategy,
                    rejected_candidates=all_rejections,
                    failure_mode=None,  # Succeeded via emergency path
                )

        # ── Truly no vehicle found ────────────────────────────────────────────
        hub_empty = all(r.rule_failed == "HUB_EMPTY" for r in all_rejections)
        failure_mode = "NO_VEHICLES_AT_HUB" if hub_empty else "ALL_REJECTED_BY_RULES"

        log.alert(
            f"No eligible vehicle found. Failure mode: {failure_mode}. "
            f"Rejected: {len(all_rejections)} candidate(s).",
            alert_type="NO_VEHICLE",
            ticket_id=ticket.get("ticket_id", "?"),
            failure_mode=failure_mode,
        )

        rejection_summary = "; ".join(
            f"{r.vehicle_reg}@{r.hub}:{r.rule_failed}" for r in all_rejections[:5]
        )
        return VehicleSelectionResult(
            selected=None,
            rationale=f"No eligible vehicle. Mode={failure_mode}. Top rejections: {rejection_summary}",
            citations=list(set(all_citations)),
            hub_used=None,
            hub_search_strategy=hub_strategy,
            rejected_candidates=all_rejections,
            failure_mode=failure_mode,
        )
