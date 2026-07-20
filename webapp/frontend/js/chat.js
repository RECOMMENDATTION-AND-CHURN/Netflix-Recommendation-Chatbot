/* webapp/frontend/js/chat.js — the ChatGPT-style chat experience. */

let CURRENT_USER = null;
let LAST_MOVIES = [];
let LAST_MOVIE_PREFS_NOTE = null;

const messagesEl = () => document.getElementById("chat-messages");
const resultsEl = () => document.getElementById("movie-results");

function formatTime(ts) {
  if (!ts) return "";
  // ts looks like "YYYY-MM-DD HH:MM:SS" — show HH:MM
  const match = ts.match(/(\d{2}):(\d{2})(:\d{2})?$/);
  return match ? `${match[1]}:${match[2]}` : ts;
}

/** Very small, safe markdown-ish renderer: escapes HTML first, then adds
 * bold/italic/inline-code/line breaks. No raw HTML from the model or user
 * is ever injected unescaped. */
function renderMarkdownLite(text) {
  let html = escapeHtml(text);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  html = html.replace(/\n/g, "<br>");
  return html;
}

function scrollToBottom() {
  const el = messagesEl();
  el.scrollTop = el.scrollHeight;
}

function appendMessageRow(role, content, timestamp, { isLast = false, animate = false } = {}) {
  const row = document.createElement("div");
  row.className = `msg-row ${role}`;
  row.dataset.role = role;
  row.dataset.raw = content;

  const avatar = role === "assistant" ? "🎬" : "🧑";
  row.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div>
      <div class="msg-bubble" data-bubble></div>
      <div class="msg-meta"><span>${formatTime(timestamp)}</span></div>
      <div class="msg-actions" data-actions></div>
    </div>
  `;
  messagesEl().appendChild(row);

  const bubble = row.querySelector("[data-bubble]");
  if (animate) {
    typeIntoBubble(bubble, content);
  } else {
    bubble.innerHTML = renderMarkdownLite(content);
  }

  if (isLast && role === "user") {
    row.querySelector("[data-actions]").innerHTML =
      `<button data-action="edit">✏️ Edit</button>`;
  }
  if (isLast && role === "assistant") {
    row.querySelector("[data-actions]").innerHTML =
      `<button data-action="regenerate">🔄 Regenerate</button>`;
  }

  scrollToBottom();
  return row;
}

function typeIntoBubble(bubble, text, speed = 12) {
  let i = 0;
  const full = renderMarkdownLite(text);
  // Type raw text then swap to rendered markdown at the end, to keep it simple/safe.
  const plain = text;
  const timer = setInterval(() => {
    i += 3;
    bubble.textContent = plain.slice(0, i);
    scrollToBottom();
    if (i >= plain.length) {
      clearInterval(timer);
      bubble.innerHTML = full;
    }
  }, speed);
}

function clearLastMessageActions() {
  document.querySelectorAll(".msg-actions").forEach((el) => (el.innerHTML = ""));
}

function showTypingIndicator() {
  const row = document.createElement("div");
  row.className = "msg-row assistant";
  row.id = "typing-indicator";
  row.innerHTML = `
    <div class="msg-avatar">🎬</div>
    <div class="msg-bubble"><span class="typing-dots"><span></span><span></span><span></span></span></div>
  `;
  messagesEl().appendChild(row);
  scrollToBottom();
}

function hideTypingIndicator() {
  document.getElementById("typing-indicator")?.remove();
}

function starHtml(rating) {
  const n = Math.max(0, Math.min(5, Math.round((rating || 0) / 2)));
  return "⭐".repeat(n) + "☆".repeat(5 - n);
}

function renderMovies(movies) {
  const container = resultsEl();
  if (!movies || !movies.length) {
    container.innerHTML = "";
    return;
  }
  LAST_MOVIES = movies;

  const cards = movies
    .map((m, idx) => {
      const poster = m.poster
        ? `<img src="${m.poster}" class="movie-poster" loading="lazy" alt="${escapeHtml(m.title)} poster">`
        : `<div class="movie-poster-placeholder">🎬 No Poster</div>`;
      const reasons = (m.reasons || []).map((r) => `<li>✔ ${escapeHtml(r)}</li>`).join("");
      const ratingOptions = [0, 1, 2, 3, 4, 5]
        .map((v) => `<option value="${v}" ${v === (m.userRating || 0) ? "selected" : ""}>${v === 0 ? "Rate" : v}</option>`)
        .join("");

      return `
      <div class="movie-card glass" data-idx="${idx}">
        ${poster}
        <div class="movie-title">${escapeHtml(m.title)}</div>
        <div class="movie-meta">${starHtml(m.rating)} <span class="badge">⭐ ${m.rating ?? "-"}</span> <span class="badge">🕒 ${m.runtime ?? "?"} min</span></div>
        <div class="movie-meta">${escapeHtml(m.genre)}</div>
        <div class="movie-meta">🎬 ${escapeHtml(m.director)}</div>
        <div class="movie-overview">${escapeHtml(m.overview || "")}</div>
        <div class="reasons"><b>Why recommended</b><ul>${reasons}</ul></div>
        <div class="card-actions">
          <button class="btn btn-ghost btn-sm" data-action="favorite" ${m.isFavorited ? "disabled" : ""}>
            ${m.isFavorited ? "✅ Favorited" : "👍 Save"}
          </button>
          ${m.trailer ? `<button class="btn btn-ghost btn-sm" data-action="trailer">▶ Trailer</button>` : ""}
          <select class="rating-select" data-action="rate">${ratingOptions}</select>
        </div>
      </div>`;
    })
    .join("");

  container.innerHTML = `<div class="movie-grid">${cards}</div>`;

  container.querySelectorAll(".movie-card").forEach((card) => {
    const idx = Number(card.dataset.idx);
    const movie = movies[idx];

    card.querySelector('[data-action="favorite"]')?.addEventListener("click", async (e) => {
      const res = await Api.post("/api/favorites", { movie_title: movie.title, genre: movie.genre });
      if (res.ok) {
        e.target.disabled = true;
        e.target.textContent = "✅ Favorited";
        showToast(`Added ${movie.title} to favorites!`, "success");
      } else {
        showToast(res.error || "Could not save favorite.", "error");
      }
    });

    card.querySelector('[data-action="trailer"]')?.addEventListener("click", async () => {
      await Api.post("/api/trailer-click", { movie_title: movie.title });
      window.open(movie.trailer, "_blank", "noopener");
    });

    card.querySelector('[data-action="rate"]')?.addEventListener("change", async (e) => {
      const rating = Number(e.target.value);
      if (!rating) return;
      const res = await Api.post("/api/ratings", { movie_title: movie.title, rating });
      if (res.ok) showToast(`Rated ${movie.title} ${rating}★`, "success");
      else showToast(res.error || "Could not save rating.", "error");
    });
  });
}

async function loadHistory() {
  const res = await Api.get("/api/chat/history");
  if (!res.ok) {
    showToast("Could not load chat history.", "error");
    return;
  }
  messagesEl().innerHTML = "";
  const msgs = res.messages;
  msgs.forEach((m, i) => {
    appendMessageRow(m.role, m.content, m.timestamp, { isLast: i === msgs.length - 1 });
  });
}

function handleTurnResult(result) {
  hideTypingIndicator();
  clearLastMessageActions();
  const msgs = result.messages || [];
  msgs.forEach((m, i) => {
    appendMessageRow(m.role, m.content, new Date().toISOString().slice(0, 19).replace("T", " "), {
      isLast: i === msgs.length - 1,
      animate: true,
    });
  });
  renderMovies(result.movies);
}

async function sendMessage(text) {
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("send-btn");

  clearLastMessageActions();
  appendMessageRow("user", text, new Date().toISOString().slice(0, 19).replace("T", " "), { isLast: true });
  input.value = "";
  input.style.height = "auto";
  sendBtn.disabled = true;
  showTypingIndicator();

  const res = await Api.post("/api/chat/send", { message: text });
  if (!res.ok) {
    hideTypingIndicator();
    showToast(res.error || "Something went wrong.", "error");
    sendBtn.disabled = false;
    return;
  }
  handleTurnResult(res);
  sendBtn.disabled = false;
  input.focus();
}

async function regenerate() {
  showTypingIndicator();
  // Remove the last assistant bubble from the UI immediately for a snappy feel.
  const rows = messagesEl().querySelectorAll(".msg-row");
  const last = rows[rows.length - 1];
  if (last && last.dataset.role === "assistant") last.remove();

  const res = await Api.post("/api/chat/regenerate", {});
  if (!res.ok) {
    hideTypingIndicator();
    showToast(res.error || "Could not regenerate.", "error");
    return;
  }
  handleTurnResult(res);
}

async function editLastMessage(row) {
  const original = row.dataset.raw;
  const bubble = row.querySelector("[data-bubble]");
  const textarea = document.createElement("textarea");
  textarea.value = original;
  textarea.style.cssText = "width:100%;min-height:60px;background:rgba(0,0,0,0.25);color:#fff;border:1px solid var(--nf-border);border-radius:8px;padding:8px;";
  bubble.replaceWith(textarea);
  textarea.focus();

  const actions = row.querySelector("[data-actions]");
  actions.innerHTML = `<button data-action="save-edit">💾 Save & resend</button> <button data-action="cancel-edit">✖ Cancel</button>`;

  actions.querySelector('[data-action="cancel-edit"]').addEventListener("click", () => loadHistory());
  actions.querySelector('[data-action="save-edit"]').addEventListener("click", async () => {
    const newText = textarea.value.trim();
    if (!newText) return;
    showTypingIndicator();
    const res = await Api.post("/api/chat/edit-last-user-message", { message: newText });
    if (!res.ok) {
      hideTypingIndicator();
      showToast(res.error || "Could not edit message.", "error");
      return;
    }
    await loadHistory();
    handleTurnResult(res);
  });
}

function wireInput() {
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("send-btn");

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 140) + "px";
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const text = input.value.trim();
      if (text) sendMessage(text);
    }
  });

  sendBtn.addEventListener("click", () => {
    const text = input.value.trim();
    if (text) sendMessage(text);
  });

  messagesEl().addEventListener("click", (e) => {
    const action = e.target.dataset.action;
    if (action === "regenerate") regenerate();
    if (action === "edit") editLastMessage(e.target.closest(".msg-row"));
  });

  document.getElementById("clear-chat-btn").addEventListener("click", async () => {
    if (!confirm("Clear the entire conversation? This cannot be undone.")) return;
    const res = await Api.post("/api/chat/clear", {});
    if (res.ok) {
      messagesEl().innerHTML = "";
      resultsEl().innerHTML = "";
      showToast("Chat cleared.", "info");
    } else {
      showToast(res.error || "Could not clear chat.", "error");
    }
  });
}

(async () => {
  CURRENT_USER = await requireAuth();
  if (!CURRENT_USER) return;

  renderSidebar("chat", CURRENT_USER);
  document.getElementById("hero-sub").textContent =
    `Welcome back, ${CURRENT_USER.username[0].toUpperCase()}${CURRENT_USER.username.slice(1)}! Tell me your mood, language, or genre.`;

  wireInput();
  await loadHistory();

  document.getElementById("page-loader").style.display = "none";
  document.getElementById("app-shell").style.display = "flex";
})();
