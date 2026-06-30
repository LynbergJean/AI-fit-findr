"""
embeddings.py

Manages the Pinecone vector index for semantic search over listings.
Embeds listing text using sentence-transformers and upserts to Pinecone.
"""

import os
import json

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec

from utils.data_loader import load_listings

load_dotenv()

MODEL_NAME = "all-MiniLM-L6-v2"
INDEX_NAME = "fitfindr-listings"
DIMENSION = 384  # MiniLM-L6-v2 output dimension

_model = None
_index = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _get_index():
    global _index
    if _index is not None:
        return _index

    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        raise ValueError("PINECONE_API_KEY not set. Add it to .env.")

    pc = Pinecone(api_key=api_key)

    if INDEX_NAME not in [idx.name for idx in pc.list_indexes()]:
        pc.create_index(
            name=INDEX_NAME,
            dimension=DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )

    _index = pc.Index(INDEX_NAME)
    return _index


def _listing_to_text(listing: dict) -> str:
    """Convert a listing dict to a searchable text string."""
    return (
        f"{listing['title']}. {listing['description']}. "
        f"Category: {listing['category']}. "
        f"Style: {', '.join(listing['style_tags'])}. "
        f"Colors: {', '.join(listing['colors'])}."
    )


def build_index():
    """Embed all listings and upsert to Pinecone. Idempotent."""
    model = _get_model()
    index = _get_index()
    listings = load_listings()

    texts = [_listing_to_text(l) for l in listings]
    embeddings = model.encode(texts).tolist()

    vectors = []
    for listing, embedding in zip(listings, embeddings):
        vectors.append({
            "id": listing["id"],
            "values": embedding,
            "metadata": {
                "title": listing["title"],
                "price": listing["price"],
                "size": listing["size"],
                "category": listing["category"],
                "json": json.dumps(listing),
            },
        })

    # Upsert in batch
    index.upsert(vectors=vectors)
    return len(vectors)


def semantic_search(
    query: str,
    size: str | None = None,
    max_price: float | None = None,
    top_k: int = 5,
) -> list[dict]:
    """
    Search listings by semantic similarity, with optional filters.

    Returns a list of listing dicts sorted by relevance.
    """
    model = _get_model()
    index = _get_index()

    query_embedding = model.encode(query).tolist()

    # Build metadata filter
    filter_dict = {}
    if max_price is not None:
        filter_dict["price"] = {"$lte": max_price}
    if size is not None:
        filter_dict["size"] = {"$eq": size}

    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True,
        filter=filter_dict if filter_dict else None,
    )

    listings = []
    for match in results.matches:
        listing = json.loads(match.metadata["json"])
        listing["_score"] = match.score
        listings.append(listing)

    return listings


if __name__ == "__main__":
    count = build_index()
    print(f"Indexed {count} listings to Pinecone.")

    # Test query
    results = semantic_search("cozy fall layer")
    print(f"\nQuery: 'cozy fall layer'")
    for r in results[:3]:
        print(f"  {r['title']} (${r['price']}) — score: {r['_score']:.3f}")
