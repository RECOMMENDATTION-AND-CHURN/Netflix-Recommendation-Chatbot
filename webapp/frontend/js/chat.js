/* webapp/frontend/js/chat.js — the ChatGPT-style chat experience. */

let CURRENT_USER = null;
let LAST_MOVIES = [];

const QUICK_PROMPTS = [
  "Something dark and funny",
  "Feel-good Sunday movie",
  "Best Korean thrillers",
  "Movies like Inception",
];

const messagesEl = () => document.getElementById("chat-messages");

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

function renderQuickPrompts() {
  const el = document.getElementById("quick-prompts");
  if (!el) return;
  el.innerHTML = QUICK_PROMPTS
    .map((p) => `<button class="quick-prompt-chip" data-prompt="${escapeHtml(p)}">${escapeHtml(p)}</button>`)
    .join("");
  el.querySelectorAll(".quick-prompt-chip").forEach((btn) => {
    btn.addEventListener("click", () => sendMessage(btn.dataset.prompt));
  });
}

function appendMessageRow(role, content, timestamp, { isLast = false, animate = false } = {}) {
  const row = document.createElement("div");
  row.className = `msg-row ${role}`;
  row.dataset.role = role;
  row.dataset.raw = content;

  const avatarIcon = role === "assistant" ? "clapperboard" : "user";
  row.innerHTML = `
    <div class="msg-avatar"><i data-lucide="${avatarIcon}"></i></div>
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
      `<button data-action="edit"><i data-lucide="pencil"></i> Edit</button>`;
  }
  if (isLast && role === "assistant") {
    row.querySelector("[data-actions]").innerHTML =
      `<button data-action="regenerate"><i data-lucide="refresh-cw"></i> Regenerate</button>`;
  }

  lucide.createIcons();
  scrollToBottom();
  return row;
}

function typeIntoBubble(bubble, text, speed = 12) {
  let i = 0;
  const full = renderMarkdownLite(text);
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
    <div class="msg-avatar"><i data-lucide="clapperboard"></i></div>
    <div class="msg-bubble"><span class="typing-dots"><span></span><span></span><span></span></span></div>
  `;
  messagesEl().appendChild(row);
  lucide.createIcons();
  scrollToBottom();
}

function hideTypingIndicator() {
  document.getElementById("typing-indicator")?.remove();
}

/** Renders a compact horizontal-scroll row of movie cards INSIDE the given
 * assistant message row, so recommendations travel with the message they
 * belong to instead of floating in a separate panel below the chat. */
function renderMoviesInRow(row, movies) {
  if (!row || !movies || !movies.length) return;
  LAST_MOVIES = movies;

  const cards = movies
    .map((m, idx) => {
      const poster = m.poster
        ? `<img src="${m.poster}" class="movie-poster" loading="lazy" alt="${escapeHtml(m.title)} poster">`
        : `<div class="movie-poster-placeholder"><i data-lucide="film"></i></div>`;
      const genres = String(m.genre || "")
        .split(",")
        .map((g) => g.trim())
        .filter(Boolean)
        .slice(0, 3);
      const genreChips = genres.map((g) => `<span class="genre-chip">${escapeHtml(g)}</span>`).join("");
      const ratingOptions = [0, 1, 2, 3, 4, 5]
        .map((v) => `<option value="${v}" ${v === (m.userRating || 0) ? "selected" : ""}>${v === 0 ? "Rate" : v}</option>`)
        .join("");

      return `
      <div class="movie-card-mini" data-idx="${idx}">
        <div class="movie-poster-wrap">
          ${poster}
          ${m.trailer ? `<button class="poster-play" data-action="trailer" aria-label="Play trailer"><i data-lucide="play"></i></button>` : ""}
        </div>
        <div class="movie-card-body">
          <div class="movie-title" title="${escapeHtml(m.title)}">${escapeHtml(m.title)}</div>
          <div class="movie-meta">
            <span class="badge"><i data-lucide="star"></i>${m.rating ?? "-"}</span>
            <span class="badge"><i data-lucide="clock"></i>${m.runtime ?? "?"}m</span>
          </div>
          ${genreChips ? `<div class="genre-row">${genreChips}</div>` : ""}
          ${m.overview ? `<p class="movie-overview-mini">${escapeHtml(m.overview)}</p>` : ""}
          <div class="card-actions">
            <button class="btn btn-ghost btn-sm" data-action="favorite" ${m.isFavorited ? "disabled" : ""}>
              <i data-lucide="${m.isFavorited ? "bookmark-check" : "bookmark-plus"}"></i>
              ${m.isFavorited ? "Saved" : "Save"}
            </button>
            <select class="rating-select" data-action="rate">${ratingOptions}</select>
          </div>
        </div>
      </div>`;
    })
    .join("");

  const wrap = document.createElement("div");
  wrap.className = "msg-movies";
  wrap.innerHTML = cards;
  row.querySelector("[data-bubble]").insertAdjacentElement("afterend", wrap);

  wrap.querySelectorAll(".movie-card-mini").forEach((card) => {
    const idx = Number(card.dataset.idx);
    const movie = movies[idx];

    card.querySelector('[data-action="favorite"]')?.addEventListener("click", async (e) => {
      const btn = e.target.closest("button");
      const res = await Api.post("/api/favorites", { movie_title: movie.title, genre: movie.genre });
      if (res.ok) {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="bookmark-check"></i> Saved`;
        lucide.createIcons();
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
      if (res.ok) showToast(`Rated ${movie.title} ${rating} stars`, "success");
      else showToast(res.error || "Could not save rating.", "error");
    });
  });

  lucide.createIcons();
  scrollToBottom();
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
  let lastAssistantRow = null;
  msgs.forEach((m, i) => {
    const row = appendMessageRow(m.role, m.content, new Date().toISOString().slice(0, 19).replace("T", " "), {
      isLast: i === msgs.length - 1,
      animate: true,
    });
    if (m.role === "assistant") lastAssistantRow = row;
  });
  if (result.movies && lastAssistantRow) renderMoviesInRow(lastAssistantRow, result.movies);
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
  actions.innerHTML = `<button data-action="save-edit"><i data-lucide="save"></i> Save &amp; resend</button> <button data-action="cancel-edit"><i data-lucide="x"></i> Cancel</button>`;
  lucide.createIcons();

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
    const action = e.target.closest("[data-action]")?.dataset.action;
    if (action === "regenerate") regenerate();
    if (action === "edit") editLastMessage(e.target.closest(".msg-row"));
  });

  document.getElementById("clear-chat-btn").addEventListener("click", async () => {
    if (!confirm("Clear the entire conversation? This cannot be undone.")) return;
    const res = await Api.post("/api/chat/clear", {});
    if (res.ok) {
      messagesEl().innerHTML = "";
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

  renderQuickPrompts();
  wireInput();
  await loadHistory();
  lucide.createIcons();

  document.getElementById("page-loader").style.display = "none";
  document.getElementById("app-shell").style.display = "flex";
})();