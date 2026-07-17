from database.chat_store import save_chat, get_recent_chat
from chatbot.memory import merge_preferences
from chatbot.prompts import SYSTEM_PROMPT
from chatbot.gemini_api import ask_gemini
import json


USER_ID = 1


def extract_preferences(user_input):
    conversation = build_conversation(USER_ID, user_input)

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

        return {
            "intent": None,
            "movie_name": None,
            "mood": None,
            "genre": None,
            "language": None,
            "watch_time": None,
            "audience": None
        }


def chatbot():

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


def build_conversation(user_id, user_message):

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