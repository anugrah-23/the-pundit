"""Semantic cache with negation guard, entity guard and data-version expiry."""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy.orm import sessionmaker

from .db import CacheEntry
from .entities import Entities

# English, Hindi/Hinglish and Tamil/Tanglish negation words.
NEGATION_WORDS = {
    "not", "never", "without", "none", "nobody", "neither", "nor", "cannot",
    "nahi", "nahin", "nhi", "nai", "mat", "bina",
    "illa", "illai", "illaya", "illaiya", "illaye", "kidaiyathu", "kidaiyadhu", "kedayathu",
    "venaam", "vendam", "vendaam", "maatan", "maataan", "maaten", "maatten", "mudiyathu", "mudiyadhu",
}
# Tamil verbs negate with suffixes: "adikala" (didn't score), "pannala" (didn't do),
# "adikkaadha" (one who doesn't score). Heuristic, with known false positives excluded.
TAMIL_NEG_SUFFIXES = ("kala", "nala", "vala", "rala", "dala", "tala", "aadha", "aatha", "kaadhu")
SUFFIX_EXCEPTIONS = {"guatemala", "kerala", "ayala", "chandala", "koala", "gala", "scala", "impala"}


def has_negation(text: str) -> bool:
    lowered = text.lower()
    if re.search(r"\b\w+n't\b", lowered):
        return True
    tokens = re.findall(r"[a-z]+", lowered.replace("n't", " not"))
    for i, tok in enumerate(tokens):
        if tok == "no":
            # "no of goals" / "no. of goals" means "number of", not a negation.
            nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
            if nxt != "of" and not re.search(r"\bno\s*\.", lowered):
                return True
            continue
        if tok in NEGATION_WORDS:
            return True
        if len(tok) >= 6 and tok not in SUFFIX_EXCEPTIONS and tok.endswith(TAMIL_NEG_SUFFIXES):
            return True
    return False


def normalize_question(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


@dataclass
class CachedItem:
    id: int
    question: str
    answer: str
    sources: list
    entities: Entities
    negated: bool
    volatile: bool
    data_version: str
    created_at: datetime


@dataclass
class CacheResult:
    hit: bool
    item: CachedItem | None = None
    similarity: float | None = None  # similarity of the nearest candidate considered
    skip_reason: str | None = None  # why the nearest above-threshold candidate was rejected


class SemanticCache:
    def __init__(
        self,
        session_factory: sessionmaker,
        dim: int,
        threshold: float,
        data_version: str,
        max_age_days: int = 14,
        negation_guard: bool = True,
        entity_guard: bool = True,
    ):
        self.sf = session_factory
        self.dim = dim
        self.threshold = threshold
        self.data_version = data_version
        self.max_age = timedelta(days=max_age_days)
        self.negation_guard = negation_guard
        self.entity_guard = entity_guard
        self._lock = threading.Lock()
        self._items: list[CachedItem] = []
        self._matrix = np.zeros((0, dim), dtype=np.float32)
        self._load()

    def _load(self) -> None:
        with self.sf() as s:
            rows = s.query(CacheEntry).order_by(CacheEntry.id).all()
        vecs = []
        for r in rows:
            vec = np.frombuffer(r.embedding, dtype=np.float32)
            if vec.shape[0] != self.dim:
                continue  # embedder changed; stale entry
            vecs.append(vec)
            self._items.append(self._to_item(r))
        if vecs:
            self._matrix = np.vstack(vecs)

    @staticmethod
    def _to_item(r: CacheEntry) -> CachedItem:
        created = r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=timezone.utc)
        return CachedItem(
            id=r.id, question=r.question, answer=r.answer, sources=r.sources or [],
            entities=Entities.from_dict(r.entities or {}), negated=has_negation(r.question),
            volatile=r.volatile, data_version=r.data_version, created_at=created,
        )

    def __len__(self) -> int:
        return len(self._items)

    def _expired(self, item: CachedItem, now: datetime) -> bool:
        if now - item.created_at > self.max_age:
            return True
        return item.volatile and item.data_version != self.data_version

    def lookup(self, question: str, vec: np.ndarray, entities: Entities, max_candidates: int = 5) -> CacheResult:
        with self._lock:
            if not self._items:
                return CacheResult(hit=False)
            sims = self._matrix @ vec
            order = np.argsort(-sims)[:max_candidates]
            nearest = float(sims[order[0]])
            negated = has_negation(question)
            now = datetime.now(timezone.utc)
            first_reason: str | None = None
            for idx in order:
                sim = float(sims[idx])
                if sim < self.threshold:
                    break
                item = self._items[idx]
                reason = None
                if self._expired(item, now):
                    reason = "expired"
                elif self.negation_guard and negated != item.negated:
                    reason = "negation"
                elif self.entity_guard and (diff := entities.differs_from(item.entities)):
                    reason = f"entity:{diff}"
                if reason is None:
                    self._bump(item.id)
                    return CacheResult(hit=True, item=item, similarity=sim)
                first_reason = first_reason or reason
            return CacheResult(hit=False, similarity=nearest, skip_reason=first_reason)

    def _bump(self, entry_id: int) -> None:
        with self.sf() as s:
            row = s.get(CacheEntry, entry_id)
            if row:
                row.hit_count += 1
                s.commit()

    def add(
        self, question: str, vec: np.ndarray, answer: str, sources: list, entities: Entities, volatile: bool
    ) -> CachedItem:
        with self.sf() as s:
            row = CacheEntry(
                question=question, normalized=normalize_question(question),
                embedding=vec.astype(np.float32).tobytes(), answer=answer, sources=sources,
                entities=entities.as_dict(), volatile=volatile, data_version=self.data_version,
            )
            s.add(row)
            s.commit()
            item = self._to_item(row)
        with self._lock:
            self._items.append(item)
            self._matrix = np.vstack([self._matrix, vec.reshape(1, -1).astype(np.float32)])
        return item

    def set_data_version(self, version: str) -> None:
        self.data_version = version
