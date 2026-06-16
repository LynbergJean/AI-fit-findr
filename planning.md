# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset by keyword overlap, with optional size and price filters. Returns matching items sorted by relevance.

**Input parameters:**
- `description` (str): Keywords describing what the user is looking for (e.g., "vintage graphic tee")
- `size` (str | None): Size to filter by (case-insensitive substring match), or None to skip
- `max_price` (float | None): Maximum price inclusive, or None to skip price filtering

**What it returns:**
A list of listing dicts sorted by relevance score (keyword overlap count). Each dict contains: id, title, description, category, style_tags, size, condition, price, colors, brand, platform.

**What happens if it fails or returns nothing:**
Returns an empty list. The agent sets session["error"] to a message suggesting the user broaden their criteria and returns early without calling further tools.

---

### Tool 2: suggest_outfit

**What it does:**
Takes a thrifted item and the user's wardrobe, then calls the Groq LLM to suggest 1–2 complete outfit combinations. If the wardrobe is empty, it provides general styling advice instead.

**Input parameters:**
- `new_item` (dict): A listing dict representing the item the user is considering
- `wardrobe` (dict): A dict with an 'items' key containing the user's wardrobe pieces

**What it returns:**
A string containing 1–2 outfit suggestions that pair the new item with specific wardrobe pieces (or general styling ideas if wardrobe is empty).

**What happens if it fails or returns nothing:**
If the LLM call fails, the exception propagates to the agent, which catches it and sets session["error"] with a descriptive message. The agent returns early.

---

### Tool 3: create_fit_card

**What it does:**
Generates a short, shareable Instagram/TikTok-style caption for the thrifted outfit using the Groq LLM at a higher temperature for variety.

**Input parameters:**
- `outfit` (str): The outfit suggestion string from suggest_outfit()
- `new_item` (dict): The listing dict for the thrifted item

**What it returns:**
A 2–4 sentence caption that mentions the item name, price, and platform naturally while capturing the outfit vibe.

**What happens if it fails or returns nothing:**
If the outfit string is empty/whitespace, returns a descriptive error message without calling the LLM. If the LLM call fails, the exception propagates and the agent catches it.

---

### Additional Tools (if any)

None — three tools are sufficient for the core flow.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The agent uses a fixed sequential pipeline:

1. Parse the query (regex extraction of size, price, description)
2. Call search_listings → if empty results, stop with error
3. Select the top result
4. Call suggest_outfit with the selected item + wardrobe
5. Call create_fit_card with the outfit suggestion + item
6. Return the completed session

There is no dynamic branching — the pipeline always runs in order, with early termination only on errors or empty search results.

---

## State Management

**How does information from one tool get passed to the next?**

A single session dict is initialized at the start of run_agent() and threaded through every step. Each tool's output is stored in a named field:

- `session["parsed"]` → extracted description/size/max_price from query
- `session["search_results"]` → full list from search_listings
- `session["selected_item"]` → top result picked from search_results
- `session["outfit_suggestion"]` → string from suggest_outfit
- `session["fit_card"]` → string from create_fit_card
- `session["error"]` → set if anything fails; checked by app.py

This dict is the single source of truth for the entire interaction.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Set session["error"] to suggest broadening criteria, return early |
| suggest_outfit | LLM API call fails (network, rate limit, bad key) | Catch exception, set session["error"] with details, return early |
| create_fit_card | Outfit input is empty/whitespace | Return a descriptive error string without calling LLM |
| create_fit_card | LLM API call fails | Catch exception, set session["error"] with details, return early |

---

## Architecture

```
User Input (query + wardrobe choice)
        │
        ▼
┌─────────────────────────────────────────┐
│           run_agent() Planning Loop      │
│                                          │
│  1. _parse_query(query)                  │
│       → session["parsed"]                │
│                                          │
│  2. search_listings(desc, size, price)   │
│       → session["search_results"]        │
│       → if empty: set error, RETURN      │
│                                          │
│  3. Select top result                    │
│       → session["selected_item"]         │
│                                          │
│  4. suggest_outfit(item, wardrobe)       │
│       → session["outfit_suggestion"]     │
│       → if exception: set error, RETURN  │
│                                          │
│  5. create_fit_card(outfit, item)        │
│       → session["fit_card"]              │
│       → if exception: set error, RETURN  │
│                                          │
│  6. RETURN session                       │
└─────────────────────────────────────────┘
        │
        ▼
app.py handle_query() formats output
        │
        ▼
Gradio UI (3 panels: listing, outfit, fit card)
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

I'll give the AI my Tool 1/2/3 specs (inputs, outputs, failure modes) along with the data_loader utility and sample data, and ask it to implement each function. I'll test each tool independently:
- search_listings: verify keyword matching returns correct results for "vintage graphic tee" and that price/size filters work
- suggest_outfit: verify it returns non-empty text for both populated and empty wardrobes
- create_fit_card: verify it returns a caption string mentioning item name, price, platform

**Milestone 4 — Planning loop and state management:**

I'll give the AI my architecture diagram and state management spec, plus the completed tool functions, and ask it to implement run_agent(). I'll test with:
- Happy path: "vintage graphic tee under $30" → expect all session fields populated
- No-results path: "designer ballgown size XXS under $5" → expect error set
- Empty wardrobe: verify suggest_outfit still returns styling advice

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
Agent parses the query:
- description: "I'm looking for a vintage graphic tee I mostly wear baggy jeans and chunky sneakers What's out there and how would I style it"
- max_price: 30.0
- size: None

Calls `search_listings(description="...", size=None, max_price=30.0)`.

**Step 2:**
search_listings returns matches. Top results include "Graphic Tee — 2003 Tour Bootleg Style" ($24), "Vintage Band Tee — Faded Grey" ($19), "Y2K Baby Tee — Butterfly Print" ($18).

Agent selects the top-scored result and stores it as session["selected_item"].

**Step 3:**
Agent calls `suggest_outfit(new_item=selected_item, wardrobe=example_wardrobe)`.

The LLM receives the item details + wardrobe items and returns something like:
"Pair this bootleg tee with your baggy straight-leg jeans and chunky white sneakers for a relaxed streetwear look. Layer your black denim jacket over it when it gets cooler."

**Step 4:**
Agent calls `create_fit_card(outfit=suggestion, new_item=selected_item)`.

The LLM generates a caption like:
"Found this 2003 Tour Bootleg tee on depop for $24 and it's giving effortless grunge energy. Threw it on with my go-to baggy jeans and chunky sneakers — the faded graphic does all the talking."

**Final output to user:**
- Panel 1: Listing details (title, price, size, condition, platform, description)
- Panel 2: Outfit suggestion from the LLM
- Panel 3: Fit card caption
