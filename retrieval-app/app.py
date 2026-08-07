"""
retrieval app - ties the RAG flow together.

endpoints:
  /search  - embed the question, ask Qdrant for the closest note chunks.
             no LLM needed, good for testing retrieval on its own.
  /ask     - full RAG: retrieve context, then send it to the LLM (vLLM)
             to generate an answer. needs vLLM deployed.
  /health  - liveness check.

run locally: uvicorn app:app --reload --port 8000
"""
import os
import requests
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from common import get_client, embed, COLLECTION

# vLLM endpoint, empty until vLLM is deployed - /ask stays disabled until then
VLLM_URL = os.getenv("VLLM_URL", "")
VLLM_MODEL = os.getenv("VLLM_MODEL", "")

# how many note chunks to retrieve for context
TOP_K = int(os.getenv("TOP_K", "5"))

app = FastAPI(title="Abubaker RAG assistant")


class Query(BaseModel):
    question: str


def retrieve(question, top_k=TOP_K):
    """embed the question, return the closest note chunks from Qdrant."""
    vector = embed([question])[0]
    hits = get_client().search(
        collection_name=COLLECTION,
        query_vector=vector,
        limit=top_k,
    )
    return [
        {
            "text": h.payload["text"],
            "source": h.payload["source"],
            "score": round(h.score, 3),
        }
        for h in hits
    ]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/search")
def search(q: Query):
    """retrieval only, no LLM - see what context RAG would pull."""
    return {"question": q.question, "results": retrieve(q.question)}


@app.post("/ask")
def ask(q: Query):
    """full RAG: retrieve context, then ask the LLM to answer using it."""
    if not VLLM_URL:
        return {
            "error": "LLM not configured yet. Set VLLM_URL once vLLM is deployed.",
            "hint": "Use /search to test retrieval in the meantime.",
        }

    results = retrieve(q.question)
    context = "\n\n".join(r["text"] for r in results)

    prompt = (
        "You are answering a visitor's question about a person named Abubaker, "
        "on his behalf. The notes below are written in Abubaker's own words "
        "(first person, 'I'), but you must answer about him in the third "
        "person instead, e.g. 'He follows...' or 'Abubaker drives...'. Never "
        "say 'I'.\n\n"
        "Only use facts stated in the notes. Do not add any names, brands, "
        "numbers, or details that are not explicitly written in the notes, "
        "even if they seem plausible. If the notes do not contain the "
        "answer, say so rather than guessing.\n\n"
        "Keep the answer to 1-3 sentences.\n\n"
        f"Notes:\n{context}\n\n"
        f"Question: {q.question}\n"
        "Answer:"
    )

    # vLLM exposes an OpenAI-compatible API
    resp = requests.post(
        f"{VLLM_URL}/v1/completions",
        json={
            "model": VLLM_MODEL,
            "prompt": prompt,
            "max_tokens": 120,
            "min_tokens": 16,
            "temperature": 0.2,
            "stop": ["\n\n", "Question:", "Notes:"],
        },
        timeout=60,
    )
    resp.raise_for_status()
    answer = resp.json()["choices"][0]["text"].strip()

    return {"question": q.question, "answer": answer, "sources": [r["source"] for r in results]}


# chat UI, served alongside the API so /ask needs no CORS setup
app.mount("/ui", StaticFiles(directory="static", html=True), name="ui")
