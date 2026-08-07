"""
ingest: read the note docs, chunk them, embed them, load into Qdrant.
run once, or again any time the docs change.

usage: python ingest.py
"""
import os
import glob
from qdrant_client.models import Distance, VectorParams, PointStruct

from common import get_client, embed, chunk_text, COLLECTION, EMBED_DIM

DOCS_DIR = os.path.join(os.path.dirname(__file__), "docs")


def main():
    client = get_client()

    # recreate wipes any old data so re-running ingest is always clean
    client.recreate_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
    )
    print(f"Collection '{COLLECTION}' ready.")

    points = []
    point_id = 0

    for path in sorted(glob.glob(os.path.join(DOCS_DIR, "*.txt"))):
        source = os.path.basename(path)
        with open(path) as f:
            text = f.read()

        chunks = chunk_text(text)
        vectors = embed(chunks)

        for chunk, vector in zip(chunks, vectors):
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    # payload = the metadata we get back on retrieval
                    payload={"text": chunk, "source": source},
                )
            )
            point_id += 1

        print(f"  {source}: {len(chunks)} chunks")

    client.upsert(collection_name=COLLECTION, points=points)
    print(f"\nLoaded {len(points)} chunks from {len(glob.glob(os.path.join(DOCS_DIR, '*.txt')))} docs into Qdrant.")


if __name__ == "__main__":
    main()
