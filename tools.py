"""
tools.py

FitFindr tools — semantic search via Pinecone, outfit suggestion, fit card.
Uses Google Gemini for LLM calls.

Tools:
    search_listings(query, size, max_price, top_k)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
import google.generativeai as genai

from embeddings import semantic_search

load_dotenv()


def _get_model(temperature=0.7):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set. Add it to .env.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        "gemini-2.0-flash",
        generation_config=genai.GenerationConfig(temperature=temperature, max_output_tokens=300),
    )


# ── Tool 1: search_listings (semantic) ────────────────────────────────────────

def search_listings(
    query: str,
    size: str | None = None,
    max_price: float | None = None,
    top_k: int = 5,
) -> list[dict]:
    """
    Semantic search over listings using Pinecone + sentence-transformers.
    """
    return semantic_search(query=query, size=size, max_price=max_price, top_k=top_k)


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Suggest 1-2 outfits pairing the item with the user's wardrobe.
    """
    model = _get_model(temperature=0.7)

    item_desc = (
        f"{new_item['title']} — {new_item['description']} "
        f"(Category: {new_item['category']}, Colors: {', '.join(new_item['colors'])}, "
        f"Style: {', '.join(new_item['style_tags'])})"
    )

    if not wardrobe.get("items"):
        prompt = (
            f"I'm considering buying this secondhand item:\n{item_desc}\n\n"
            "I don't have a wardrobe on file yet. Suggest 1-2 outfit ideas "
            "with general pieces that would pair well. Be concise and casual."
        )
    else:
        wardrobe_lines = [
            f"- {item['name']} ({item['category']}, colors: {', '.join(item['colors'])})"
            for item in wardrobe["items"]
        ]
        prompt = (
            f"I'm considering buying this secondhand item:\n{item_desc}\n\n"
            f"Here's what I already own:\n" + "\n".join(wardrobe_lines) + "\n\n"
            "Suggest 1-2 complete outfits using the new item paired with "
            "specific pieces from my wardrobe. Be concise and casual."
        )

    response = model.generate_content(prompt)
    return response.text.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a shareable Instagram/TikTok caption for the outfit.
    """
    if not outfit or not outfit.strip():
        return "Could not generate a fit card — no outfit suggestion provided."

    model = _get_model(temperature=0.9)

    prompt = (
        f"Write a 2-4 sentence Instagram/TikTok caption for this thrifted outfit.\n\n"
        f"Item: {new_item['title']}\n"
        f"Price: ${new_item['price']}\n"
        f"Platform: {new_item['platform']}\n"
        f"Outfit idea: {outfit}\n\n"
        "Guidelines:\n"
        "- Sound casual and authentic, like a real OOTD post\n"
        "- Mention the item name, price, and platform naturally (once each)\n"
        "- Capture the outfit vibe in specific terms\n"
        "- Do NOT use hashtags"
    )

    response = model.generate_content(prompt)
    return response.text.strip()
