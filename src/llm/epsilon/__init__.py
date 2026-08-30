# Epsilon Engine — Meridian Freight Package
"""
Ported from Nyaya AI core/engine.
All LLM calls for Meridian go through this package.

Architecture:
  EpsilonRouter     → zero-cost complexity classifier
  ContextInjector   → fact-grounded prompt builder (anti-hallucination)
  EpsilonLLM        → Ollama inference with tier routing + subprocess lifecycle
  CritiquePass      → algorithmic output validator (rejects hallucinations)
  AetherLink        → stdin/stdout JSON bridge for pipeline-mode
  VRAMGuard         → Python-level VRAM budget tracker (native .so optional)
  SparseKVCache     → INT8 ring-buffer token cache for multi-turn queries
"""
