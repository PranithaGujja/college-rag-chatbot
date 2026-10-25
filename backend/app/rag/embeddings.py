"""Embedding model wrapper (fastembed = ONNX runtime, no PyTorch, small RAM footprint).

    python -m app.rag.embeddings --warmup     # download the model once (used in the Render build)
"""
import os
import sys
import threading

from app.config import BASE_DIR, settings

_model = None
_lock = threading.Lock()
# BGE models are trained to see this instruction in front of *queries* (not passages).
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def _get_model():
    global _model
    with _lock:
        if _model is None:
            from fastembed import TextEmbedding

            cache = os.getenv("FASTEMBED_CACHE_PATH", str(BASE_DIR / ".fastembed_cache"))
            _model = TextEmbedding(model_name=settings.embed_model, cache_dir=cache, threads=1)
        return _model


def embed_passages(texts):
    return [v.tolist() for v in _get_model().embed(texts, batch_size=16)]


def embed_query(text: str):
    if "bge" in settings.embed_model.lower():
        text = _BGE_QUERY_PREFIX + text
    return next(iter(_get_model().embed([text]))).tolist()


if __name__ == "__main__":
    if "--warmup" in sys.argv:
        v = embed_query("warm up")
        print(f"Embedding model ready: {settings.embed_model} (dim={len(v)})")
