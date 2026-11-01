"""LLM-as-judge: faithfulness gate for the cache, and bias-controlled pairwise judging."""
from __future__ import annotations

from dataclasses import dataclass, field

from .corpus import Doc
from .guardrails import spotlight
from .llm import LLM, LLMError, parse_json
from .prompts import FAITHFULNESS_SYSTEM, FAITHFULNESS_USER, PAIRWISE_SYSTEM, PAIRWISE_USER


@dataclass
class Faithfulness:
    passed: bool
    faithful: bool
    score: int
    unsupported: list[str] = field(default_factory=list)
    reason: str = ""
    error: str | None = None
    tokens: int = 0


@dataclass
class Pairwise:
    order_ab: str  # winner when shown as (first, second): "first" | "second" | "tie"
    order_ba: str  # winner when shown swapped, mapped back to the original labels
    final: str  # "first" | "second" | "tie": a win counts only if it holds in both orders
    reason: str = ""
    tokens: int = 0


class Judge:
    def __init__(self, llm: LLM, pass_score: int = 4):
        self.llm = llm
        self.pass_score = pass_score

    def faithfulness(self, question: str, docs: list[Doc], answer: str) -> Faithfulness:
        user = FAITHFULNESS_USER.format(documents=spotlight(docs), question=question, answer=answer)
        try:
            res = self.llm.complete(FAITHFULNESS_SYSTEM, user, temperature=0.0, json_mode=True)
            data = parse_json(res.text)
        except (LLMError, ValueError) as e:
            # Fail closed: an answer the judge could not check is never cached.
            return Faithfulness(False, False, 0, error=str(e)[:200])
        faithful = bool(data.get("faithful", False))
        score = int(data.get("score", 0) or 0)
        return Faithfulness(
            passed=faithful and score >= self.pass_score, faithful=faithful, score=score,
            unsupported=[str(c) for c in data.get("unsupported_claims", [])][:5],
            reason=str(data.get("reason", ""))[:300], tokens=res.tokens,
        )

    def _one(self, question: str, a: str, b: str, docs: list[Doc]) -> tuple[str, str, int]:
        documents = spotlight(docs) if docs else ""
        user = PAIRWISE_USER.format(documents=documents, question=question, answer_a=a, answer_b=b)
        res = self.llm.complete(PAIRWISE_SYSTEM, user, temperature=0.0, json_mode=True)
        data = parse_json(res.text)
        winner = str(data.get("winner", "tie")).strip().upper()
        return (winner if winner in {"A", "B"} else "TIE"), str(data.get("reason", ""))[:400], res.tokens

    def pairwise(self, question: str, first: str, second: str, docs: list[Doc] | None = None) -> Pairwise:
        docs = docs or []
        w1, r1, t1 = self._one(question, first, second, docs)
        w2, _, t2 = self._one(question, second, first, docs)
        ab = {"A": "first", "B": "second"}.get(w1, "tie")
        ba = {"A": "second", "B": "first"}.get(w2, "tie")
        final = ab if ab == ba else "tie"
        return Pairwise(ab, ba, final, r1, t1 + t2)
