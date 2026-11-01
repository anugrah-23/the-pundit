"""The RAG corpus: documents, their embeddings, and retrieval."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .embeddings import Embedder
from .entities import Entities, Gazetteer

ENTITY_BOOST = 0.15


@dataclass
class Doc:
    doc_id: str
    kind: str
    text: str
    league: str = ""
    season: str = ""
    entities: dict = field(default_factory=dict)  # {"players": [...], "teams": [...]}
    volatile: bool = True
    source: str = ""

    def to_public(self) -> dict:
        return {"doc_id": self.doc_id, "kind": self.kind, "text": self.text, "source": self.source}


class Corpus:
    """Loads a built corpus directory:

    docs.jsonl        one Doc per line
    embeddings.npy    float32 matrix, row i is docs[i] (written by etl/build_index.py)
    gazetteer.json    players and teams with aliases
    meta.json         {"data_version": "...", "embedding_model": "..."}
    """

    def __init__(self, docs: list[Doc], matrix: np.ndarray, gazetteer: Gazetteer, data_version: str):
        assert matrix.shape[0] == len(docs), "embeddings and docs are out of sync"
        self.docs = docs
        self.matrix = matrix
        self.gazetteer = gazetteer
        self.data_version = data_version

    @classmethod
    def load(cls, directory: Path, embedder: Embedder) -> "Corpus":
        docs = [Doc(**json.loads(line)) for line in (directory / "docs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
        emb_path = directory / "embeddings.npy"
        matrix = None
        if emb_path.exists():
            matrix = np.load(emb_path)
            if matrix.shape != (len(docs), embedder.dim):
                matrix = None  # built with a different embedder; rebuild in memory
        if matrix is None:
            matrix = embedder.encode([d.text for d in docs]) if docs else np.zeros((0, embedder.dim), np.float32)
        return cls(docs, matrix, Gazetteer.load(directory / "gazetteer.json"), meta["data_version"])

    def retrieve(self, vec: np.ndarray, entities: Entities, k: int = 4) -> list[tuple[Doc, float]]:
        if not self.docs:
            return []
        scores = self.matrix @ vec
        wanted_players = {p for name in entities.players for p in name.split("|")}
        wanted_teams = set(entities.teams)
        if wanted_players or wanted_teams:
            boost = np.array(
                [
                    ENTITY_BOOST
                    if wanted_players & set(d.entities.get("players", [])) or wanted_teams & set(d.entities.get("teams", []))
                    else 0.0
                    for d in self.docs
                ],
                dtype=np.float32,
            )
            scores = scores + boost
        top = np.argsort(-scores)[:k]
        return [(self.docs[i], float(scores[i])) for i in top]
