"""
DEVELOPED BY FAHUMITHA AFROSE(8208E23ASR019)
""" 
chatbot/chatbot.py
--------------------
LLM-facing layer: builds the Gemini prompt from recent conversation
history, calls Gemini, and parses its JSON reply into a preferences dict.
Also contains a single-user CLI chatbot() for quick manual testing
outside the Streamlit/Flask UIs.
"""

from typing import Optional, Dict, Any

from database.chat_store import save_chat, get_recent_chat
from chatbot.memory import merge_preferences
from chatbot.prompts import SYSTEM_PROMPT
from chatbot.gemini_api import ask_gemini
import json


USER_ID = 1

# Returned when Gemini responds but its reply isn't valid JSON (rare, but
# possible with any LLM) — an "empty" preferences dict so callers can
# keep merging without special-casing a parse failure.
_EMPTY_PREFERENCES: Dict[str, Any] = {
    "intent": None,
    "movie_name": None,
    "mood": None,
    "genre": None,
    "language": None,
    "watch_time": None,
    "audience": None,
}


def extract_preferences(user_input: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Asks Gemini to extract movie preferences from `user_input` plus
    recent conversation context, and returns the parsed preferences dict.

    Returns None only if Gemini itself is unreachable (see
    chatbot/gemini_api.py's retry logic) — a malformed-but-present reply
    still returns a (mostly empty) dict rather than None, so callers can
    treat "no signal extracted" and "API down" differently upstream.

    user_id is optional and defaults to the module-level USER_ID (used
    by the single-user CLI chatbot() below) so existing single-argument
    callers keep working exactly as before. app.py (the multi-user web
    UI) passes the real logged-in user's id so conversation context is
    built from THEIR chat history, not always user 1's.
    """
    effective_user_id = USER_ID if user_id is None else user_id
    conversation = build_conversation(effective_user_id, user_input)

    prompt = f"""
        {SYSTEM_PROMPT}

    Conversation:

        {conversation}
""" 

    response = ask_gemini(prompt)

    if response is None:

        return None

    response = response.replace("```json", "")
    response = response.replace("```", "")
    response = response.strip()

    try:

        return json.loads(response)

    except Exception:

        return dict(_EMPTY_PREFERENCES)


def chatbot() -> None:
    """Single-user, terminal-based chat loop for manual/local testing.
    Not used by app.py or webapp/server.py (both are multi-user and have
    their own UI loops) — this is purely a developer convenience."""

    print("\n🎬 Netflix AI Chatbot")
    print("Type 'exit' to quit.\n")

    while True:

        user_input = input("You : ")

        if user_input.lower() == "exit":
            break

        # Save user message
        save_chat(USER_ID, "user", user_input)

        extracted = extract_preferences(user_input)

        if extracted is None:

            print("\nBot : Gemini API unavailable.\n")
            continue

        # Merge with previous preferences
        preferences = merge_preferences(USER_ID, extracted)

        # Save assistant response
        save_chat(
            USER_ID,
            "assistant",
            json.dumps(preferences)
        )

        print("\nCurrent Preferences\n")

        print(json.dumps(preferences, indent=4))

        print("\n-----------------------------------\n")


def build_conversation(user_id: int, user_message: str) -> str:
    """Formats recent chat history + the new message into the plain-text
    transcript the Gemini prompt expects (see extract_preferences)."""

    history = get_recent_chat(user_id)

    conversation = ""

    for role, message in history:

        if role == "user":
            conversation += f"User: {message}\n"

        else:
            conversation += f"Assistant: {message}\n"

    conversation += f"User: {user_message}\n"

    return conversation

if __name__ == "__main__":

    chatbot()
