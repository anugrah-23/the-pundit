"""LLM-as-judge audit (spec section 8.2).

Step 1, generate answers:   python -m eval.judge_audit answers
  reads eval/data/judge_questions.jsonl ({"id", "question"}), gets an answer from the answer model
  and from the opponent model, writes eval/data/judge_pairs.jsonl

Step 2, grade them yourself BEFORE looking at any judge output:
  fill eval/data/human_grades.jsonl with {"id": "...", "winner": "first" | "second" | "tie"}
  ("first" is the answer_model's answer, "second" the opponent's)

Step 3, run the judge and the bias tests:   python -m eval.judge_audit judge
  - agreement with you (X/30) and Cohen's kappa, single order
  - position bias: re-judge with order swapped, count flips
  - length bias: pad 10 answers with filler, count verdicts that move toward the padded answer
  - self-preference: let the opponent model judge, compare how often it picks its own answer vs you
  - fixed judge (both orders, length instruction, different family): agreement again
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.embeddings import make_embedder  # noqa: E402
from app.corpus import Corpus  # noqa: E402
from app.judge import Judge  # noqa: E402
from app.llm import make_llm, parse_json  # noqa: E402
from app.pipeline import cohens_kappa  # noqa: E402
from app.prompts import ANSWER_SYSTEM, ANSWER_USER  # noqa: E402
from app.guardrails import spotlight  # noqa: E402

DATA = ROOT / "eval" / "data"
RESULTS = ROOT / "eval" / "results"
PADDING = (" To restate the question for clarity, you asked about this specific statistic, which is an important"
           " and interesting topic in football. Overall, this is the answer based on the data available.")
# A deliberately naive judge prompt, used for the "before fixes" numbers.
NAIVE_SYSTEM = "You compare two answers to a football question. Reply with JSON only."
NAIVE_USER = 'Question: {question}\n\nAnswer A:\n{a}\n\nAnswer B:\n{b}\n\nWhich answer is better? Return JSON: {{"winner": "A" | "B" | "tie"}}'


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_jsonl(p: Path, rows: list[dict]) -> None:
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def answers() -> None:
    cfg = get_settings()
    keys = dict(gemini_key=cfg.gemini_api_key, groq_key=cfg.groq_api_key)
    first = make_llm(cfg.answer_provider, cfg.answer_model, **keys)
    second = make_llm(cfg.opponent_provider, cfg.opponent_model, **keys)
    embedder = make_embedder(cfg.embedder, cfg.embedding_model)
    corpus = Corpus.load(cfg.corpus_dir, embedder)
    rows = []
    for q in load_jsonl(DATA / "judge_questions.jsonl"):
        vec = embedder.encode([q["question"]])[0]
        docs = [d for d, _ in corpus.retrieve(vec, corpus.gazetteer.extract(q["question"]), cfg.top_k)]
        user = ANSWER_USER.format(documents=spotlight(docs), question=q["question"])
        system = ANSWER_SYSTEM.format(secret_clause="")
        rows.append({"id": q["id"], "question": q["question"], "doc_ids": [d.doc_id for d in docs],
                     "first_model": first.name, "first": first.complete(system, user).text,
                     "second_model": second.name, "second": second.complete(system, user).text})
    write_jsonl(DATA / "judge_pairs.jsonl", rows)
    print(f"wrote {len(rows)} pairs. Now grade them in eval/data/human_grades.jsonl before running the judge.")


def naive_verdict(llm, q, a, b) -> str:
    data = parse_json(llm.complete(NAIVE_SYSTEM, NAIVE_USER.format(question=q, a=a, b=b), temperature=0.0, json_mode=True).text)
    return str(data.get("winner", "tie")).upper()


def judge() -> None:
    cfg = get_settings()
    keys = dict(gemini_key=cfg.gemini_api_key, groq_key=cfg.groq_api_key)
    judge_llm = make_llm(cfg.judge_provider, cfg.judge_model, **keys)
    self_judge_llm = make_llm(cfg.opponent_provider, cfg.opponent_model, **keys)  # judges its own answers
    pairs = load_jsonl(DATA / "judge_pairs.jsonl")
    human = {g["id"]: g["winner"] for g in load_jsonl(DATA / "human_grades.jsonl")}
    pairs = [p for p in pairs if p["id"] in human]

    to_label = {"A": "first", "B": "second"}
    naive, flips, length_moves, self_pref_second = [], 0, 0, 0
    examples = []
    for i, p in enumerate(pairs):
        v1 = to_label.get(naive_verdict(judge_llm, p["question"], p["first"], p["second"]), "tie")
        v2 = {"A": "second", "B": "first"}.get(naive_verdict(judge_llm, p["question"], p["second"], p["first"]), "tie")
        naive.append(v1)
        if v1 != v2:
            flips += 1
            if len(examples) < 2:
                examples.append({"question": p["question"], "first_order": v1, "swapped_order": v2})
        if i < 10:
            padded = to_label.get(naive_verdict(judge_llm, p["question"], p["first"] + PADDING, p["second"]), "tie")
            if v1 != "first" and padded == "first":
                length_moves += 1
        if to_label.get(naive_verdict(self_judge_llm, p["question"], p["first"], p["second"]), "tie") == "second":
            self_pref_second += 1

    fixed_judge = Judge(judge_llm)
    fixed = [fixed_judge.pairwise(p["question"], p["first"], p["second"]).final for p in pairs]

    hv = [human[p["id"]] for p in pairs]
    out = {
        "n": len(pairs), "judge_model": judge_llm.name, "self_judge_model": self_judge_llm.name,
        "naive_agreement": sum(a == b for a, b in zip(naive, hv)), "naive_kappa": cohens_kappa(list(zip(hv, naive))),
        "position_flips": flips, "length_bias_moves_of_10": length_moves,
        "self_judge_picks_own": self_pref_second, "human_picks_second": sum(h == "second" for h in hv),
        "fixed_agreement": sum(a == b for a, b in zip(fixed, hv)), "fixed_kappa": cohens_kappa(list(zip(hv, fixed))),
        "flip_examples": examples,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "judge_audit.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"\nJudge agreed with me on {out['naive_agreement']}/{out['n']}; swapping answer order changed {flips} verdicts; "
          f"judging in both orders raised agreement to {out['fixed_agreement']}/{out['n']}.")


if __name__ == "__main__":
    {"answers": answers, "judge": judge}[sys.argv[1] if len(sys.argv) > 1 else "judge"]()
