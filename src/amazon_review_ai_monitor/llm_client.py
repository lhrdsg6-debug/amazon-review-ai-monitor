from __future__ import annotations

from dataclasses import dataclass
import json
import random
import re
import time
from typing import Any

import requests


@dataclass
class LLMResult:
    content: str
    usage: dict[str, int]
    cost_usd: float


class LLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        input_usd_per_1m: float,
        output_usd_per_1m: float,
        timeout_seconds: int = 90,
        max_attempts: int = 6,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.input_usd_per_1m = input_usd_per_1m
        self.output_usd_per_1m = output_usd_per_1m
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts

    def chat(self, system: str, user: str, temperature: float = 0.2) -> LLMResult:
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }

        for attempt in range(1, self.max_attempts + 1):
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt == self.max_attempts:
                    break
                sleep_seconds = min(60, 2 ** (attempt - 1)) + random.random()
                print(
                    f"Claude API busy/rate limited ({response.status_code}); "
                    f"retrying in {sleep_seconds:.1f}s..."
                )
                time.sleep(sleep_seconds)
                continue

            response.raise_for_status()
            data = response.json()
            content = _extract_content(data)
            usage = _normalize_usage(data.get("usage") or {})
            cost = (
                usage["input_tokens"] / 1_000_000 * self.input_usd_per_1m
                + usage["output_tokens"] / 1_000_000 * self.output_usd_per_1m
            )
            return LLMResult(content=content, usage=usage, cost_usd=cost)

        response.raise_for_status()
        raise RuntimeError("Claude API request failed after retries")


def _extract_content(data: dict[str, Any]) -> str:
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        return "\n".join(parts).strip()
    anthropic_content = data.get("content")
    if isinstance(anthropic_content, list):
        return "\n".join(
            str(item.get("text", "")) for item in anthropic_content if isinstance(item, dict)
        ).strip()
    return ""


def _normalize_usage(usage: dict[str, Any]) -> dict[str, int]:
    input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    output_tokens = int(
        usage.get("completion_tokens") or usage.get("output_tokens") or 0
    )
    total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if fenced:
        return json.loads(fenced.group(1))

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise ValueError("LLM response did not contain a JSON object")
