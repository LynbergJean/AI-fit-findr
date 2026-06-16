"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for.
        size:        Size string to filter by, or None to skip size filtering.
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches.
    """
    listings = load_listings()
    keywords = description.lower().split()

    results = []
    for listing in listings:
        # Filter by price
        if max_price is not None and listing["price"] > max_price:
            continue
        # Filter by size (case-insensitive substring match)
        if size is not None and size.lower() not in listing["size"].lower():
            continue

        # Score by keyword overlap across title, description, style_tags, colors, category
        searchable = " ".join([
            listing["title"].lower(),
            listing["description"].lower(),
            " ".join(listing["style_tags"]).lower(),
            " ".join(listing["colors"]).lower(),
            listing["category"].lower(),
            (listing["brand"] or "").lower(),
        ])
        score = sum(1 for kw in keywords if kw in searchable)

        if score > 0:
            results.append((score, listing))

    # Sort by score descending
    results.sort(key=lambda x: x[0], reverse=True)
    return [listing for _, listing in results]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing wardrobe items.

    Returns:
        A string with outfit suggestions. If wardrobe is empty, returns general
        styling advice.
    """
    client = _get_groq_client()

    item_desc = (
        f"{new_item['title']} — {new_item['description']} "
        f"(Category: {new_item['category']}, Colors: {', '.join(new_item['colors'])}, "
        f"Style: {', '.join(new_item['style_tags'])})"
    )

    if not wardrobe.get("items"):
        prompt = (
            f"I'm considering buying this secondhand item:\n{item_desc}\n\n"
            "I don't have a wardrobe on file yet. Suggest 1-2 outfit ideas "
            "with general pieces that would pair well with this item. "
            "Keep it concise and casual in tone."
        )
    else:
        wardrobe_lines = []
        for item in wardrobe["items"]:
            wardrobe_lines.append(
                f"- {item['name']} ({item['category']}, colors: {', '.join(item['colors'])})"
            )
        wardrobe_text = "\n".join(wardrobe_lines)
        prompt = (
            f"I'm considering buying this secondhand item:\n{item_desc}\n\n"
            f"Here's what I already own:\n{wardrobe_text}\n\n"
            "Suggest 1-2 complete outfits using the new item paired with "
            "specific pieces from my wardrobe. Be concise and casual in tone."
        )

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        Returns an error message if outfit is empty.
    """
    if not outfit or not outfit.strip():
        return "Could not generate a fit card — no outfit suggestion provided."

    client = _get_groq_client()

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

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()
