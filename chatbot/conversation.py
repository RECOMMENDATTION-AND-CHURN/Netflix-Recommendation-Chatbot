"""
chatbot/conversation.py
-------------------------
Two responsibilities:
1. Slot-filling: decide whether to ask a follow-up question or recommend now.
2. Change explanation: when a returning user changes one slot (e.g. swaps
   language but keeps genre), generate a ChatGPT-style acknowledgement
   instead of silently re-running with no explanation.

Design decision (documented, not hidden):
watch_time is treated as OPTIONAL and never gates the conversation — see
is_ready_to_recommend(). This is what makes "Tamil comedy movie" recommend
instantly while "I need a movie" still walks through language -> genre.
"""

from typing import Dict, Optional

QUESTIONS = {
    "language": "What language do you prefer? 🌐 (e.g. Tamil, English, Hindi, Korean...)",
    "genre": "What genre are you in the mood for? 🎭 (e.g. Comedy, Action, Thriller, Romance...)",
}

# Human-readable labels for the slots we track, used in change-explanation messages
SLOT_LABELS = {
    "genre": "genre",
    "language": "language",
    "mood": "mood",
    "audience": "audience",
    "watch_time": "watch time",
}


def is_ready_to_recommend(preferences: Dict) -> bool:
    if preferences.get("intent") == "similar_movie" and preferences.get("movie_name"):
        return True

    has_genre_signal = bool(preferences.get("genre") or preferences.get("mood"))
    has_language = bool(preferences.get("language"))
    return has_genre_signal and has_language


def next_question(preferences: Dict) -> Optional[str]:
    if is_ready_to_recommend(preferences):
        return None
    if not preferences.get("language"):
        return QUESTIONS["language"]
    if not (preferences.get("genre") or preferences.get("mood")):
        return QUESTIONS["genre"]
    return None


def describe_preference_change(before: Dict, after: Dict) -> Optional[str]:
    """
    Compares preferences before/after a merge and returns a ChatGPT-style
    sentence describing what changed, e.g.:
        "Got it — I'll keep Comedy and switch the language to English."
    Returns None if nothing meaningful changed (e.g. first message ever).
    """
    changed = []
    kept = []

    for slot, label in SLOT_LABELS.items():
        old_val = before.get(slot)
        new_val = after.get(slot)

        if old_val and new_val and old_val != new_val:
            changed.append(f"switch the {label} to {new_val}")
        elif new_val and old_val == new_val:
            kept.append(f"{label} as {new_val}")

    if not changed:
        return None  # nothing was actually changed vs. before — no need to comment

    change_text = " and ".join(changed)
    sentence = f"Got it — I'll {change_text}"

    if kept:
        sentence += f", and keep the {', '.join(kept)}"

    return sentence + "."
