"""Epsilon VRAM Guard & Process Lifecycle Manager.

Ported and adapted from Nyaya AI core/engine/native/vram_guard.cpp & engine/tiers/model_manager.py.
Protects system memory by tracking VRAM budgets, ensuring single-agent execution locks,
and safely launching / monitoring local LLM inference backends.
"""

import os
import sys
import time
import subprocess
import threading
from typing import Dict, Any, Optional

VRAM_TOTAL_MB = 4096       # Target baseline
VRAM_SAFETY_MB = 200      # Safety headroom
VRAM_USABLE_MB = VRAM_TOTAL_MB - VRAM_SAFETY_MB

TIER_VRAM_USAGE = {
    "fast": 1024,      # ~1GB for Qwen 1.5B
    "balanced": 3500,  # ~3.5GB for 7B
    "deep": 512        # CPU offloaded
}

class VRAMGuard:
    """
    Thread-safe VRAM budget tracker and process lifecycle guardian.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._allocated_mb = 0
        self._active_tier: Optional[str] = None
        self._server_proc: Optional[subprocess.Popen] = None

    def acquire_budget(self, tier: str) -> bool:
        """
        Attempts to allocate VRAM budget for the specified tier.
        """
        required = TIER_VRAM_USAGE.get(tier, 1024)
        with self._lock:
            if self._allocated_mb + required <= VRAM_USABLE_MB:
                self._allocated_mb += required
                self._active_tier = tier
                return True
            return False

    def release_budget(self, tier: Optional[str] = None) -> None:
        """
        Frees allocated VRAM budget.
        """
        with self._lock:
            t = tier or self._active_tier
            if t:
                reclaimed = TIER_VRAM_USAGE.get(t, 1024)
                self._allocated_mb = max(0, self._allocated_mb - reclaimed)
                if t == self._active_tier:
                    self._active_tier = None

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_mb": VRAM_TOTAL_MB,
                "usable_mb": VRAM_USABLE_MB,
                "allocated_mb": self._allocated_mb,
                "available_mb": max(0, VRAM_USABLE_MB - self._allocated_mb),
                "active_tier": self._active_tier
            }
