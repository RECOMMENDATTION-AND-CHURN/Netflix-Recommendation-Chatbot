from chatbot.database import load_preferences, save_preferences

def merge_preferences(user_id, new_preferences):
    """
    Merge newly extracted preferences with existing preferences.
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