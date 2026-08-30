"""Epsilon Engine - Master LLM Orchestrator for Meridian Freight.

Integrates:
- EpsilonRouter (Zero-cost complexity scoring and model tier assignment)
- ContextInjector (Grounded context construction from ContextStore)
- VRAMGuard (Resource budgeting & concurrency management)
- CritiquePass (Algorithmic validation against fleet records, SLAs, and PII)
- SparseAttentionKVCache (INT8 ring buffer for context memory)
- AetherLink (Zero-knowledge session cleanup)
- Resilient local inference with automated fallback
"""

import os
import json
import logging
import requests
from typing import Any, Dict, List, Optional, Tuple

from src.entity.context_store import ContextStore
from src.llm.epsilon.router import EpsilonRouter
from src.llm.epsilon.context_injector import ContextInjector
from src.llm.epsilon.critique import CritiquePass
from src.llm.epsilon.vram_guard import VRAMGuard
from src.llm.epsilon.kv_cache import SparseAttentionKVCache
from src.llm.epsilon.aether_link import AetherLink
from src.security.pii_scrubber import redact_text, scan_for_pii
from src.observability import logger as log

OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_TAGS_URL = os.environ.get("OLLAMA_TAGS_URL", "http://127.0.0.1:11434/api/tags")

# Tier Model Mapping
TIER_MODELS = {
    "fast": "qwen2.5:1.5b",
    "balanced": "qwen2.5:7b",
    "deep": "llama3.2:3b"
}

class EpsilonEngine:
    """
    Production-grade local LLM engine that orchestrates routing, fact injection,
    VRAM management, hallucination interception, and deterministic failovers.
    """
    def __init__(self, context_store: Optional[ContextStore] = None):
        self.context_store = context_store or ContextStore()
        if not self.context_store.is_loaded:
            self.context_store.load_all()

        self.router = EpsilonRouter()
        self.context_injector = ContextInjector(self.context_store)
        self.critique = CritiquePass(self.context_store)
        self.vram_guard = VRAMGuard()
        self.kv_cache = SparseAttentionKVCache(top_k=64)
        self.aether = AetherLink()
        
        self.available_models: List[str] = []
        self.is_llm_online = self._detect_local_backend()

    def _detect_local_backend(self) -> bool:
        """Checks if local Ollama or inference server is responsive and indexes models."""
        try:
            resp = requests.get(OLLAMA_TAGS_URL, timeout=1.2)
            if resp.status_code == 200:
                data = resp.json()
                self.available_models = [m.get("name", "") for m in data.get("models", [])]
                log.info(f"Epsilon Engine connected to local backend. Models available: {self.available_models}")
                return True
        except Exception:
            pass
        return False

    def generate_grounded_comms(
        self,
        ticket: Dict[str, Any],
        replacement_vehicle: Optional[Dict[str, Any]] = None,
        rationale: str = "",
        citations: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generates a client communication message using Epsilon pipeline with full critique pass.
        """
        ticket_id = ticket.get("ticket_id", "UNKNOWN")
        client = ticket.get("client", "Internal")
        
        # 1. Zero-Cost Routing & Complexity Calculation
        route_meta = self.router.route_request(f"draft client message for {client} regarding {ticket.get('issue')}")
        tier = route_meta["assigned_tier"]
        
        # 2. Build Injected Fact Grounding Block
        grounding_block = self.context_injector.build_ticket_grounding_block(
            ticket, replacement_vehicle, rationale, citations
        )

        prompt = (
            f"Write a formal, concise operational notification to {client}.\n"
            f"Strictly follow these facts and NEVER invent dates, vehicles, or phone numbers:\n\n"
            f"{grounding_block}\n\n"
            f"Draft the notification body now:"
        )

        system_prompt = (
            "You are the Meridian Freight Automated Dispatch Assistant. "
            "Communicate factually, concisely, and professionally. NEVER disclose personal phone numbers or unverified data."
        )

        # 3. Model Generation (with VRAM budget and critique retry)
        draft_text = ""
        model_name = self._resolve_model_for_tier(tier)

        if self.is_llm_online and self.vram_guard.acquire_budget(tier):
            try:
                for attempt in range(2):
                    raw_gen = self._invoke_llm(prompt, system_prompt, model_name)
                    if raw_gen:
                        # 4. Critique Pass
                        is_valid, flaws = self.critique.validate_comms_draft(raw_gen, ticket, replacement_vehicle)
                        if is_valid:
                            draft_text = raw_gen
                            break
                        else:
                            log.warn(f"Critique pass intercepted flaws on attempt {attempt+1}: {flaws}")
            except Exception as e:
                log.error(f"Epsilon generation error: {e}")
            finally:
                self.vram_guard.release_budget(tier)

        # 5. Deterministic Fallback if LLM unavailable or rejected
        if not draft_text:
            draft_text = self._build_deterministic_comms(ticket, replacement_vehicle, rationale)

        # 6. Final Hard-Gate PII Redaction
        sanitized_draft = redact_text(draft_text)
        
        # 7. Zero-Knowledge Session Wipe
        response = self.aether.dispatch_response(
            ok=True,
            result=sanitized_draft,
            metadata={
                "ticket_id": ticket_id,
                "tier_used": tier,
                "complexity": route_meta["complexity_score"],
                "model": model_name if self.is_llm_online else "deterministic_fallback",
                "citations": citations or []
            }
        )

        return response

    def generate_grounded_query_answer(self, question: str) -> Dict[str, Any]:
        """
        Executes a natural language query over knowledge base via Epsilon Engine.
        """
        route_meta = self.router.route_request(question)
        tier = route_meta["assigned_tier"]
        
        # Search candidate citations
        candidate_citations = ["dispatcher_interview.txt", "fleet_master.csv", "maintenance_log.xlsx"]
        grounding_block = self.context_injector.build_query_grounding_block(question, candidate_citations)

        prompt = (
            f"Answer the user query based ONLY on the operational grounding below.\n"
            f"If the answer cannot be found in the facts, state clearly: 'Insufficient data in the ingested knowledge base and operational records to answer this query with grounded certainty.'\n\n"
            f"{grounding_block}\n\n"
            f"Question: {question}\nAnswer:"
        )

        answer_text = ""
        model_name = self._resolve_model_for_tier(tier)

        if self.is_llm_online and self.vram_guard.acquire_budget(tier):
            try:
                raw_answer = self._invoke_llm(prompt, "You are Rajender's Brain, an AI logistics copilot for Meridian Freight. Answer accurately based on provided operational facts.", model_name)
                if raw_answer and len(raw_answer.strip()) > 3:
                    answer_text = raw_answer.strip()
            except Exception as e:
                log.error(f"Epsilon query generation error: {e}")
            finally:
                self.vram_guard.release_budget(tier)

        # Extract vehicle and rule metadata for UI buttons
        from src.entity.normalizer import extract_vehicle_reg_from_text
        norm_veh, is_reg = extract_vehicle_reg_from_text(question)
        vehicle_data = None
        rule_code = None
        rule_name = None

        if is_reg and norm_veh:
            veh = self.context_store.get_vehicle(norm_veh)
            maint = self.context_store.get_maintenance_summary(norm_veh)
            if veh:
                vehicle_data = {
                    "reg": norm_veh,
                    "model": veh.get("model"),
                    "year": veh.get("year"),
                    "bs_stage": veh.get("bs_stage"),
                    "home_hub": veh.get("home_hub"),
                    "status": veh.get("status"),
                    "engine_heater": veh.get("engine_heater"),
                    "latest_service_date": maint.get("latest_service_date", "N/A"),
                    "is_overdue": maint.get("is_overdue", False),
                    "has_active_jugaad": maint.get("has_active_jugaad", False),
                    "brake_work_in_last_30d": maint.get("brake_work_in_last_30d", False),
                }
                if maint.get("is_overdue"):
                    rule_code = "RULE-DISP-05"
                    rule_name = "Maintenance Overdue Grounding Policy (>30 Days)"

        if not rule_code:
            q_low = question.lower()
            if "shakti" in q_low:
                rule_code = "RULE-CLI-01"
                rule_name = "Shakti Cement 36-Hour Operational Protocol"
            elif "vertex" in q_low:
                rule_code = "RULE-CLI-02"
                rule_name = "Vertex Retail 6:00 PM Gate Hold Protocol"
            elif "apex" in q_low:
                rule_code = "RULE-CLI-03"
                rule_name = "Apex Chemicals Truck Rotation Protocol"
            elif "orion" in q_low:
                rule_code = "RULE-CLI-04"
                rule_name = "Orion Pharma 2020+ Vehicle & Refrigeration Protocol"
            elif "bs4" in q_low or "bs6" in q_low:
                rule_code = "RULE-DISP-02"
                rule_name = "Delhi NCR Winter GRAP BS4 Vehicle Ban"
            elif "hill" in q_low or "rudrapur" in q_low or "nainital" in q_low:
                rule_code = "RULE-DISP-03 / 04"
                rule_name = "Hill Route Engine Heater & 30-Day Brake Rule"
            elif "guddu" in q_low or "jugaad" in q_low:
                rule_code = "RULE-DISP-06"
                rule_name = "Guddu Roadside Temporary Patch 7-Day Boundary Rule"

        if not answer_text:
            # Fallback only if LLM is unreachable or timed out
            from src.query.engine import GroundedQueryEngine
            engine = GroundedQueryEngine(self.context_store)
            det_res = engine.query(question)
            answer_text = det_res["answer"]
            citations = det_res["citations"]
            is_sufficient = det_res["is_sufficient"]
            rule_code = rule_code or det_res.get("rule_code")
            rule_name = rule_name or det_res.get("rule_name")
            vehicle_data = vehicle_data or det_res.get("vehicle_data")
            is_llm = False
        else:
            citations = candidate_citations
            is_sufficient = "insufficient data" not in answer_text.lower()
            is_llm = True

        sanitized_answer = redact_text(answer_text)
        self.aether.session_wipe()

        return {
            "question": question,
            "answer": sanitized_answer,
            "citations": citations,
            "is_sufficient": is_sufficient,
            "tier_used": tier,
            "model_used": model_name if is_llm else "deterministic_engine",
            "is_llm_generated": is_llm,
            "rule_code": rule_code,
            "rule_name": rule_name,
            "vehicle_data": vehicle_data
        }

    def _resolve_model_for_tier(self, tier: str) -> str:
        """Selects the best installed model matching the tier."""
        if self.available_models:
            preferred = TIER_MODELS.get(tier, "qwen2.5:1.5b")
            for m in self.available_models:
                if preferred.split(":")[0] in m:
                    return m
            return self.available_models[0]
        return TIER_MODELS.get(tier, "qwen2.5:1.5b")

    def _invoke_llm(self, prompt: str, system: str, model: str) -> str:
        """Submits inference request to Ollama HTTP API."""
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 256
            }
        }
        resp = requests.post(OLLAMA_API_URL, json=payload, timeout=12.0)
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
        return ""

    def _build_deterministic_comms(
        self,
        ticket: Dict[str, Any],
        replacement_vehicle: Optional[Dict[str, Any]],
        rationale: str
    ) -> str:
        """High-reliability deterministic template for comms drafting."""
        client = ticket.get("client", "Internal")
        broken = ticket.get("vehicle", "assigned vehicle")
        issue = ticket.get("issue", "technical malfunction")
        orig = ticket.get("origin_hub", "Origin")
        dest = ticket.get("destination", "Destination")
        repl = replacement_vehicle.get("canonical_reg", "replacement vehicle") if replacement_vehicle else "roadside support team"

        if client == "Shakti Cement":
            return (
                f"Dear Shakti Cement Dispatch Team,\n\n"
                f"Vehicle {broken} encountered a {issue} on the {orig} to {dest} transit. "
                f"In accordance with our 36-hour delivery protocol, replacement vehicle {repl} has been dispatched "
                f"to complete transshipment without delay. Total turnaround remains on schedule.\n\n"
                f"Meridian Operations"
            )
        elif client == "Vertex Retail":
            return (
                f"Dear Vertex Retail Logistics Team,\n\n"
                f"Vehicle {broken} experienced a {issue} en route from {orig} to {dest}. "
                f"Replacement vehicle {repl} has been mobilized. Consignment is scheduled "
                f"for morning gate opening delivery at 8:00 AM as per standing SOP.\n\n"
                f"Meridian Operations"
            )
        elif client == "Apex Chemicals":
            return (
                f"Dear Apex Chemicals Stores Team,\n\n"
                f"Consignment on route {orig} to {dest} reported a {issue} on vehicle {broken}. "
                f"A dedicated replacement unit {repl} has been deployed to ensure uninterrupted delivery. "
                f"All required MSDS documentation is in order.\n\n"
                f"Meridian Operations"
            )
        elif client == "Orion Pharma":
            return (
                f"Dear Orion Pharma SCM Team,\n\n"
                f"Vehicle {broken} en route {orig} to {dest} reported a {issue}. "
                f"Audit-compliant replacement vehicle {repl} (2020+ model) has been deployed immediately. "
                f"Refrigeration and temperature monitoring remain continuously maintained.\n\n"
                f"Meridian Operations"
            )
        else:
            return (
                f"Operational Update [{client}]: Vehicle {broken} reported a {issue} on route {orig} to {dest}. "
                f"Replacement vehicle {repl} has been assigned for resolution.\n\n"
                f"Meridian Dispatch"
            )
