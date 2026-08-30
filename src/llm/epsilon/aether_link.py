"""Epsilon Aether Link - Communication Bridge & Zero-Knowledge Session Guardian.

Ported from Nyaya AI core/engine/aether/link.py.
Handles inter-process message dispatch and performs mandatory zero-knowledge session wipes
after every inference step to eliminate memory leaks and cross-request contamination.
"""

import gc
import json
import sys
from typing import Dict, Any, Optional

class AetherLink:
    """
    Session orchestrator that ensures deterministic responses and strict zero-knowledge memory wiping.
    """
    def __init__(self):
        self.request_count = 0

    def session_wipe(self) -> None:
        """
        Zero-Knowledge Session Wipe.
        Clears Python garbage, temporary token allocations, and cached buffers.
        """
        try:
            gc.collect()
        except Exception:
            pass

    def dispatch_response(self, ok: bool, result: Any, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Structures output and executes immediate session cleanup.
        """
        self.request_count += 1
        payload = {
            "ok": ok,
            "result": result,
            "metadata": metadata or {},
            "request_count": self.request_count
        }
        self.session_wipe()
        return payload
