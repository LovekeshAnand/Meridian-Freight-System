"""Epsilon Router - Zero-AI Task Classification, Complexity Scoring & Tier Routing.

Ported from Nyaya AI core/engine/agents/router.py & engine/tiers/router.py.
Implements pure deterministic keyword heuristics to bypass expensive token burns
and calculate complexity (1-10) for dispatch operations.
"""

from typing import Any, Dict, List, Optional
import re

# Complexity signal dictionary tailored to Meridian Freight Operations
COMPLEXITY_SIGNALS = {
    # High-complexity operational conditions (Scores 3-4)
    "delhi ncr": 3,
    "bs4": 3,
    "grap": 4,
    "winter": 3,
    "monsoon": 3,
    "rudrapur": 3,
    "nainital": 3,
    "hill route": 4,
    "engine heater": 3,
    "jugaad": 4,
    "guddu": 4,
    "roadside fix": 3,
    "overdue service": 3,
    "pharma audit": 3,
    "apex chemical": 3,
    "incident history": 3,
    "brake work": 3,
    
    # Moderate complexity operational terms (Scores 1-2)
    "shakti cement": 2,
    "vertex retail": 2,
    "orion pharma": 2,
    "transshipment": 2,
    "delivery protocol": 2,
    "sla": 1,
    "origin hub": 1,
    "destination": 1,
    "replacement vehicle": 2,
    "work order": 1,
    "breakdown": 1
}

# Task classification keywords
CLASSIFICATION_KEYWORDS = {
    "COMMS_DRAFT": ["draft", "notify", "client message", "communication", "email", "sms", "alert client"],
    "GROUNDED_QUERY": ["what is", "where is", "how much", "who is", "explain", "policy", "rule", "protocol", "status of"],
    "FLEET_LOOKUP": ["vehicle details", "driver details", "maintenance history", "is overdue", "plate number", "specs"],
    "DIAGNOSTIC_ANALYSIS": ["defect analysis", "root cause", "component failure", "malfunction", "jugaad status"]
}

class EpsilonRouter:
    """
    Deterministic zero-cost classifier and complexity evaluator for Meridian Freight LLM pipelines.
    """
    def __init__(self, available_tiers: Optional[List[str]] = None):
        self.available_tiers = available_tiers or ["fast", "balanced", "deep"]

    def detect_task_type(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        for task_type, keywords in CLASSIFICATION_KEYWORDS.items():
            if any(kw in prompt_lower for kw in keywords):
                return task_type
        return "GENERAL_DISPATCH_QUERY"

    def calculate_complexity(self, prompt: str) -> int:
        """
        Score prompt complexity from 1 to 10 based on keyword signals, length, and multi-clause rules.
        """
        prompt_lower = prompt.lower()
        score = 1  # Base score

        for signal, weight in COMPLEXITY_SIGNALS.items():
            if signal in prompt_lower:
                score += weight

        # Length and multi-line heuristics
        words = prompt.split()
        if len(words) > 40:
            score += 1
        if len(words) > 80:
            score += 1
        if prompt.count("\n") > 5:
            score += 1

        return min(max(score, 1), 10)

    def select_model_tier(self, complexity: int) -> str:
        """
        Routes complexity to tiers:
        - 1 to 3: fast (Qwen 1.5B / Fast model)
        - 4 to 7: balanced (7B model / High precision)
        - 8 to 10: deep (Reasoning / Extended grounding)
        """
        if complexity <= 3:
            ideal = "fast"
        elif complexity <= 7:
            ideal = "balanced"
        else:
            ideal = "deep"

        if ideal in self.available_tiers:
            return ideal

        # Fallback hierarchy
        for fallback in ["fast", "balanced", "deep"]:
            if fallback in self.available_tiers:
                return fallback
        return "fast"

    def route_request(self, prompt: str) -> Dict[str, Any]:
        """
        Executes complete routing in <1ms without invoking any neural network.
        """
        task_type = self.detect_task_type(prompt)
        complexity = self.calculate_complexity(prompt)
        tier = self.select_model_tier(complexity)

        return {
            "task_type": task_type,
            "complexity_score": complexity,
            "assigned_tier": tier,
            "needs_llm": complexity > 1 or task_type == "COMMS_DRAFT"
        }
