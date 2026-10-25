"""Per-role knowledge base. Each role has its own chunks, its own BM25 and its own FAISS index."""
import json
import logging
import math
import threading
from dataclasses import dataclass, field

from app.config import settings
from app.rag.bm25 import BM25, tokenize
from app.rag.ingest import HANDBOOKS, retrieval_text

log = logging.getLogger("rag")
RRF_K = 60
CANDIDATES = 15


class KnowledgeBaseMissing(RuntimeError):
    pass


@dataclass
class Hit:
    chunk: dict
    dense: float | None = None
    bm25: float = 0.0
    fused: float = 0.0


@dataclass
class Retrieval:
    hits: list = field(default_factory=list)
    best_dense: float | None = None
    best_bm25: float = 0.0
    coverage: float = 0.0
    relevant: bool = False


class KnowledgeBase:
    def __init__(self, role: str):
        if role not in HANDBOOKS:
            raise ValueError(f"unknown role {role!r}")
        self.role = role
        self.label = HANDBOOKS[role]["label"]
        d = settings.index_dir / role
        path = d / "chunks.json"
        if not path.exists():
            raise KnowledgeBaseMissing(f"No index for '{role}'. Run: python -m app.rag.ingest")
        self.chunks = json.loads(path.read_text(encoding="utf-8"))
        # Hard isolation check: every chunk in this KB must belong to this role.
        bad = [c["id"] for c in self.chunks if c.get("role") != role]
        if bad:
            raise RuntimeError(f"Index for '{role}' contains foreign chunks: {bad[:3]}")
        self.bm25 = BM25([retrieval_text(c) for c in self.chunks])
        self.index_of = {c["id"]: i for i, c in enumerate(self.chunks)}

        self.faiss = None
        meta_path = d / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        if settings.retrieval_mode == "hybrid":
            fpath = d / "vectors.faiss"
            if fpath.exists() and meta.get("embed_model") == settings.embed_model:
                import faiss

                self.faiss = faiss.read_index(str(fpath))
                if self.faiss.ntotal != len(self.chunks):
                    raise RuntimeError(f"Index/chunk count mismatch for '{role}'. Re-run ingest.")
            else:
                log.warning("[%s] no usable vector index (found model=%s, want %s); using BM25 only. Run ingest.",
                            role, meta.get("embed_model"), settings.embed_model)

    @property
    def mode(self) -> str:
        return "hybrid" if self.faiss is not None else "bm25"

    def coverage(self, query: str, hits) -> float:
        """Share (IDF-weighted) of the question's informative words found in the top retrieved chunks.
        Words that never occur in the handbook count as maximally informative, so questions about
        things the handbook does not mention score low."""
        terms = set(tokenize(query))
        if not terms or not hits:
            return 0.0
        max_idf = math.log(1 + (self.bm25.n + 0.5) / 0.5)
        seen = set()
        for h in hits[:3]:
            seen |= set(self.bm25.doc_tf[self.index_of[h.chunk["id"]]])
        total = got = 0.0
        for t in terms:
            idf = self.bm25.idf(t) if t in self.bm25.postings else max_idf
            total += idf
            if t in seen:
                got += idf
        return got / total if total else 0.0

    def search(self, query: str, k: int | None = None) -> Retrieval:
        k = k or settings.top_k
        hits: dict[int, Hit] = {}

        bm = self.bm25.scores(query)
        bm_ranked = sorted(bm.items(), key=lambda x: -x[1])[:CANDIDATES]
        for rank, (i, s) in enumerate(bm_ranked):
            h = hits.setdefault(i, Hit(self.chunks[i]))
            h.bm25 = s
            h.fused += 1 / (RRF_K + rank + 1)
        best_bm25 = bm_ranked[0][1] if bm_ranked else 0.0

        best_dense = None
        if self.faiss is not None:
            import faiss
            import numpy as np

            from app.rag.embeddings import embed_query

            q = np.asarray([embed_query(query)], dtype="float32")
            faiss.normalize_L2(q)
            scores, ids = self.faiss.search(q, CANDIDATES)
            for rank, (i, s) in enumerate(zip(ids[0], scores[0])):
                if i < 0:
                    continue
                h = hits.setdefault(int(i), Hit(self.chunks[int(i)]))
                h.dense = float(s)
                h.fused += 1 / (RRF_K + rank + 1)
            best_dense = float(scores[0][0]) if len(scores[0]) else None

        top = sorted(hits.values(), key=lambda h: -h.fused)[:k]
        cov = self.coverage(query, top)
        relevant = cov >= settings.min_coverage or (best_dense is not None and best_dense >= settings.dense_min_score)
        return Retrieval(hits=top, best_dense=best_dense, best_bm25=best_bm25, coverage=cov, relevant=relevant)


_cache: dict[str, KnowledgeBase] = {}
_cache_lock = threading.Lock()


def get_kb(role: str) -> KnowledgeBase:
    """The ONLY way the application obtains a knowledge base. Roles map 1:1 to handbooks."""
    with _cache_lock:
        if role not in _cache:
            _cache[role] = KnowledgeBase(role)
        return _cache[role]
