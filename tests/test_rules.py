"""Expert Rules and Client SLA Verification Test Suite."""
import unittest
from datetime import datetime

from src.rules.expert_rules import ExpertRulesEngine

class TestExpertRules(unittest.TestCase):
    def setUp(self):
        self.engine = ExpertRulesEngine()

    def test_rule_origin_vs_nearest_hub(self):
        # <= 50km must be origin hub
        res_text, cits = self.engine.evaluate_origin_vs_nearest_hub(20.0, "Lucknow")
        self.assertIn("origin hub 'Lucknow'", res_text)
        self.assertIn("dispatcher_interview.txt:L36-37", cits)

        # > 50km nearest hub
        res_text, cits = self.engine.evaluate_origin_vs_nearest_hub(120.0, "Lucknow")
        self.assertIn("nearest hub", res_text)

    def test_rule_delhi_ncr_winter_bs4_ban(self):
        # December in Delhi with BS4 -> FAIL
        dec_date = datetime(2026, 12, 15)
        res = self.engine.check_delhi_ncr_winter_bs_stage(["Delhi", "Gurgaon"], "BS4", dec_date)
        self.assertFalse(res.is_compliant)
        self.assertEqual(res.rule_id, "RULE-DISP-02")

        # December in Delhi with BS6 -> PASS
        res = self.engine.check_delhi_ncr_winter_bs_stage(["Delhi", "Gurgaon"], "BS6", dec_date)
        self.assertTrue(res.is_compliant)

        # July in Delhi with BS4 -> PASS (summer)
        jul_date = datetime(2026, 7, 15)
        res = self.engine.check_delhi_ncr_winter_bs_stage(["Delhi"], "BS4", jul_date)
        self.assertTrue(res.is_compliant)

    def test_rule_hill_route_engine_heater_and_brake(self):
        dec_date = datetime(2026, 12, 10)
        
        # Rudrapur in winter with no heater -> FAIL
        res = self.engine.check_hill_route_requirements(["Rudrapur"], "No", False, dec_date)
        self.assertFalse(res.is_compliant)
        self.assertEqual(res.rule_id, "RULE-DISP-03")

        # Rudrapur with brake work in last 30 days -> FAIL
        res = self.engine.check_hill_route_requirements(["Rudrapur"], "Yes", True, dec_date)
        self.assertFalse(res.is_compliant)
        self.assertEqual(res.rule_id, "RULE-DISP-04")

        # Compliant
        res = self.engine.check_hill_route_requirements(["Rudrapur"], "Yes", False, dec_date)
        self.assertTrue(res.is_compliant)

    def test_rule_shakti_sla_and_client_overrides(self):
        res = self.engine.get_client_sla_and_rules("Shakti Cement", datetime(2026, 5, 1), 24.0, "Kanpur")
        self.assertEqual(res["sla_hours"], 36.0)
        self.assertIn("dispatcher_interview.txt:L22", res["citations"])

    def test_rule_monsoon_eastern_buffer(self):
        aug_date = datetime(2026, 8, 15)
        res = self.engine.get_client_sla_and_rules("Shakti Cement", aug_date, 20.0, "Lucknow")
        self.assertTrue(any("+20%" in s for s in res["special_instructions"]))

if __name__ == "__main__":
    unittest.main()
