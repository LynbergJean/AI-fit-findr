# FitFindr

A secondhand fashion shopping assistant powered by semantic search and LLM-based styling. Find thrifted clothing, get outfit suggestions, and generate shareable fit cards — all through a conversational interface.

## Project Structure

```
Fit-Findr/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading data
├── agent.py                   # ReAct-style conversational agent
├── app.py                     # Gradio chat UI
├── embeddings.py              # Pinecone vector index + semantic search
├── tools.py                   # Agent tools (search, outfit, fit card)
├── planning.md                # Architecture & design decisions
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file with your API keys:
```
GEMINI_API_KEY=your_key_here
PINECONE_API_KEY=your_key_here
```

## Usage

Launch the Gradio chat interface:
```bash
python app.py
```

Or run the agent in CLI mode:
```bash
python agent.py
```

## The Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

## Wardrobe

`data/wardrobe_schema.json` defines how a user's existing wardrobe is represented. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items
- `empty_wardrobe`: a starting template for a new user

## How It Works

1. User describes what they're looking for in natural language
2. The agent uses semantic search (sentence-transformers + Pinecone) to find matching listings
3. On request, it pairs finds with the user's wardrobe for outfit suggestions (via Gemini)
4. It can generate shareable social media captions for the styled outfit
