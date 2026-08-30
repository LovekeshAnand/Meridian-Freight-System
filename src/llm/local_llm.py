"""Local LLM Interface for Meridian Freight — Powered by Epsilon Engine.

All LLM operations (text generation, client communications, grounded Q&A, and diagnostics)
are routed through the Epsilon Engine.
"""

from typing import Any, Dict, Optional, List
from src.llm.epsilon.epsilon_engine import EpsilonEngine
from src.entity.context_store import ContextStore

class LocalLLM:
    """
    Unified LLM runner backed by Epsilon Engine.
    Provides complete anti-hallucination critique, zero-cost complexity routing,
    and 100% reliable fallback.
    """
    def __init__(self, context_store: Optional[ContextStore] = None):
        self.context_store = context_store or ContextStore()
        self.engine = EpsilonEngine(self.context_store)

    @property
    def is_available(self) -> bool:
        return self.engine.is_llm_online

    def generate_comms(
        self,
        ticket: Dict[str, Any],
        replacement_vehicle: Optional[Dict[str, Any]] = None,
        rationale: str = "",
        citations: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generates grounded client communication via Epsilon Engine."""
        return self.engine.generate_grounded_comms(
            ticket=ticket,
            replacement_vehicle=replacement_vehicle,
            rationale=rationale,
            citations=citations
        )

    def query(self, question: str) -> Dict[str, Any]:
        """Answers operational questions with exact citations via Epsilon Engine."""
        return self.engine.generate_grounded_query_answer(question)

    def generate(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 512) -> str:
        """Raw generation fallback hook passing through Epsilon routing."""
        route = self.engine.router.route_request(prompt)
        tier = route["assigned_tier"]
        model = self.engine._resolve_model_for_tier(tier)
        
        if self.engine.is_llm_online and self.engine.vram_guard.acquire_budget(tier):
            try:
                return self.engine._invoke_llm(prompt, system_prompt or "", model)
            finally:
                self.engine.vram_guard.release_budget(tier)
                self.engine.aether.session_wipe()
        return ""
