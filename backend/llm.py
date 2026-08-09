"""OpenAI 兼容的模型客户端。换厂商只需改 .env 里的 base_url / model。

两种运行模式：
  live  —— 真实调用 API（需要 LLM_API_KEY）
  mock  —— 走 mock_llm.py 里的规则桩，无 key 也能跑通全流程 / 现场演示兜底
"""

from __future__ import annotations

import json
import re
from typing import AsyncIterator

from openai import AsyncOpenAI

from config import SETTINGS

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class LLMClient:
    def __init__(self) -> None:
        self.live = SETTINGS.live
        self.model = SETTINGS.model
        self._client: AsyncOpenAI | None = None
        if self.live:
            self._client = AsyncOpenAI(api_key=SETTINGS.api_key, base_url=SETTINGS.base_url)

    @property
    def mode(self) -> str:
        return "live" if self.live else "mock"

    def _require(self) -> AsyncOpenAI:
        if self._client is None:
            raise RuntimeError("当前为 mock 模式，不应调用真实 API")
        return self._client

    async def json_completion(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 500,
    ) -> dict:
        """要求模型返回 JSON 对象。带一层容错解析，避免模型多吐了包裹文字就崩掉。"""
        resp = await self._require().chat.completions.create(
            model=model or self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return parse_json(resp.choices[0].message.content or "")

    async def stream_completion(
        self,
        system: str,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float = 0.85,
        max_tokens: int = 400,
    ) -> AsyncIterator[str]:
        stream = await self._require().chat.completions.create(
            model=model or self.model,
            messages=[{"role": "system", "content": system}, *messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


def parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[-1] if "\n" in raw else raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(raw)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    raise ValueError(f"模型未返回可解析的 JSON: {raw[:200]!r}")


CLIENT = LLMClient()
