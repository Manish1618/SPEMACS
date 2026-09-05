"""Language model access for the Copilot.

Two providers behind one interface:

  * GeminiProvider  -- calls the Gemini REST API with function declarations, so
                       the model chooses which retrieval tools to call.
  * OfflineProvider -- a deterministic planner used when no key is configured or
                       the API is unreachable, so the whole product still runs.

The offline provider is a genuine fallback planner, not a bank of prepared
answers. It reads the question, decides which tools to call from the words and
structures actually present in it, and then reports strictly what those tools
returned. It is weaker than the model at unusual phrasings, and it says so in
its own output rather than pretending otherwise.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

from app.core.config import settings

GEMINI_MODEL = "gemini-3.6-flash"
# Tried in order when the primary model is rate limited or unavailable.
FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-2.5-flash"]
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any]


@dataclass
class ModelTurn:
    """One step of the model's reasoning loop.

    raw_parts holds the model's content parts exactly as returned. They must be
    echoed back verbatim on the next turn: the parts carry a thought signature
    that the API requires for tool calling to work, and rebuilding them by hand
    drops it.
    """

    tool_calls: List[ToolCall] = field(default_factory=list)
    text: str = ""
    finished: bool = False
    raw_parts: List[Dict[str, Any]] = field(default_factory=list)


class LLMUnavailable(RuntimeError):
    pass


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str = GEMINI_MODEL, timeout: int = 45):
        self.api_key = api_key
        self.model = model
        self.active_model = model
        self.timeout = timeout

    @property
    def available(self) -> bool:
        key = self.api_key or ""
        return bool(key) and len(key) > 20 and "your_gemini" not in key

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST with backoff on rate limits, then fall back to a lighter model.

        Free-tier quota is per minute, so a burst of tool rounds can trip it
        mid-question. Retrying briefly and then dropping to a lighter model keeps
        a demonstration running rather than failing the whole answer.
        """
        last_error = ""
        for model in [self.model] + [m for m in FALLBACK_MODELS if m != self.model]:
            for attempt in range(3):
                try:
                    response = requests.post(
                        GEMINI_URL.format(model=model),
                        params={"key": self.api_key},
                        json=payload,
                        timeout=self.timeout,
                    )
                except requests.RequestException as exc:
                    last_error = f"network error: {exc}"
                    break

                if response.status_code == 200:
                    self.active_model = model
                    return response.json()

                last_error = f"{response.status_code}: {response.text[:200]}"

                if response.status_code == 429:
                    delay = _retry_delay(response) or (2 ** attempt)
                    if attempt < 2:
                        time.sleep(min(delay, 20))
                        continue
                    break  # move on to the next model
                if response.status_code >= 500:
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                        continue
                    break
                break  # 4xx other than rate limiting will not improve on retry

        raise LLMUnavailable(f"Gemini request failed ({last_error})")

    def step(
        self,
        system_instruction: str,
        contents: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float = 0.1,
        json_mode: bool = False,
        max_output_tokens: int = 4096,
    ) -> ModelTurn:
        """One turn: the model either requests tool calls or produces final text.

        json_mode constrains the reply to a bare JSON object. Without it the model
        wraps the object in a code fence, and a long answer can be cut off before
        the closing brace, leaving nothing parseable.
        """
        generation: Dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        }
        if json_mode:
            generation["responseMimeType"] = "application/json"

        payload: Dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": contents,
            "generationConfig": generation,
        }
        if tools:
            payload["tools"] = [{"functionDeclarations": tools}]

        data = self._post(payload)
        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMUnavailable("Gemini returned no candidates.")

        parts = (candidates[0].get("content") or {}).get("parts") or []
        turn = ModelTurn(raw_parts=parts)
        for part in parts:
            if "functionCall" in part:
                call = part["functionCall"]
                turn.tool_calls.append(
                    ToolCall(name=call.get("name", ""), arguments=call.get("args") or {})
                )
            elif "text" in part:
                turn.text += part["text"]

        turn.finished = not turn.tool_calls
        return turn

    def complete_json(self, system_instruction: str, prompt: str) -> Optional[Dict[str, Any]]:
        """Ask for a single JSON object and parse it."""
        payload = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 3000,
                "responseMimeType": "application/json",
            },
        }
        data = self._post(payload)
        candidates = data.get("candidates") or []
        if not candidates:
            return None
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts).strip()
        return _loads(text)


def _retry_delay(response: "requests.Response") -> Optional[float]:
    """Seconds the API asked us to wait, when it says so."""
    try:
        details = response.json().get("error", {}).get("details", [])
    except ValueError:
        return None
    for detail in details:
        raw = detail.get("retryDelay")
        if isinstance(raw, str) and raw.endswith("s"):
            try:
                return float(raw[:-1])
            except ValueError:
                continue
    return None


def _loads(text: str) -> Optional[Dict[str, Any]]:
    """Parse a JSON object, tolerating fenced code blocks."""
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    text = text.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def get_provider() -> Optional[GeminiProvider]:
    provider = GeminiProvider(settings.GEMINI_API_KEY)
    return provider if provider.available else None
