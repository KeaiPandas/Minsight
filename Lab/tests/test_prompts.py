# -*- coding: utf-8 -*-

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROMPT_DIR = ROOT / "Core" / "prompts" / "v2"


class PromptQualityTests(unittest.TestCase):
    def test_v2_prompts_include_role_rules_steps_and_few_shot(self):
        required = {
            "normalize.txt": ["{{TRANSCRIPT}}", "{{MEETING_INFO}}"],
            "key_points.txt": ["{{TRANSCRIPT}}"],
            "actions_decisions.txt": ["{{TRANSCRIPT}}", "{{ALIAS_MAP}}", "{{MEETING_DATE}}"],
            "repair.txt": ["{{ERROR}}", "{{RAW}}"],
        }

        for name, placeholders in required.items():
            with self.subTest(prompt=name):
                text = (PROMPT_DIR / name).read_text(encoding="utf-8")

                self.assertIn("【System / 角色】", text)
                self.assertIn("【内部分析步骤】", text)
                self.assertIn("【规则】", text)
                self.assertIn("【Few-shot】", text)
                self.assertIn("只输出 JSON", text)
                for placeholder in placeholders:
                    self.assertIn(placeholder, text)


if __name__ == "__main__":
    unittest.main()
