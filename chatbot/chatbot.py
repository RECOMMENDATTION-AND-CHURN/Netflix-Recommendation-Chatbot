import json

from prompts import SYSTEM_PROMPT
from gemini_api import ask_gemini


def extract_preferences(user_input):

    prompt = f"""
{SYSTEM_PROMPT}

User Message:

{user_input}
"""

    response = ask_gemini(prompt)

    response = response.replace("```json", "")
    response = response.replace("```", "")
    response = response.strip()

    try:

        preferences = json.loads(response)

        return preferences

    except Exception:

        return {
            "mood": None,
            "genre": None,
            "language": None,
            "watch_time": None,
            "audience": None
        }


def chatbot():

    print("🎬 Netflix AI Chatbot")
    print("Tell me what kind of movie you want.\n")

    user_input = input("You : ")

    preferences = extract_preferences(user_input)

    print("\nExtracted Preferences\n")

    print(json.dumps(preferences, indent=4))

    return preferences


if __name__ == "__main__":

    chatbot()