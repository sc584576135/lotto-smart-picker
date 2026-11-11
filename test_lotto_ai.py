# -*- coding: utf-8 -*-
import sys, types, unittest

# 桩 requests，防止真实网络
fake_req = types.ModuleType("requests")
class _R:
    status_code = 200
    text = ""
    def json(self):
        return {"choices": [{"message": {"content": "1 3 5 7 9"}}]}
fake_req.post = lambda *a, **k: _R()
sys.modules["requests"] = fake_req

import lotto_ai as ai

class TestAI(unittest.TestCase):
    def test_extract(self):
        self.assertEqual(ai.extract_numbers("1,3、5 7。9"), [1, 3, 5, 7, 9])

    def test_validate(self):
        # 越界/重复/截断
        out = ai.validate_numbers([1, 1, 2, 88, 3, 4, 5, 6], 1, 35, 5)
        self.assertEqual(out, [1, 2, 3, 4, 5])
        # 不足则补齐
        out2 = ai.validate_numbers([1], 1, 12, 2)
        self.assertEqual(out2, [1, 2])

    def test_chat_once_ok(self):
        cfg = ai.AIConfig(); cfg.enabled = True; cfg.api_key = "k";
        cfg.base_url = "https://x/v1"; cfg.model = "m"; cfg.timeout = 5
        ok, text = ai.chat_once(cfg, "帮我选5个前区号")
        self.assertTrue(ok)
        self.assertIn("1 3 5 7 9", text)

    def test_chat_once_disabled(self):
        cfg = ai.AIConfig(); cfg.enabled = False
        ok, text = ai.chat_once(cfg, "x")
        self.assertFalse(ok)
        self.assertEqual(text, "")

    def test_presets(self):
        self.assertIn("DeepSeek", ai.PROVIDER_PRESETS)
        self.assertIn("SiliconFlow(硅基流动)", ai.PROVIDER_PRESETS)

if __name__ == "__main__":
    unittest.main()