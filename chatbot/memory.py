"""
DEVELOPED BY FAHUMITHA AFROSE(8208E23ASR019)
"""

from typing import Dict, Any

from database.chat_store import load_preferences, save_preferences

def merge_preferences(user_id: int, new_preferences: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge newly extracted preferences with existing preferences.

    If the user's intent has changed since last time (e.g. they were
    describing preferences and now ask for movies "similar to X"), every
    other slot is wiped first — an old genre/language from a different
    intent shouldn't silently carry over into a new one. Otherwise, any
    non-null field in new_preferences overwrites the stored value; null
    fields leave the existing value untouched (so "Tamil" then "comedy"
    across two turns still ends up as {language: Tamil, genre: comedy}).

    Persists the merged result via save_preferences() and returns it.
    """

    current = load_preferences(user_id)

    # -----------------------------
    # If intent changes
    # -----------------------------
    if (
        current["intent"] is not None and
        new_preferences["intent"] is not None and
        current["intent"] != new_preferences["intent"]
    ):

        current = {
            "intent": None,
            "movie_name": None,
            "mood": None,
            "genre": None,
            "language": None,
            "watch_time": None,
            "audience": None
        }

    # -----------------------------
    # Merge values
    # -----------------------------
    for key, value in new_preferences.items():

        if value is not None:
            current[key] = value

    save_preferences(user_id, current)

    return current
