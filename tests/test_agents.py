import json
import unittest

from nova import application


class AgentPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = json.loads(
            application.RULES_PATH.read_text(encoding="utf-8")
        )

    def test_clean_document_is_auto_approved_without_extra_llm_calls(self):
        extracted = application.demo_extract("clean-commercial-invoice.pdf")
        validation = application.validator_agent(extracted, self.rules, "demo")
        decision = application.router_agent(validation, "demo")

        self.assertEqual(
            validation["summary"],
            {"match": 8, "mismatch": 0, "uncertain": 0},
        )
        self.assertEqual(decision["outcome"], "auto_approve")

    def test_messy_document_never_silently_approves(self):
        extracted = application.demo_extract("messy-commercial-invoice.pdf")
        validation = application.validator_agent(extracted, self.rules, "demo")
        decision = application.router_agent(validation, "demo")

        self.assertGreater(validation["summary"]["uncertain"], 0)
        self.assertNotEqual(decision["outcome"], "auto_approve")
        self.assertTrue(decision["draft_amendment"])


if __name__ == "__main__":
    unittest.main()

