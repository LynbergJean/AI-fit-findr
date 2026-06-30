"""
app.py

Gradio chat interface for FitFindr with multi-turn conversation.

Run with:
    python app.py
"""

import gradio as gr

from agent import run_agent
from embeddings import build_index
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


def initialize():
    """Build Pinecone index on startup (idempotent)."""
    try:
        count = build_index()
        print(f"✓ Pinecone index ready ({count} listings)")
    except Exception as e:
        print(f"⚠ Index build failed: {e}. Search may not work.")


def respond(user_message: str, chat_history: list, wardrobe_choice: str, agent_state: dict):
    """Handle a user message and return the updated chat."""
    if not user_message.strip():
        return "", chat_history, agent_state

    # Set wardrobe in state
    if "wardrobe" not in agent_state:
        agent_state["wardrobe"] = (
            get_example_wardrobe() if wardrobe_choice == "Example wardrobe"
            else get_empty_wardrobe()
        )

    # Get conversation history from state
    conversation_history = agent_state.get("conversation_history", [])

    # Run agent
    response, conversation_history, agent_state = run_agent(
        user_message=user_message,
        conversation_history=conversation_history,
        state=agent_state,
    )

    # Save updated history back to state
    agent_state["conversation_history"] = conversation_history

    # Update Gradio chat display
    chat_history.append((user_message, response))

    return "", chat_history, agent_state


def build_interface():
    with gr.Blocks(title="FitFindr", theme=gr.themes.Soft()) as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas. Ask follow-up questions to refine results.

**Try:** "Find me a cozy fall layer under $40" → "Can you style that with my wardrobe?" → "Give me a caption for it"
        """)

        agent_state = gr.State({})

        with gr.Row():
            wardrobe_choice = gr.Radio(
                choices=["Example wardrobe", "Empty wardrobe (new user)"],
                value="Example wardrobe",
                label="Wardrobe",
            )

        chatbot = gr.Chatbot(label="FitFindr", height=500)

        with gr.Row():
            msg = gr.Textbox(
                label="Message",
                placeholder="e.g. Find me a vintage graphic tee under $30...",
                scale=4,
            )
            send_btn = gr.Button("Send", variant="primary", scale=1)

        gr.Examples(
            examples=[
                "Find me a cozy fall layer under $40",
                "Looking for vintage graphic tees",
                "I need black combat boots",
                "Something cottagecore for summer",
                "90s streetwear vibes, size M",
            ],
            inputs=msg,
            label="Try these",
        )

        # Event handlers
        send_btn.click(
            fn=respond,
            inputs=[msg, chatbot, wardrobe_choice, agent_state],
            outputs=[msg, chatbot, agent_state],
        )
        msg.submit(
            fn=respond,
            inputs=[msg, chatbot, wardrobe_choice, agent_state],
            outputs=[msg, chatbot, agent_state],
        )

    return demo


if __name__ == "__main__":
    initialize()
    demo = build_interface()
    demo.launch()
