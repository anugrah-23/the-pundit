"""LLM providers behind one small interface: Gemini, Groq (OpenAI-compatible) and a mock."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResult:
    text: str
    tokens: int
    model: str


class LLM:
    name: str

    def complete(self, system: str, user: str, temperature: float = 0.3, json_mode: bool = False) -> LLMResult:
        raise NotImplementedError


class GeminiLLM(LLM):
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, model: str, api_key: str, timeout: float = 30.0):
        if not api_key:
            raise LLMError("PUNDIT_GEMINI_API_KEY is not set")
        self.name = model
        self.api_key = api_key
        self.client = httpx.Client(timeout=timeout)

    def complete(self, system, user, temperature=0.3, json_mode=False):
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": temperature},
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        r = self.client.post(self.URL.format(model=self.name), json=body, headers={"x-goog-api-key": self.api_key})
        if r.status_code != 200:
            raise LLMError(f"gemini {r.status_code}: {r.text[:200]}")
        data = r.json()
        try:
            text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError) as e:
            raise LLMError(f"gemini returned no text: {str(data)[:200]}") from e
        tokens = data.get("usageMetadata", {}).get("totalTokenCount", 0)
        return LLMResult(text.strip(), tokens, self.name)


class GroqLLM(LLM):
    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, model: str, api_key: str, timeout: float = 30.0):
        if not api_key:
            raise LLMError("PUNDIT_GROQ_API_KEY is not set")
        self.name = model
        self.api_key = api_key
        self.client = httpx.Client(timeout=timeout)

    def complete(self, system, user, temperature=0.3, json_mode=False):
        body = {
            "model": self.name,
            "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = self.client.post(self.URL, json=body, headers={"Authorization": f"Bearer {self.api_key}"})
        if r.status_code != 200:
            raise LLMError(f"groq {r.status_code}: {r.text[:200]}")
        data = r.json()
        text = data["choices"][0]["message"]["content"] or ""
        return LLMResult(text.strip(), data.get("usage", {}).get("total_tokens", 0), self.name)


class MockLLM(LLM):
    """Deterministic stand-in for tests and keyless local development.

    As an answerer it repeats the first sentence of the first document. As a judge it
    returns a passing faithfulness verdict, or a pairwise verdict favouring the answer
    that contains more digits (a crude proxy for "cites numbers").
    """

    def __init__(self, name: str = "mock"):
        self.name = name

    def complete(self, system, user, temperature=0.3, json_mode=False):
        if json_mode and "Answer A" in user:
            a = re.search(r"Answer A:\n(.*?)\n\nAnswer B:", user, re.S)
            b = re.search(r"Answer B:\n(.*?)(\n\n|$)", user, re.S)
            da = len(re.findall(r"\d", a.group(1))) if a else 0
            db = len(re.findall(r"\d", b.group(1))) if b else 0
            winner = "A" if da > db else "B" if db > da else "tie"
            return LLMResult(json.dumps({"winner": winner, "reason": "mock: more figures"}), 0, self.name)
        if json_mode:
            return LLMResult(json.dumps({"faithful": True, "unsupported_claims": [], "score": 4, "reason": "mock"}), 0, self.name)
        m = re.search(r"<document[^>]*>\n(.*?)\n</document>", user, re.S)
        if not m:
            return LLMResult("I don't have data on that.", 0, self.name)
        first = re.split(r"(?<=[.!?])\s", m.group(1).strip())[0]
        return LLMResult(first, 0, self.name)


def make_llm(provider: str, model: str, gemini_key: str = "", groq_key: str = "") -> LLM:
    if provider == "gemini":
        return GeminiLLM(model, gemini_key)
    if provider == "groq":
        return GroqLLM(model, groq_key)
    return MockLLM(f"mock-{model}")


def parse_json(text: str) -> dict:
    """Parse a JSON object from a model reply, tolerating code fences and stray prose."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise
