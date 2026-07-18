# -*- coding: utf-8 -*-

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROMPT_DIR = ROOT / "Core" / "prompts" / "v2"


class PromptQualityTests(unittest.TestCase):
    def test_v2_prompts_include_role_rules_steps_and_few_shot(self):
        required_placeholders = {
            "normalize.txt": ["{{TRANSCRIPT}}", "{{MEETING_INFO}}"],
            "key_points.txt": ["{{TRANSCRIPT}}"],
            "key_points_reduce.txt": ["{{CANDIDATES}}"],
            "actions_decisions.txt": ["{{TRANSCRIPT}}", "{{ALIAS_MAP}}", "{{MEETING_DATE}}"],
            "decision_filter.txt": ["{{CANDIDATES}}"],
            "repair.txt": ["{{ERROR}}", "{{RAW}}"],
        }
        structured_english_prompts = {"key_points_reduce.txt", "decision_filter.txt"}

        for name, placeholders in required_placeholders.items():
            with self.subTest(prompt=name):
                text = (PROMPT_DIR / name).read_text(encoding="utf-8")

                if name in structured_english_prompts:
                    self.assertIn("[System / Role]", text)
                    self.assertIn("[Internal Analysis Steps]", text)
                    self.assertIn("[Rules]", text)
                    self.assertIn("[Few-shot]", text)
                    self.assertIn("Output JSON only", text)
                else:
                    self.assertIn("JSON", text)
                for placeholder in placeholders:
                    self.assertIn(placeholder, text)


if __name__ == "__main__":
    unittest.main()
