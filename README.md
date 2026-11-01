# The Pundit

An AI football analyst for the Premier League, La Liga, Serie A, Bundesliga and Ligue 1 (2026-27). It answers questions from real stats in English, Hinglish or Tanglish, and is publicly tested on three things:

- **Is it cheap?** A semantic cache answers repeat questions without calling the model, with an entity guard so "Haaland goals this season" never returns the answer for Mbappé.
- **Is it honest?** An LLM judge checks every fresh answer against the stats it was built from, and only verified answers are allowed into the cache. The judge itself is audited for position, length and self-preference bias.
- **Is it hard to manipulate?** Retrieved text is spotlighted as data, scanned for injection patterns, and every reply passes an output check for leaked secrets, spam links and invented transfers. Visitors can try to break it.

> Results: _to be filled in from `backend/eval/results/` once the evaluations run on real data._
> "Cache hit rate X% on 100 test questions at threshold T with Y false hits; the entity guard prevented Z false hits."
> "Judge agreed with me on X/30; swapping answer order changed Y verdicts; judging in both orders raised agreement to Z/30."
> "Successful injections: X/10 before, Y/10 after guardrails; Z false blocks on 20 normal questions."

## The four modes

| Mode | What you do | What it measures |
|---|---|---|
| Ask | Ask a stats or tactics question | Cache hit rate, latency, judge pass rate |
| Debate | Two models answer, you vote before the reveal | Human agreement with the judge (and Cohen's kappa) |
| Break the Pundit | Write a poisoned fan-blog post to make it announce a fake transfer, leak a fake key or post a spam link | Attack success with guardrails on and off |
| Numbers | Read the live and offline results | Everything above |

## How a question flows

```
question -> embed -> semantic cache (threshold + negation guard + entity guard + data-version expiry)
   hit  -> cached answer in milliseconds
   miss -> retrieve top 4 stats docs -> input scan -> spotlight in <document> tags -> answer model
        -> output check (secret, links, unverified transfers) -> judge (faithfulness)
        -> cache only if every check passed
```

Full design: [docs/SPEC.md](docs/SPEC.md).

## Running locally

Backend (Python 3.11+):

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env            # add your Gemini and Groq keys, or set the providers to "mock"
python -m etl.make_demo         # fictional demo corpus, so the app runs before the first real data refresh
uvicorn app.main:app --reload   # http://localhost:8000
python -m pytest -q
```

Real data (needs network access to Understat):

```bash
pip install -r requirements-etl.txt
python -m etl.fetch_understat --season 2026 --out data/raw
python -m etl.build_corpus --raw data/raw --out data/corpus
```

In production this runs weekly in GitHub Actions (`.github/workflows/etl.yml`) and commits the refreshed corpus.

Frontend:

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev   # http://localhost:3000
```

## Evaluations

| Script | Spec | Needs |
|---|---|---|
| `python -m eval.cache_sweep` | 8.1 | `eval/data/cache_seeds.jsonl`, `eval/data/cache_testset.jsonl` (hand-checked labels) |
| `python -m eval.judge_audit answers` then `judge` | 8.2 | `eval/data/judge_questions.jsonl`, your own grades in `eval/data/human_grades.jsonl` |
| `python -m eval.injection_suite` | 8.3 | `eval/data/attacks.jsonl`, `eval/data/normal_questions.jsonl`, a real answer model |

Results are written to `backend/eval/results/*.json` and shown on the Numbers page.

## Stack

FastAPI, sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`), numpy, SQLAlchemy, rapidfuzz; Gemini Flash (answers), gpt-oss-120b on Groq (judge), Llama on Groq (debate opponent); Next.js on Vercel; backend on Hugging Face Spaces; Postgres for logs, cache, votes and leaderboard.

## Data

Stats from [Understat](https://understat.com) via [soccerdata](https://github.com/probberechts/soccerdata). FBref removed its Opta advanced stats in January 2026, so it is only used as a backup for basic tables. The admin key and fan-blog posts in Break the Pundit are fake and exist only for testing.
