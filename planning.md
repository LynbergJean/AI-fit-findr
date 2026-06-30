# FitFindr — Design Document

---

## Tools

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset by semantic similarity via Pinecone, with optional size and price filters. Returns matching items sorted by relevance.

**Input parameters:**
- `query` (str): Natural language description of what the user is looking for (e.g., "vintage graphic tee")
- `size` (str | None): Size to filter by, or None to skip
- `max_price` (float | None): Maximum price inclusive, or None to skip price filtering
- `top_k` (int): Number of results to return (default 5)

**What it returns:**
A list of listing dicts sorted by semantic similarity score. Each dict contains: id, title, description, category, style_tags, size, condition, price, colors, brand, platform, _score.

**What happens if it fails or returns nothing:**
Returns an empty list. The agent informs the user no results matched and suggests broadening their search.

---

### Tool 2: suggest_outfit

**What it does:**
Takes a thrifted item and the user's wardrobe, then calls Gemini to suggest 1–2 complete outfit combinations. If the wardrobe is empty, it provides general styling advice instead.

**Input parameters:**
- `new_item` (dict): A listing dict representing the item the user is considering
- `wardrobe` (dict): A dict with an 'items' key containing the user's wardrobe pieces

**What it returns:**
A string containing 1–2 outfit suggestions that pair the new item with specific wardrobe pieces (or general styling ideas if wardrobe is empty).

**What happens if it fails or returns nothing:**
If the LLM call fails, the exception propagates to the agent, which catches it and reports the error to the user.

---

### Tool 3: create_fit_card

**What it does:**
Generates a short, shareable Instagram/TikTok-style caption for the thrifted outfit using Gemini at a higher temperature for variety.

**Input parameters:**
- `outfit` (str): The outfit suggestion string from suggest_outfit()
- `new_item` (dict): The listing dict for the thrifted item

**What it returns:**
A 2–4 sentence caption that mentions the item name, price, and platform naturally while capturing the outfit vibe.

**What happens if it fails or returns nothing:**
If the outfit string is empty/whitespace, returns a descriptive error message without calling the LLM. If the LLM call fails, the exception propagates and the agent catches it.

---

## Planning Loop

**How the agent decides which tool to call next:**

The agent uses a ReAct-style loop powered by Gemini. The LLM receives the conversation history plus a system prompt describing available tools, and decides whether to call a tool or respond directly. Tool results are fed back into the conversation for the LLM to reason over.

The loop runs for up to 6 steps per turn, allowing multi-tool chains (e.g., search → suggest → fit card) in a single interaction.

---

## State Management

**How information flows between tools:**

A persistent state dict is maintained across conversation turns:

- `state["last_search_results"]` → results from the most recent search_listings call
- `state["last_outfit_suggestion"]` → string from the most recent suggest_outfit call
- `state["last_styled_item"]` → the item that was last styled
- `state["last_fit_card"]` → string from create_fit_card
- `state["wardrobe"]` → the user's wardrobe (example or empty)
- `state["conversation_history"]` → full message history for multi-turn context

---

## Error Handling

| Tool | Failure mode | Response |
|------|-------------|----------|
| search_listings | No results match the query | Inform user, suggest broadening search |
| suggest_outfit | LLM API call fails (network, rate limit, bad key) | Catch exception, report error |
| create_fit_card | Outfit input is empty/whitespace | Return descriptive error without calling LLM |
| create_fit_card | LLM API call fails | Catch exception, report error |

---

## Architecture

```
User Input (natural language query)
        │
        ▼
┌─────────────────────────────────────────┐
│        ReAct Agent Loop (agent.py)       │
│                                          │
│  1. Send user message + history to LLM   │
│  2. LLM decides: tool call or response?  │
│                                          │
│  If tool call:                           │
│    → Execute tool                        │
│    → Feed result back to LLM             │
│    → Repeat (up to 6 steps)              │
│                                          │
│  If direct response:                     │
│    → Return to user                      │
└─────────────────────────────────────────┘
        │
        ▼
Gradio Chat UI (app.py)
```

---

## Example Interaction

**User:** "I'm looking for a vintage graphic tee under $30. How would I style it?"

**Step 1:**
Agent sends message to LLM. LLM decides to call `search_listings(query="vintage graphic tee", max_price=30)`.

**Step 2:**
Search returns matches via Pinecone semantic search. Top results include "Graphic Tee — 2003 Tour Bootleg Style" ($24), "Vintage Band Tee — Faded Grey" ($19), etc.

LLM sees results, decides to call `suggest_outfit(item_index=0)` to style the top result.

**Step 3:**
Gemini receives the item details + wardrobe items and returns outfit suggestions pairing the tee with wardrobe pieces.

**Step 4:**
LLM composes a final response showing the search results, highlighting the top pick, and presenting the outfit idea. User can then ask for a fit card, more options, or refine the search.
