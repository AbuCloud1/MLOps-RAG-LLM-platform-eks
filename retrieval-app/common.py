"""
shared bits used by both ingest.py and app.py.
model name, collection name and chunking logic live here so ingest
and query always agree.
"""
import os
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# reached through kubectl port-forward locally (looks like localhost),
# becomes qdrant.rag once the app runs in-cluster
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# the Qdrant "collection" is like a table - holds the note embeddings
COLLECTION = "abubker_notes"

# small, fast embedding model, CPU only, 384-dim vectors
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384

# load once, reuse across calls
_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def get_client():
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def embed(texts):
    """turn a list of strings into a list of embedding vectors."""
    return get_model().encode(texts, normalize_embeddings=True).tolist()


def chunk_text(text, max_chars=500):
    """
    split a document into smaller chunks by paragraph.
    RAG works better on small chunks than whole documents - retrieve
    just the relevant paragraph, not a whole page.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) < max_chars:
            current = (current + "\n\n" + p).strip()
        else:
            if current:
                chunks.append(current)
            current = p
    if current:
        chunks.append(current)
    return chunks
