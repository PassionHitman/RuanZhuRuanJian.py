"""DeepSeek API 客户端封装（兼容 OpenAI SDK）。"""
from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import get_api_key, load_config


class DeepSeekClient:
    """封装 DeepSeek API 调用，提供同步和流式两种方式。"""

    def __init__(self) -> None:
        config = load_config()
        self._client = OpenAI(
            base_url=config["deepseek_base_url"],
            api_key=get_api_key(),
        )
        self._model = config["deepseek_model"]

    @property
    def is_configured(self) -> bool:
        return bool(get_api_key())

    def chat(
        self,
        user_prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 16000,
        response_json: bool = False,
    ) -> str:
        """同步调用 DeepSeek Chat API，返回文本响应。"""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_json:
            kwargs["response_format"] = {"type": "json_object"}

        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def chat_json(
        self,
        user_prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 16000,
    ) -> dict[str, Any]:
        """同步调用并返回 JSON 对象。"""
        text = self.chat(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_json=True,
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试从文本中提取 JSON 块
            import re

            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                return json.loads(match.group())
            raise ValueError(f"无法解析 DeepSeek 返回的 JSON: {text[:500]}")


# 全局单例
_client: DeepSeekClient | None = None


def get_client() -> DeepSeekClient:
    global _client
    if _client is None:
        _client = DeepSeekClient()
    return _client
