import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.config import Settings  # noqa: E402
from app.embeddings import HashingEmbedder  # noqa: E402
from app.pipeline import Pundit, build_services  # noqa: E402
from etl.make_demo import make_demo  # noqa: E402


@pytest.fixture(scope="session")
def demo_corpus(tmp_path_factory):
    out = tmp_path_factory.mktemp("corpus")
    make_demo(out, "hashing", data_version="demo-test-1")
    return out


@pytest.fixture
def settings(demo_corpus, tmp_path):
    return Settings(
        corpus_dir=demo_corpus, database_url=f"sqlite:///{tmp_path / 'test.db'}", embedder="hashing",
        answer_provider="mock", judge_provider="mock", opponent_provider="mock", cache_threshold=0.9,
    )


@pytest.fixture
def pundit(settings):
    return Pundit(build_services(settings, embedder=HashingEmbedder()))


@pytest.fixture
def gazetteer(pundit):
    return pundit.s.corpus.gazetteer
