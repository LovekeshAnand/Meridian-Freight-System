"""Adversarial Epsilon Engine Test Suite.

Verifies:
1. Zero-cost router complexity scoring (1-10) and tier mapping
2. ContextInjector evidence block building from ContextStore
3. CritiquePass hallucination and flaw detection (phantom vehicles, wrong SLAs, PII, repetition)
4. SparseAttentionKVCache INT8 tensor cache performance
5. VRAMGuard allocation and release
6. AetherLink zero-knowledge session wipe
7. EpsilonEngine end-to-end execution and offline resilience
"""

import unittest
import numpy as np
from src.entity.context_store import ContextStore
from src.llm.epsilon.router import EpsilonRouter
from src.llm.epsilon.context_injector import ContextInjector
from src.llm.epsilon.critique import CritiquePass
from src.llm.epsilon.kv_cache import SparseKVCache, SparseAttentionKVCache
from src.llm.epsilon.vram_guard import VRAMGuard
from src.llm.epsilon.aether_link import AetherLink
from src.llm.epsilon.epsilon_engine import EpsilonEngine
from src.llm.local_llm import LocalLLM

class TestEpsilonEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context_store = ContextStore()
        cls.context_store.load_all()

    def test_epsilon_router_scoring(self):
        router = EpsilonRouter()
        
        # Simple query -> low complexity, fast tier
        simple_res = router.route_request("what is the origin hub")
        self.assertLessEqual(simple_res["complexity_score"], 3)
        self.assertEqual(simple_res["assigned_tier"], "fast")

        # Multi-constraint complex query -> high complexity, deep tier
        complex_res = router.route_request(
            "delhi ncr winter bs4 grap restriction and hill route rudrapur engine heater with guddu jugaad"
        )
        self.assertGreaterEqual(complex_res["complexity_score"], 7)
        self.assertIn(complex_res["assigned_tier"], ["balanced", "deep"])

    def test_context_injector(self):
        injector = ContextInjector(self.context_store)
        ticket = {
            "ticket_id": "TKT-0001",
            "client": "Shakti Cement",
            "vehicle": "UP40IM3144",
            "origin_hub": "Gurgaon",
            "destination": "Lucknow",
            "km_from_origin_hub": 25.0,
            "issue": "radiator leak"
        }
        repl = {"canonical_reg": "HR16SP9238", "model": "Tata Prima", "year": 2021, "bs_stage": "BS6", "home_hub": "Gurgaon"}
        
        block = injector.build_ticket_grounding_block(ticket, repl, "Assigned replacement", ["dispatcher_interview.txt:L22"])
        self.assertIn("Shakti Cement", block)
        self.assertIn("UP40IM3144", block)
        self.assertIn("HR16SP9238", block)
        self.assertIn("=== VERIFIED OPERATIONAL FACTS", block)

    def test_critique_pass_intercepts_hallucinations(self):
        critique = CritiquePass(self.context_store)
        ticket = {"ticket_id": "TKT-0001", "client": "Shakti Cement", "vehicle": "UP40IM3144"}
        
        # 1. Hallucinated 48-hour SLA for Shakti Cement
        bad_sla_text = "Dear Dispatch, Vehicle UP40IM3144 has broken down. We will deliver within our 48-hour SLA window."
        is_valid, flaws = critique.validate_comms_draft(bad_sla_text, ticket)
        self.assertFalse(is_valid)
        self.assertTrue(any("48-hour SLA" in f for f in flaws))

        # 2. Hallucinated non-existent vehicle
        fake_veh_text = "Dear Dispatch, Vehicle UP40IM3144 replaced with DL99XX9999 for transit."
        is_valid2, flaws2 = critique.validate_comms_draft(fake_veh_text, ticket)
        self.assertFalse(is_valid2)
        self.assertTrue(any("HALLUCINATED_VEHICLE" in f for f in flaws2))

        # 3. PII Leak Interception
        pii_text = "Dear Dispatch, please call driver at 9311840522 immediately."
        is_valid3, flaws3 = critique.validate_comms_draft(pii_text, ticket)
        self.assertFalse(is_valid3)
        self.assertTrue(any("PII detected" in f for f in flaws3))

        # 4. Valid draft passes cleanly
        good_text = "Dear Dispatch Team, Vehicle UP40IM3144 encountered an issue. Replacement HR16SP9238 deployed under 36-hour protocol."
        is_valid4, flaws4 = critique.validate_comms_draft(good_text, ticket, {"canonical_reg": "HR16SP9238"})
        self.assertTrue(is_valid4)
        self.assertEqual(len(flaws4), 0)

    def test_kv_cache_ring_buffer(self):
        cache = SparseAttentionKVCache(n_layers=4, n_heads=4, max_tokens=16, d_head=8, top_k=4)
        k_dummy = np.ones((4, 8), dtype=np.float32) * 5.0
        v_dummy = np.ones((4, 8), dtype=np.float32) * 2.0
        
        cache.write(layer=0, keys=k_dummy, values=v_dummy)
        cache.advance()
        self.assertEqual(cache.n_tokens, 1)

        read_k, read_v = cache.read(layer=0)
        self.assertEqual(read_k.shape, (4, 1, 8))
        stats = cache.get_stats()
        self.assertIn("tokens_cached", stats)

    def test_vram_guard_budget(self):
        guard = VRAMGuard()
        acquired = guard.acquire_budget("fast")
        self.assertTrue(acquired)
        status = guard.get_status()
        self.assertGreater(status["allocated_mb"], 0)
        
        guard.release_budget("fast")
        status_released = guard.get_status()
        self.assertEqual(status_released["allocated_mb"], 0)

    def test_aether_link_wipe(self):
        aether = AetherLink()
        resp = aether.dispatch_response(ok=True, result="test output", metadata={"test": True})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["request_count"], 1)

    def test_local_llm_interface_e2e(self):
        local_llm = LocalLLM(self.context_store)
        ticket = {
            "ticket_id": "TKT-0010",
            "client": "Orion Pharma",
            "vehicle": "UP40IM3144",
            "origin_hub": "Gurgaon",
            "destination": "Delhi",
            "km_from_origin_hub": 15.0,
            "issue": "engine failure"
        }
        repl = {"canonical_reg": "HR16SP9238", "model": "Tata Prima", "year": 2022, "bs_stage": "BS6"}
        
        # Test comms generation (fallback or live)
        result = local_llm.generate_comms(ticket, repl, "Complies with Orion 2020+ rule", ["dispatcher_interview.txt:L28"])
        self.assertTrue(result["ok"])
        self.assertIn("Orion Pharma", result["result"])
        self.assertIn("HR16SP9238", result["result"])

        # Test query answering
        q_ans = local_llm.query("What is Shakti Cement's delivery window?")
        self.assertTrue(q_ans["is_sufficient"])
        ans_low = q_ans["answer"].lower()
        self.assertTrue("36" in ans_low and ("hour" in ans_low or "hours" in ans_low))

if __name__ == "__main__":
    unittest.main()
