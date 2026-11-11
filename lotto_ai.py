# -*- coding: utf-8 -*-
"""免费的 OpenAI 兼容大模型接入层（可选功能）。

主程序数据不足/随机森林不理想时，可把候选号码池交给免费大模型做
二次加权选号。纯离线环境下该模块自动降级为随机补充，不影响主流程。

适配的免费/低价 OpenAI 兼容端点（国内可直连）：
  - SiliconFlow 硅基流动  https://api.siliconflow.cn/v1
  - DeepSeek              https://api.deepseek.com/v1
  - 智谱GLM               https://open.bigmodel.cn/api/paas/v4
  - 阿里云百炼 Qwen       https://dashscope.aliyuncs.com/compatible-mode/v1
  - OpenRouter(免费模型)  https://openrouter.ai/api/v1

你需要在自己对应的开放平台申请 API Key 并填入“AI/模型设置”。
"""
import json
import threading

import requests


# 兼容的免费模型清单（随更新，用户可自行改 base_url / model）
PROVIDER_PRESETS = {
    "SiliconFlow(硅基流动)": {
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "deepseek-ai/DeepSeek-V3",
        "free": True,
    },
    "DeepSeek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "free": False,
    },
    "智谱GLM": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "free": True,
    },
    "阿里百炼Qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "free": False,
    },
    "OpenRouter(免费)": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "free": True,
    },
}


class AIConfig:
    """AI 连接配置，可从 JSON 文件读写。"""
    def __init__(self):
        self.enabled = False
        self.provider = "SiliconFlow(硅基流动)"
        self.base_url = PROVIDER_PRESETS[self.provider]["base_url"]
        self.model = PROVIDER_PRESETS[self.provider]["model"]
        self.api_key = ""
        self.timeout = 30

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d):
        c = cls()
        for k, v in (d or {}).items():
            if hasattr(c, k):
                setattr(c, k, v)
        return c


def chat_once(config, prompt, system="你是资深彩票数据分析助手，只输出号码，不解释。",
              log=None):
    """调用一次 OpenAI 兼容 chat 接口。返回 (ok, text)。失败时 ok=False。"""
    if not config or not config.enabled or not config.api_key:
        if log:
            log("AI未启用或未填Key，跳过")
        return False, ""
    url = (config.base_url.rstrip("/")) + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.9,
        "max_tokens": 300,
    }
    try:
        if log:
            log(f"🤖 正在调用 {config.model} ...")
        r = requests.post(url, headers=headers, json=body, timeout=config.timeout)
        if r.status_code != 200:
            if log:
                log(f"AI HTTP {r.status_code}: {r.text[:200]}")
            return False, ""
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        return True, content
    except Exception as e:
        if log:
            log(f"AI调用异常：{e}")
        return False, ""


def chat_async(config, prompt, callback, log=None):
    """后台线程调用 AI，回调 callback(ok, text)。不阻塞 UI。"""
    def _run():
        ok, text = chat_once(config, prompt, log=log)
        try:
            callback(ok, text)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()
    return True


def extract_numbers(text, count=5):
    """从模型输出里尽量提炼出合法号码（1-35/1-12 由调用方限定校验）。"""
    if not text:
        return []
    for sep in [",", "，", "、", "。", ";", "；", " ", "\n", "\t"]:
        text = text.replace(sep, " ")
    nums = [int(x) for x in text.split() if x.isdigit()]
    return nums


def validate_numbers(nums, low, high, count):
    """去重、限界、截取 count 个。不足则用 1..high 顺序补齐。"""
    result = []
    for n in nums:
        if low <= n <= high and n not in result:
            result.append(n)
        if len(result) >= count:
            break
    filler = (n for n in range(low, high + 1))
    while len(result) < count:
        n = next(filler)
        if n not in result:
            result.append(n)
    return sorted(result[:count])