"""
dashboard.py
-------------
Provider-only analytics dashboard. Completely separate Streamlit app from
app.py (the chatbot) — never imported by, or linked from, the chatbot.
Reads user_activity + ratings + users, scores churn risk, and explains
predictions with SHAP.

Run with:
    streamlit run dashboard.py
"""

import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

from logging_config import configure_logging

logger = configure_logging(component="dashboard")

from database.activity_store import get_all_user_activity
from database.auth_store import get_all_users
from database.ratings_store import get_all_ratings
from database.analytics_store import (
    get_recent_activity_feed, get_signup_trend, get_recommendation_trend,
    get_recommendation_acceptance_rate, get_movie_popularity,
)
from churn.model import predict_churn_probability, risk_label, _load_bundle, build_feature_row

st.set_page_config(page_title="Netflix AI — Provider Dashboard", page_icon="📊", layout="wide")

# Reuse the same theme as the chatbot (app.py) so both surfaces feel like
# one product instead of one styled app and one default-Streamlit page.
BASE_DIR = os.path.dirname(__file__)
css_path = os.path.join(BASE_DIR, "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
# Plotly charts default to a light theme — force dark so they don't clash
# with the red/black background.
px.defaults.template = "plotly_dark"

st.markdown(
    """
    <div class="nf-hero">
        <h1>📊 Provider Dashboard</h1>
        <p>Engagement analytics &amp; churn risk — provider/admin only. Never shown inside the chatbot.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

@st.cache_data(ttl=30, show_spinner=False)
def _load_dashboard_data():
    return get_all_user_activity(), get_all_users(), get_all_ratings()


activity_rows, users, ratings = _load_dashboard_data()

if not activity_rows:
    st.info("No user activity recorded yet. Have someone sign up and use the chatbot (app.py) first.")
    st.stop()

df = pd.DataFrame(activity_rows)
users_df = pd.DataFrame(users)

# --- Score every user with the churn model ---
probs, labels = [], []
for _, row in df.iterrows():
    try:
        p = predict_churn_probability(row.to_dict())
    except FileNotFoundError:
        st.error("No trained churn model found. Run `python -m churn.model` first.")
        st.stop()
    probs.append(p)
    labels.append(risk_label(p))

df["churn_probability"] = probs
df["risk_label"] = labels

# =====================================================
# Top-line metrics
# =====================================================
now = datetime.now()

total_users = len(users_df) if not users_df.empty else len(df)

new_users_7d = 0
if not users_df.empty and "created_at" in users_df.columns:
    created = pd.to_datetime(users_df["created_at"], errors="coerce")
    new_users_7d = int((created >= now - timedelta(days=7)).sum())

active_users = int((df["days_since_last_login"].fillna(99) <= 7).sum())
high_risk_users = int((df["churn_probability"] >= 0.7).sum())
low_risk_users = int((df["churn_probability"] < 0.4).sum())
avg_satisfaction = round(df["satisfaction_score"].fillna(0).mean(), 2)
retention_rate = round(100 * (1 - df["churn_probability"].mean()), 1)
avg_rating_platform = round(sum(r["rating"] for r in ratings) / len(ratings), 2) if ratings else 0.0

# Daily / Monthly Active Users, based on last_activity timestamp
dau, mau = 0, 0
if "last_activity" in df.columns:
    last_activity = pd.to_datetime(df["last_activity"], errors="coerce")
    dau = int((last_activity.dt.date == now.date()).sum())
    mau = int((last_activity >= now - timedelta(days=30)).sum())

with st.container(border=True, key="nf_panel_kpis_1"):
    row1 = st.columns(5)
    row1[0].metric("Total Users", total_users)
    row1[1].metric("New Users (7d)", new_users_7d)
    row1[2].metric("Active Users (7d)", active_users)
    row1[3].metric("Daily Active Users", dau)
    row1[4].metric("Monthly Active Users", mau)

with st.container(border=True, key="nf_panel_kpis_2"):
    row2 = st.columns(5)
    row2[0].metric("High-Risk Users", high_risk_users)
    row2[1].metric("Low-Risk Users", low_risk_users)
    row2[2].metric("Avg Satisfaction", f"{avg_satisfaction} / 5")
    row2[3].metric("Avg Rating (platform)", f"{avg_rating_platform} / 5")
    row2[4].metric("Est. Retention Rate", f"{retention_rate}%")

st.divider()

# =====================================================
# Charts
# =====================================================
col_a, col_b = st.columns(2)

with st.container(border=True, key="nf_panel_charts_1"):
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Churn Risk Distribution")
        risk_counts = df["risk_label"].value_counts().reset_index()
        risk_counts.columns = ["Risk Level", "Users"]
        fig = px.pie(risk_counts, names="Risk Level", values="Users", hole=0.4,
                     color="Risk Level",
                     color_discrete_map={"High Risk": "#e74c3c", "Medium Risk": "#f39c12", "Low Risk": "#2ecc71"})
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Genre Popularity")
        if "preferred_genre" in df.columns and df["preferred_genre"].notna().any():
            genre_counts = df["preferred_genre"].value_counts().reset_index()
            genre_counts.columns = ["Genre", "Users"]
            fig2 = px.bar(genre_counts, x="Genre", y="Users")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No genre preferences recorded yet.")

with st.container(border=True, key="nf_panel_charts_2"):
    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("Session Duration (minutes)")
        fig3 = px.histogram(df, x="session_duration", nbins=20)
        st.plotly_chart(fig3, use_container_width=True)

    with col_d:
        st.subheader("Recommendation Requests per User")
        fig4 = px.histogram(df, x="recommendation_requests", nbins=20)
        st.plotly_chart(fig4, use_container_width=True)

st.divider()

# =====================================================
# Module 5 — Weekly / Monthly trends
# =====================================================
st.markdown('<div class="nf-section-title">📈 Trends Over Time</div>', unsafe_allow_html=True)

with st.container(border=True, key="nf_panel_trends"):
    trend_period = st.radio("Granularity", ["Weekly", "Monthly"], horizontal=True, label_visibility="collapsed")
    freq, periods, period_label = ("W", 8, "week") if trend_period == "Weekly" else ("M", 6, "month")

    signup_trend = get_signup_trend(freq=freq, periods=periods)
    rec_trend = get_recommendation_trend(freq=freq, periods=periods)

    trend_col1, trend_col2 = st.columns(2)
    with trend_col1:
        st.caption(f"New signups per {period_label}")
        fig_signups = px.area(signup_trend, x="period", y="count", markers=True)
        fig_signups.update_traces(line_color="#E50914", fillcolor="rgba(229,9,20,0.18)")
        st.plotly_chart(fig_signups, use_container_width=True)

    with trend_col2:
        st.caption(f"Recommendation requests per {period_label}")
        fig_recs = px.area(rec_trend, x="period", y="count", markers=True)
        fig_recs.update_traces(line_color="#2ecc71", fillcolor="rgba(46,204,113,0.18)")
        st.plotly_chart(fig_recs, use_container_width=True)

st.divider()

# =====================================================
# Module 5 — Recommendation acceptance & movie popularity
# =====================================================
st.markdown('<div class="nf-section-title">🎯 Recommendation Acceptance &amp; Movie Popularity</div>', unsafe_allow_html=True)

with st.container(border=True, key="nf_panel_acceptance"):
    acceptance = get_recommendation_acceptance_rate()
    acc_col1, acc_col2, acc_col3 = st.columns(3)
    acc_col1.metric("Movies Recommended", acceptance["total_recommended"])
    acc_col2.metric("Acted On (fav/rated/trailer)", acceptance["accepted"])
    acc_col3.metric("Acceptance Rate", f"{acceptance['acceptance_rate_pct']}%")
    st.caption(
        "A recommendation counts as \"acted on\" if the user favorited it, rated it, "
        "or watched its trailer — a simple, honest proxy for \"did they like what we suggested.\""
    )

    popularity_df = get_movie_popularity(limit=10)
    if popularity_df.empty:
        st.info("No movie interactions recorded yet.")
    else:
        fig_pop = px.bar(
            popularity_df.sort_values("total"),
            x="total", y="movie_title", orientation="h",
            hover_data=["recommended", "favorited", "trailer", "rated"],
            labels={"total": "Total interactions", "movie_title": "Movie"},
            title="Most-engaged-with movies platform-wide",
        )
        st.plotly_chart(fig_pop, use_container_width=True)

st.divider()

# =====================================================
# Module 5 — Live activity feed
# =====================================================
st.markdown('<div class="nf-section-title">🔴 Live Activity Feed</div>', unsafe_allow_html=True)

with st.container(border=True, key="nf_panel_activity_feed"):
    if st.button("🔄 Refresh feed"):
        st.rerun()

    feed = get_recent_activity_feed(limit=25)
    if not feed:
        st.info("No activity recorded yet.")
    else:
        for event in feed:
            st.markdown(
                f"{event['icon']} **{event['username']}** {event['text']} "
                f"&nbsp;·&nbsp; <span style='color:var(--nf-text-muted);font-size:0.82rem'>{event['timestamp']}</span>",
                unsafe_allow_html=True,
            )

st.divider()

# =====================================================
# SHAP explanation — why the model flags high-risk users
# =====================================================
st.subheader("🔍 SHAP: What's driving churn risk")

try:
    import shap

    bundle = _load_bundle()
    model = bundle["model"]
    feature_columns = bundle["feature_columns"]

    X_all = pd.concat(
        [build_feature_row(row.to_dict())[feature_columns] for _, row in df.iterrows()],
        ignore_index=True,
    )

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_all)
    # LGBMClassifier binary output: shap_values may be a list [class0, class1] or a single array
    sv = shap_values[1] if isinstance(shap_values, list) else shap_values

    mean_abs_shap = np.abs(sv).mean(axis=0)
    importance_df = pd.DataFrame({
        "feature": feature_columns,
        "mean_abs_shap": mean_abs_shap,
    }).sort_values("mean_abs_shap", ascending=False).head(10)

    fig_shap = px.bar(
        importance_df, x="mean_abs_shap", y="feature", orientation="h",
        title="Top features driving churn predictions (mean |SHAP value|)"
    )
    fig_shap.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_shap, use_container_width=True)

except ImportError:
    st.info("Install `shap` (see requirements.txt) to see feature-importance explanations.")
except Exception as e:
    st.warning(f"Could not compute SHAP explanation: {e}")

st.divider()

# =====================================================
# Per-user SHAP explanation — real-time, on demand
# =====================================================
st.subheader("🔎 Explain a single user's churn risk")
st.caption("Real-time — recomputed from that user's current activity row, not a cached batch result.")

user_ids_available = df["user_id"].tolist() if "user_id" in df.columns else []
if not user_ids_available:
    st.info("No users to explain yet.")
else:
    selected_uid = st.selectbox("Pick a user_id", sorted(user_ids_available))
    selected_row = df[df["user_id"] == selected_uid].iloc[0]

    st.metric(
        f"Churn probability — user {selected_uid}",
        f"{selected_row['churn_probability']:.1%}",
        help=selected_row["risk_label"],
    )

    try:
        import shap

        bundle = _load_bundle()
        model = bundle["model"]
        feature_columns = bundle["feature_columns"]

        X_one = build_feature_row(selected_row.to_dict())[feature_columns]

        explainer = shap.TreeExplainer(model)
        shap_values_one = explainer.shap_values(X_one)
        sv_one = (
            shap_values_one[1][0] if isinstance(shap_values_one, list)
            else shap_values_one[0]
        )

        contrib_df = pd.DataFrame({
            "feature": feature_columns,
            "value": X_one.iloc[0].values,
            "shap_contribution": sv_one,
        })
        # Sort by absolute impact so the biggest drivers (either direction) surface first.
        contrib_df["abs_contribution"] = contrib_df["shap_contribution"].abs()
        contrib_df = contrib_df.sort_values("abs_contribution", ascending=False).head(8)

        fig_one = px.bar(
            contrib_df.sort_values("shap_contribution"),
            x="shap_contribution", y="feature", orientation="h",
            color="shap_contribution",
            color_continuous_scale=["#2ecc71", "#e74c3c"],
            title=f"What's pushing user {selected_uid}'s risk up (red) or down (green)",
        )
        st.plotly_chart(fig_one, use_container_width=True)

        # Plain-language summary of the top 3 drivers.
        top3 = contrib_df.head(3)
        bullet_lines = []
        for _, r in top3.iterrows():
            direction = "increases" if r["shap_contribution"] > 0 else "decreases"
            bullet_lines.append(f"- **{r['feature']}** = {r['value']:.2f} → {direction} churn risk")
        st.markdown("**Top factors:**\n" + "\n".join(bullet_lines))

    except ImportError:
        st.info("Install `shap` (see requirements.txt) to see per-user explanations.")
    except Exception as e:
        st.warning(f"Could not compute per-user SHAP explanation: {e}")

st.divider()

# =====================================================
# User tables
# =====================================================
display_cols = [
    "user_id", "churn_probability", "risk_label", "login_frequency",
    "session_duration", "days_since_last_login", "satisfaction_score",
    "preferred_genre",
]
display_cols = [c for c in display_cols if c in df.columns]

st.subheader("⚠️ High-Risk Users")
high_risk_df = df[df["churn_probability"] >= 0.7].sort_values("churn_probability", ascending=False)
if high_risk_df.empty:
    st.success("No users currently flagged as high risk.")
else:
    st.dataframe(high_risk_df[display_cols].style.format({"churn_probability": "{:.1%}"}), use_container_width=True)

st.subheader("✅ Low-Risk Users")
low_risk_df = df[df["churn_probability"] < 0.4].sort_values("churn_probability")
if low_risk_df.empty:
    st.info("No users currently flagged as low risk.")
else:
    st.dataframe(low_risk_df[display_cols].style.format({"churn_probability": "{:.1%}"}), use_container_width=True)

st.subheader("All Users")
st.dataframe(
    df[display_cols].sort_values("churn_probability", ascending=False)
      .style.format({"churn_probability": "{:.1%}"}),
    use_container_width=True
)