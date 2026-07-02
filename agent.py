"""
agent.py

ReAct-style agent with conversation memory for FitFindr.
Uses Google Gemini for reasoning. The LLM decides which tool to call
or no tools at all based on the context of the convo.
"""

import json
import os
import re

from dotenv import load_dotenv
import google.generativeai as genai

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe

load_dotenv()

SYSTEM_PROMPT = """You are FitFindr, a secondhand fashion shopping assistant. You help users find thrifted clothing and style outfits.

You have access to these tools:

1. search_listings(query, size, max_price, top_k)
   - Searches secondhand listings by semantic similarity
   - query: natural language description of what to find
   - size: optional size filter (e.g. "M", "W30", "US 8")
   - max_price: optional max price as a number
   - top_k: how many results (default 5)

2. suggest_outfit(item_index)
   - Suggests 1-2 outfits pairing search result #item_index with the user's wardrobe
   - item_index: which search result to use (0-based)

3. create_fit_card(item_index)
   - Generates a shareable social media caption for the outfit
   - item_index: which search result to style (must call suggest_outfit first)

To use a tool, respond with EXACTLY this format:
TOOL: tool_name
ARGS: {"param": "value"}

After seeing tool results, you can call another tool or respond to the user.
When you're ready to respond to the user (no more tools needed), just write your response directly.

Rules:
- If the user asks to find/search for something, use search_listings
- If they ask to style an item or want outfit ideas, use suggest_outfit
- If they want a caption/fit card, use create_fit_card
- If they say "show me more" or "other options", call search_listings again with top_k increased or adjusted query
- If they refine ("what about in black?", "cheaper options"), modify the previous search params
- If they just want to chat or ask a question, respond directly without tools
- Always be concise, casual, and helpful
- When showing search results, format them nicely with title, price, size, and platform
"""

MAX_REACT_STEPS = 6


def _get_model():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config=genai.GenerationConfig(temperature=0.3, max_output_tokens=500),
    )


def _parse_tool_call(text: str) -> tuple[str | None, dict | None]:
    """Extract tool name and args from LLM output."""
    tool_match = re.search(r"TOOL:\s*(\w+)", text)
    args_match = re.search(r"ARGS:\s*(\{.*?\})", text, re.DOTALL)

    if tool_match and args_match:
        try:
            args = json.loads(args_match.group(1))
            return tool_match.group(1), args
        except json.JSONDecodeError:
            return None, None
    return None, None


def _execute_tool(tool_name: str, args: dict, state: dict) -> str:
    """Execute a tool and return the result as a string."""
    try:
        if tool_name == "search_listings":
            results = search_listings(
                query=args.get("query", ""),
                size=args.get("size"),
                max_price=args.get("max_price"),
                top_k=args.get("top_k", 5),
            )
            state["last_search_results"] = results
            if not results:
                return "No listings found matching that criteria. Suggest the user broaden their search."

            formatted = []
            for i, item in enumerate(results):
                score = item.get("_score", 0)
                formatted.append(
                    f"[{i}] {item['title']} — ${item['price']:.0f} | "
                    f"Size: {item['size']} | {item['platform']} | "
                    f"Style: {', '.join(item['style_tags'])} | "
                    f"Relevance: {score:.2f}"
                )
            return "Search results:\n" + "\n".join(formatted)

        elif tool_name == "suggest_outfit":
            idx = int(args.get("item_index", 0))
            results = state.get("last_search_results", [])
            if not results or idx >= len(results):
                return "No search results available. Run search_listings first."

            item = results[idx]
            wardrobe = state.get("wardrobe", get_example_wardrobe())
            suggestion = suggest_outfit(new_item=item, wardrobe=wardrobe)
            state["last_outfit_suggestion"] = suggestion
            state["last_styled_item"] = item
            return f"Outfit suggestion for '{item['title']}':\n{suggestion}"

        elif tool_name == "create_fit_card":
            idx = int(args.get("item_index", 0))
            results = state.get("last_search_results", [])
            outfit = state.get("last_outfit_suggestion", "")

            if not outfit:
                return "No outfit suggestion available. Run suggest_outfit first."

            item = state.get("last_styled_item", results[idx] if results else {})
            card = create_fit_card(outfit=outfit, new_item=item)
            state["last_fit_card"] = card
            return f"Fit card:\n{card}"

        else:
            return f"Unknown tool: {tool_name}"

    except Exception as e:
        return f"Tool error: {e}"


def run_agent(user_message: str, conversation_history: list[dict], state: dict) -> tuple[str, list[dict], dict]:
    """
    Run one turn of the ReAct agent.

    Args:
        user_message:         The user's latest message
        conversation_history: List of {"role": ..., "content": ...} messages
        state:                Persistent state dict (search results, wardrobe, etc.)

    Returns:
        (agent_response, updated_history, updated_state)
    """
    model = _get_model()

    # Add user message to history
    conversation_history.append({"role": "user", "content": user_message})

    # Build Gemini chat history
    # Gemini uses "user" and "model" roles
    gemini_history = []
    for msg in conversation_history[:-1]:  # all except last (we'll send that as the new message)
        role = "model" if msg["role"] == "assistant" else "user"
        gemini_history.append({"role": role, "parts": [msg["content"]]})

    chat = model.start_chat(
        history=[{"role": "user", "parts": [SYSTEM_PROMPT]}, {"role": "model", "parts": ["Understood. I'm FitFindr, ready to help."]}] + gemini_history
    )

    current_message = user_message

    for _ in range(MAX_REACT_STEPS):
        response = chat.send_message(current_message)
        llm_output = response.text.strip()

        # Check if LLM wants to call a tool
        tool_name, args = _parse_tool_call(llm_output)

        if tool_name is None:
            # No tool call — this is the final response
            conversation_history.append({"role": "assistant", "content": llm_output})
            return llm_output, conversation_history, state

        # Execute the tool
        tool_result = _execute_tool(tool_name, args, state)

        # Feed tool result back into the chat
        current_message = f"[Tool Result]\n{tool_result}"

    # If we hit max steps
    fallback = "I found some info but hit my processing limit. Let me know how to help further."
    conversation_history.append({"role": "assistant", "content": fallback})
    return fallback, conversation_history, state


# test

if __name__ == "__main__":
    history = []
    state = {"wardrobe": get_example_wardrobe()}

    print("FitFindr Agent (type 'quit' to exit)\n")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break

        response, history, state = run_agent(user_input, history, state)
        print(f"\nFitFindr: {response}\n")
