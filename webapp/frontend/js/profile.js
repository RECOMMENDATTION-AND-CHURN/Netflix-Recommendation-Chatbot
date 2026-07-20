/* webapp/frontend/js/profile.js */

function renderStatGrid(data) {
  const stats = [
    { label: "Favorites", value: data.favorites.length },
    { label: "Ratings Given", value: data.ratings.length },
    { label: "Average Rating", value: data.averageRating ? `${data.averageRating}★` : "—" },
  ];
  document.getElementById("stat-grid").innerHTML = stats
    .map((s) => `<div class="stat-card glass"><div class="stat-value">${s.value}</div><div class="stat-label">${s.label}</div></div>`)
    .join("");
}

function renderPreferences(prefs) {
  const labels = {
    genre: "🎭 Genre",
    language: "🌐 Language",
    mood: "🙂 Mood",
    audience: "👥 Audience",
    watch_time: "🕒 Watch time",
    movie_name: "🎬 Reference movie",
  };
  const rows = Object.entries(labels)
    .filter(([key]) => prefs[key])
    .map(([key, label]) => `<div class="list-row"><span>${label}</span><span>${escapeHtml(String(prefs[key]))}</span></div>`)
    .join("");
  document.getElementById("preferences-list").innerHTML =
    rows || `<div class="empty-state">No preferences learned yet — start chatting to build your taste profile.</div>`;
}

function renderFavorites(favorites) {
  const rows = favorites
    .map((f) => `<div class="list-row"><span>🎬 ${escapeHtml(f.movie_title)}</span><span>${escapeHtml(f.genre || "")}</span></div>`)
    .join("");
  document.getElementById("favorites-list").innerHTML =
    rows || `<div class="empty-state">No favorites saved yet. Save movies from the chat page!</div>`;
}

function renderRatings(ratings) {
  const rows = ratings
    .map((r) => `<div class="list-row"><span>🎬 ${escapeHtml(r.movie_title)}</span><span>${"⭐".repeat(r.rating)}</span></div>`)
    .join("");
  document.getElementById("ratings-list").innerHTML =
    rows || `<div class="empty-state">You haven't rated any movies yet.</div>`;
}

(async () => {
  const user = await requireAuth();
  if (!user) return;

  renderSidebar("profile", user);

  const res = await Api.get("/api/profile");
  if (!res.ok) {
    showToast("Could not load profile.", "error");
    return;
  }

  renderStatGrid(res);
  renderPreferences(res.preferences);
  renderFavorites(res.favorites);
  renderRatings(res.ratings);

  document.getElementById("page-loader").style.display = "none";
  document.getElementById("app-shell").style.display = "flex";
})();
