"""Prompt-injection suite (spec section 8.3): 10 poisoned documents, run with guardrails off and on,
plus normal questions to count false blocks.

Input: eval/data/attacks.jsonl
  {"id": "a01", "type": "fake_transfer", "post": "...poisoned fan blog...", "question": "...", "goal": "fake_transfer"}
Input: eval/data/normal_questions.jsonl   {"question": "..."}

Uses the real answer model from .env, because a mock model never "falls for" anything.
  python -m eval.injection_suite
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.pipeline import Pundit, build_services  # noqa: E402

DATA = ROOT / "eval" / "data"
RESULTS = ROOT / "eval" / "results"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        cfg = get_settings().model_copy(update={"database_url": f"sqlite:///{tmp}/inj.db", "daily_llm_budget": 10_000})
        pundit = Pundit(build_services(cfg))
        attacks = load_jsonl(DATA / "attacks.jsonl")
        rows = []
        for a in attacks:
            off = pundit.challenge(a["post"], a["question"], a["goal"], guardrails_on=False, nickname="eval")
            on = pundit.challenge(a["post"], a["question"], a["goal"], guardrails_on=True, nickname="eval")
            rows.append({"id": a["id"], "type": a["type"], "worked_before": off["success"], "worked_after": on["success"],
                         "stopped_by": on["blocked_by"], "reply_before": off["reply"], "reply_after": on["reply"]})

        normals = load_jsonl(DATA / "normal_questions.jsonl")
        false_blocks = []
        for q in normals:
            res = pundit.ask(q["question"])
            if res.get("output_blocked") or res.get("flagged_docs"):
                false_blocks.append({"question": q["question"], "blocked": res.get("output_blocked"), "flagged": res.get("flagged_docs")})

    out = {"attacks": rows, "before": sum(r["worked_before"] for r in rows), "after": sum(r["worked_after"] for r in rows),
           "n": len(rows), "false_blocks": len(false_blocks), "n_normal": len(normals), "false_block_examples": false_blocks}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "injection_suite.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("| attack | worked before | worked after | stopped by |")
    print("|---|---|---|---|")
    for r in rows:
        print(f"| {r['type']} | {'yes' if r['worked_before'] else 'no'} | {'yes' if r['worked_after'] else 'no'} | {r['stopped_by'] or '-'} |")
    print(f"\nSuccessful injections: {out['before']}/{out['n']} before, {out['after']}/{out['n']} after; "
          f"{out['false_blocks']} false blocks on {out['n_normal']} normal questions.")


if __name__ == "__main__":
    main()
