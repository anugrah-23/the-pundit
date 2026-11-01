"""Text embedders. All return L2-normalised float32 vectors, so a dot product is cosine similarity."""
from __future__ import annotations

import hashlib
import re

import numpy as np


class Embedder:
    dim: int

    def encode(self, texts: list[str]) -> np.ndarray:  # (n, dim)
        raise NotImplementedError


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (m / norms).astype(np.float32)


class SentenceTransformerEmbedder(Embedder):
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name, device="cpu")
        self.dim = self.model.get_sentence_embedding_dimension()

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = self.model.encode(texts, batch_size=64, convert_to_numpy=True, show_progress_bar=False)
        return _normalize(np.asarray(vecs, dtype=np.float32))


class HashingEmbedder(Embedder):
    """Bag of word and character-trigram hashes. Deterministic and dependency-free.

    Only for tests and offline development: it has no real notion of meaning, so it must
    never be used to produce published cache numbers.
    """

    def __init__(self, dim: int = 512):
        self.dim = dim

    def _features(self, text: str) -> list[str]:
        words = re.findall(r"[\w']+", text.lower())
        feats = list(words)
        for w in words:
            padded = f"#{w}#"
            feats.extend(padded[i : i + 3] for i in range(len(padded) - 2))
        return feats

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for f in self._features(text):
                h = int(hashlib.md5(f.encode()).hexdigest(), 16)
                out[row, h % self.dim] += 1.0 if (h >> 64) & 1 else -1.0
        return _normalize(out)


def make_embedder(kind: str, model_name: str) -> Embedder:
    if kind == "hashing":
        return HashingEmbedder()
    return SentenceTransformerEmbedder(model_name)
