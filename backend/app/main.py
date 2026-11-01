"""FastAPI app exposing The Pundit's four modes."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import BACKEND_DIR, get_settings
from .pipeline import BudgetExhausted, Pundit, UpstreamError, build_services
from .ratelimit import RateLimiter, hash_ip

DEBATE_QUESTIONS = BACKEND_DIR / "data" / "debate_questions.json"
EVAL_RESULTS = BACKEND_DIR / "eval" / "results"


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=300)


class DebateIn(BaseModel):
    question: str = Field(min_length=2, max_length=300)


class VoteIn(BaseModel):
    vote: str


class ChallengeIn(BaseModel):
    post: str = Field(min_length=1, max_length=1500)
    question: str = Field(min_length=2, max_length=300)
    goal: str
    guardrails_on: bool = True
    nickname: str | None = Field(default=None, max_length=24)


state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    state["pundit"] = Pundit(build_services(settings))
    state["limiter"] = RateLimiter()
    yield
    state.clear()


app = FastAPI(title="The Pundit", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
)


def _client_key(request: Request) -> str:
    # Behind a proxy (HF Spaces, Vercel) the real client is the first X-Forwarded-For entry.
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")
    return hash_ip(ip)


def _limit(request: Request, mode: str, limit: int) -> str:
    key = _client_key(request)
    ok, retry = state["limiter"].allow(key, mode, limit)
    if not ok:
        raise HTTPException(429, detail=f"Too many {mode} requests. Try again in {retry // 60 + 1} min.", headers={"Retry-After": str(retry)})
    return key


def _pundit() -> Pundit:
    return state["pundit"]


@app.get("/api/health")
def health():
    p = _pundit()
    return {"ok": True, "docs": len(p.s.corpus.docs), "cache_entries": len(p.s.cache), "data_version": p.s.corpus.data_version}


@app.post("/api/ask")
def ask(body: AskIn, request: Request):
    key = _limit(request, "ask", settings.ask_per_hour)
    try:
        return _pundit().ask(body.question, ip_hash=key)
    except UpstreamError:
        raise HTTPException(503, "The model provider is busy. Try again in a minute.")


@app.get("/api/debate/questions")
def debate_questions():
    if DEBATE_QUESTIONS.exists():
        return json.loads(DEBATE_QUESTIONS.read_text(encoding="utf-8"))
    return []


@app.post("/api/debate")
def debate(body: DebateIn, request: Request):
    key = _limit(request, "debate", settings.debate_per_hour)
    try:
        return _pundit().debate(body.question, ip_hash=key)
    except BudgetExhausted:
        raise HTTPException(503, "Today's free model budget is used up. Debates are back after midnight UTC.")
    except UpstreamError:
        raise HTTPException(503, "The model provider is busy. Try again in a minute.")


@app.post("/api/debate/{debate_id}/vote")
def vote(debate_id: int, body: VoteIn):
    try:
        return _pundit().vote(debate_id, body.vote)
    except KeyError:
        raise HTTPException(404, "No such debate")
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/api/challenge")
def challenge(body: ChallengeIn, request: Request):
    key = _limit(request, "challenge", settings.challenge_per_hour)
    try:
        return _pundit().challenge(body.post, body.question, body.goal, body.guardrails_on, body.nickname, ip_hash=key)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except BudgetExhausted:
        raise HTTPException(503, "Today's free model budget is used up. The challenge reopens after midnight UTC.")
    except UpstreamError:
        raise HTTPException(503, "The model provider is busy. Try again in a minute.")


@app.get("/api/challenge/leaderboard")
def leaderboard():
    return _pundit().leaderboard()


@app.get("/api/numbers")
def numbers():
    live = _pundit().numbers()
    offline = {}
    if EVAL_RESULTS.exists():
        for f in sorted(Path(EVAL_RESULTS).glob("*.json")):
            offline[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return {"live": live, "offline": offline}
