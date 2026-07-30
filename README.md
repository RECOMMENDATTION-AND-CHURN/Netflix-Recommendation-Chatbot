# Netflix-Based Movie Recommendation Chatbot with Customer Churn Prediction

## AI-Powered Personalized Movie Recommendation and Customer Retention System

### Intelligent Movie Recommendation Platform with Conversational AI and Churn Prediction

Netflix-Based Movie Recommendation Chatbot with Customer Churn Prediction is an AI-powered platform that provides personalized movie recommendations through a conversational chatbot while predicting customer churn using Machine Learning.

The system understands natural language using Google's Gemini AI, remembers user preferences across conversations, recommends movies based on semantic similarity using Sentence Transformers, and enriches recommendations with TMDB movie information such as posters, trailers, ratings, genres, and descriptions.

Additionally, the project predicts whether a customer is likely to churn based on their streaming behavior, enabling businesses to improve customer retention strategies.



# Features

## AI Conversational Movie Chatbot

- Natural language movie conversations
- Understands user preferences automatically
- Multi-turn conversation support
- Context-aware recommendation system
- Personalized recommendations using Gemini AI

## Intelligent Movie Recommendation

- Semantic similarity using Sentence Transformers
- Content-based recommendation engine
- Personalized recommendations
- Similar movie suggestions
- Genre-based recommendations
- Language-based recommendations
- Mood-based recommendations

## User Preference Memory

- Remembers user preferences
- Updates preferences dynamically
- Stores conversation history
- Personalized recommendation experience
- Slot-filling conversation management

## Customer Churn Prediction

- Predicts customer churn probability
- Machine Learning based prediction
- Customer retention analysis
- Behavioral analytics
- Business insights dashboard

## TMDB Integration

- Movie posters
- Movie trailers
- Ratings
- Release date
- Runtime
- Genres
- Cast information
- Movie overview

## User Management

- User Registration
- Secure Login
- User Profile
- Favorite Movies
- Movie Ratings
- Feedback System
- Activity Tracking



# AI Technologies

- Google Gemini AI
- Sentence Transformers
- Content-Based Recommendation
- Semantic Search
- Machine Learning
- LightGBM
- Natural Language Processing (NLP)
- Customer Churn Prediction



# System Architecture

```text
                User
                  │
                  ▼
        Streamlit Chat Interface
                  │
                  ▼
          Gemini AI Chatbot
                  │
                  ▼
     Preference Extraction Engine
                  │
                  ▼
      User Preference Memory
                  │
                  ▼
      Recommendation Engine
     ├── Semantic Embeddings
     ├── Content-Based Filtering
     ├── Similarity Search
     └── Recommendation Ranking
                  │
                  ▼
          TMDB Movie API
      (Poster • Trailer • Ratings)
                  │
                  ▼
      Personalized Movie Results
                  │
                  ▼
      Customer Churn Prediction
                  │
                  ▼
           Analytics Dashboard




# Tech Stack

## Frontend

- Streamlit
- HTML
- CSS
- JavaScript

## Backend

- Python

## AI & Machine Learning

- Google Gemini API
- Sentence Transformers
- LightGBM
- Scikit-learn
- Pandas
- NumPy

## Database

- SQLite

## External API

- TMDB API

## Development Tools

- Visual Studio Code
- Git
- GitHub



# Project Structure

```text
Netflix-Recommendation-Chatbot
│
├── app.py
├── dashboard.py
├── config.py
├── generate_embeddings.py
├── requirements.txt
├── README.md
│
├── chatbot/
│   ├── chatbot.py
│   ├── conversation.py
│   ├── database.py
│   ├── gemini_api.py
│   ├── memory.py
│   └── prompts.py
│
├── recommendation/
│   ├── recommendation.py
│   ├── movie_service.py
│   └── tmdb_api.py
│
├── churn/
│   └── model.py
│
├── database/
│   ├── connection.py
│   ├── auth_store.py
│   ├── chat_store.py
│   ├── activity_store.py
│   ├── analytics_store.py
│   ├── favorites_store.py
│   ├── feedback_store.py
│   ├── interaction_store.py
│   ├── ratings_store.py
│   └── backup.py
│
├── models/
│   ├── movie_embeddings.pkl
│   └── churn_model.pkl
│
├── data/
│   ├── tmdb_Preprocessed_dataset.csv
│   ├── tmdb_raw_Dataset.csv
│   └── streaming_churn_dataset.csv
│
├── assets/
│   ├── style.css
│   └── script.js
│
├── notebooks/
│   ├── Data_Preprocessing.ipynb
│   ├── Algorithm_Selection.ipynb
│   └── embedding_generation.ipynb
│
├── tests/
│
└── webapp/
    └── frontend/




# Project Objectives

- Provide personalized movie recommendations.
- Build an AI-powered conversational movie chatbot.
- Understand user preferences using Natural Language Processing.
- Store user preferences for future conversations.
- Recommend similar movies using semantic search.
- Display movie posters, trailers, and ratings through TMDB API.
- Predict customer churn using Machine Learning.
- Improve user engagement and retention.
- Deliver an intelligent movie discovery experience.



# Future Enhancements

- Hybrid Recommendation System
- Collaborative Filtering
- Voice-based Movie Assistant
- Multi-language Chat Support
- Emotion-based Recommendation
- Real-time Trending Movies
- Explainable AI Recommendations
- Cloud Deployment
- Mobile Application
- Multi-Agent AI Movie Assistant



# Contributors

**Netflix Recommendation Team**

Elavarasan-8208E23ASR018 (Churn Prediction)
Fahumitha Afrose-8208E23ASR019 (Chatbot)
Fathima Fazlina-8208E23ASR020 (Frontend)
Gayathri-8208E23ASR021 (Recommendation Engine)
Harihara Sudhan-8208E23ASR022 (Database)


Developed an intelligent AI-powered movie recommendation system using Natural Language Processing, Machine Learning, and Google Gemini AI.

---

# License

This project is licensed under the **MIT License**.

---

# Vision

Our vision is to build an intelligent movie recommendation platform that combines Conversational AI, Machine Learning, and Customer Analytics to deliver a highly personalized entertainment experience.

The platform understands user preferences through natural conversations, remembers user interests, recommends relevant movies using semantic similarity, enriches recommendations with TMDB movie information, and predicts customer churn to help streaming platforms improve customer retention and engagement.
