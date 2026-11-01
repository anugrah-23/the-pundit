"""Cache threshold sweep on the labelled test set (spec section 8.1).

Inputs (eval/data/):
  cache_seeds.jsonl     {"seed_id": "s01", "question": "..."}                       30 lines
  cache_testset.jsonl   {"question": "...", "label": "s01" | "none",
                         "kind": "paraphrase" | "entity_swap" | "negation" | "new",
                         "lang": "en" | "hinglish" | "tanglish"}                    100 lines

The seeds are put in a fresh cache, then every test question is looked up at each threshold,
with the guards off and on.
  hit        the test question matched its own seed (correct reuse)
  false hit  a saved answer was returned for a different question
  miss       nothing returned (the LLM would be called)

  python -m eval.cache_sweep            # real embedding model
Results go to eval/results/cache_sweep.json and are printed as a markdown table.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.cache import SemanticCache, normalize_question  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import make_session_factory  # noqa: E402
from app.embeddings import make_embedder  # noqa: E402
from app.entities import Gazetteer  # noqa: E402

DATA = ROOT / "eval" / "data"
RESULTS = ROOT / "eval" / "results"
THRESHOLDS = [0.75, 0.80, 0.85, 0.88, 0.90, 0.92, 0.95]


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(threshold: float, guards: bool, seeds, seed_vecs, tests, test_vecs, gaz: Gazetteer) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        sf = make_session_factory(f"sqlite:///{tmp}/sweep.db")
        cache = SemanticCache(sf, seed_vecs.shape[1], threshold, "eval", negation_guard=guards, entity_guard=guards)
        for s, v in zip(seeds, seed_vecs):
            cache.add(s["question"], v, f"ANSWER:{s['seed_id']}", [], gaz.extract(s["question"]), volatile=False)
        hits = false_hits = 0
        caught: list[dict] = []
        lookup_ms = []
        for t, v in zip(tests, test_vecs):
            t0 = time.perf_counter()
            res = cache.lookup(t["question"], v, gaz.extract(t["question"]))
            lookup_ms.append((time.perf_counter() - t0) * 1000)
            if res.hit:
                got = res.item.answer.removeprefix("ANSWER:")
                if got == t["label"]:
                    hits += 1
                else:
                    false_hits += 1
            elif res.skip_reason and len(caught) < 5:
                caught.append({"question": t["question"], "reason": res.skip_reason, "label": t["label"]})
    should_hit = sum(1 for t in tests if t["label"] != "none")
    return {
        "threshold": threshold, "guards": guards, "hits": hits, "false_hits": false_hits,
        "hit_rate": round(hits / should_hit, 3) if should_hit else None,
        "llm_calls_avoided_pct": round(100 * (hits + false_hits) / len(tests), 1),
        "avg_lookup_ms": round(float(np.mean(lookup_ms)), 2), "examples_caught": caught,
    }


def main() -> None:
    cfg = get_settings()
    seeds = load_jsonl(DATA / "cache_seeds.jsonl")
    tests = load_jsonl(DATA / "cache_testset.jsonl")
    corpus_dir = cfg.corpus_dir if (cfg.corpus_dir / "gazetteer.json").exists() else cfg.corpus_dir.parent / "demo_corpus"
    gaz = Gazetteer.load(corpus_dir / "gazetteer.json")
    embedder = make_embedder(cfg.embedder, cfg.embedding_model)
    seed_vecs = embedder.encode([normalize_question(s["question"]) for s in seeds])
    test_vecs = embedder.encode([normalize_question(t["question"]) for t in tests])

    rows = [run(th, g, seeds, seed_vecs, tests, test_vecs, gaz) for g in (False, True) for th in THRESHOLDS]
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = {"embedder": cfg.embedding_model if cfg.embedder != "hashing" else "hashing (NOT for publishing)",
           "n_tests": len(tests), "n_should_hit": sum(1 for t in tests if t["label"] != "none"), "rows": rows}
    (RESULTS / "cache_sweep.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    print("| guards | threshold | hit rate | hits | false hits | LLM calls avoided |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {'on' if r['guards'] else 'off'} | {r['threshold']:.2f} | {r['hit_rate']} | {r['hits']} | {r['false_hits']} | {r['llm_calls_avoided_pct']}% |")


if __name__ == "__main__":
    main()
