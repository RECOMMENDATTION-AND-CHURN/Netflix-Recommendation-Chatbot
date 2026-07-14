import streamlit as st
import json
import os

from recommendation.movie_service import MovieRecommendationService
from chatbot.chatbot import extract_preferences
from chatbot.memory import merge_preferences
from chatbot.database import save_chat

USER_ID = 1
BASE_DIR = os.path.dirname(__file__)

service = MovieRecommendationService(
    dataset_path=os.path.join(BASE_DIR, "data", "tmdb_Preprocessed_dataset.csv"),
    embedding_path=os.path.join(BASE_DIR, "models", "movie_embeddings.pkl")
)
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

        movies = service.get_recommendations_with_details(
            preferences,
            top_n=5
        )

        with st.chat_message("assistant"):

            st.markdown("## 🎬 Recommended Movies")

            if not movies:
                st.warning("No movies matched your preferences.")

            else:

                for movie in movies:

                    st.subheader(movie["title"])

                    if movie["poster"]:
                        st.image(movie["poster"], width=250)

                    col1, col2 = st.columns(2)

                    with col1:
                        st.write(f"⭐ Rating : {movie['rating']}")
                        st.write(f"🎭 Genre : {movie['genre']}")
                        st.write(f"🕒 Runtime : {movie['runtime']} min")

                    with col2:
                        st.write(f"🎬 Director : {movie['director']}")

                        if movie["cast"]:
                            st.write("👥 Cast")
                            st.write(", ".join(movie["cast"]))

                    st.write(movie["overview"])

                    if movie["trailer"]:
                        st.link_button(
                            "▶ Watch Trailer",
                            movie["trailer"]
                        )

                    st.divider()

        save_chat(
            USER_ID,
            "assistant",
            json.dumps(preferences)
        )

