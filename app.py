import streamlit as st
import json

from chatbot.chatbot import extract_preferences
from chatbot.memory import merge_preferences
from chatbot.database import save_chat

USER_ID = 1

st.set_page_config(
    page_title="Netflix AI Chatbot",
    page_icon="🎬",
    layout="centered"
)

st.title("🎬 Netflix AI Chatbot")

st.write("Tell me what kind of movie you want.")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous messages
for msg in st.session_state.messages:

    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User input
prompt = st.chat_input("Type your message...")

if prompt:

    # Show user message
    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    with st.chat_message("user"):
        st.markdown(prompt)

    # Save user message
    save_chat(USER_ID, "user", prompt)

    # Extract preferences using Gemini
    extracted = extract_preferences(prompt)

    if extracted is None:

        bot_reply = "❌ Unable to connect to Gemini API."

    else:

        preferences = merge_preferences(USER_ID, extracted)

        bot_reply = "### Extracted Preferences\n\n"
        bot_reply += "```json\n"
        bot_reply += json.dumps(preferences, indent=4)
        bot_reply += "\n```"

        save_chat(
            USER_ID,
            "assistant",
            json.dumps(preferences)
        )

    with st.chat_message("assistant"):
        st.markdown(bot_reply)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": bot_reply
        }
    )