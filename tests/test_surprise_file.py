"""Surprise File Schema Drift & Grounded Q&A Tests."""
import json
import tempfile
import unittest
from pathlib import Path

from src.entity.context_store import ContextStore
from src.pipeline.processor import BreakdownPipeline
from src.pipeline.state_manager import StateManager
from src.query.engine import GroundedQueryEngine
from src.surprise.drift_adapter import SurpriseDriftAdapter


def _make_clean_pipeline(ctx: ContextStore = None) -> BreakdownPipeline:
    """Creates a pipeline with a fresh temporary audit file (no historical state)."""
    if ctx is None:
        ctx = ContextStore()
        ctx.load_all()
    p = BreakdownPipeline(context_store=ctx)
    # Inject a fresh state manager with an isolated temp audit file
    tmp_audit = Path(tempfile.mktemp(suffix=".jsonl"))
    p.state_manager = StateManager(audit_path=tmp_audit)
    return p, tmp_audit


class TestSurpriseAndQuery(unittest.TestCase):
    def test_surprise_file_drift_adaptation(self):
        surprise_content = [
            {
                "id": "SURPRISE-TEST-01",
                "plate_no": "UP40IM3144",
                "driver": "DRV-001",
                "source_hub": "Lucknow",
                "distance_km": 15,
                "dest_hub": "Kanpur",
                "defect": "radiator leak",
                "priority": "HIGH",
                "customer": "Shakti Cement",
                "timestamp": "2026-08-15T10:00:00"
            },
            {
                "id": "SURPRISE-TEST-02",
                "plate_no": "INVALID??XYZ",
                "driver": "DRV-002",
                "source_hub": "",
                "distance_km": None,
                "customer": "Vertex Retail"
            }
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
            json.dump(surprise_content, tf)
            tf_path = Path(tf.name)

        tmp_audit = None
        try:
            records, alerts = SurpriseDriftAdapter.adapt_file(tf_path)
            self.assertEqual(len(records), 2)
            # New adapter uses "Remapped" for key mapping alerts
            self.assertTrue(
                any("Remapped" in a or "Mapped" in a for a in alerts),
                f"Expected drift mapping alert, got: {alerts}"
            )

            # Feed adapted records to pipeline via a temp queue file
            adapted_temp = Path(tempfile.mktemp(suffix=".json"))
            adapted_temp.write_text(json.dumps(records), encoding="utf-8")

            pipeline, tmp_audit = _make_clean_pipeline()
            res = pipeline.process_ticket_queue(adapted_temp)

            # SURPRISE-TEST-01 is valid (UP40IM3144 is real), SURPRISE-TEST-02 is invalid
            self.assertEqual(res["valid_processed"], 1, f"Expected 1 valid, got: {res}")
            self.assertEqual(res["quarantined"], 1, f"Expected 1 quarantined, got: {res}")
        finally:
            if tf_path.exists():
                tf_path.unlink()
            if tmp_audit and tmp_audit.exists():
                tmp_audit.unlink()

    def test_grounded_query_engine(self):
        engine = GroundedQueryEngine()

        res = engine.query("What is Shakti Cement's delivery window?")
        self.assertTrue(res["is_sufficient"])
        self.assertIn("36-hour", res["answer"])
        self.assertIn("dispatcher_interview.txt:L22", res["citations"])

        res2 = engine.query("What is the name of the CEO's dog?")
        self.assertFalse(res2["is_sufficient"])
        self.assertIn("Insufficient data", res2["answer"])


if __name__ == "__main__":
    unittest.main()
