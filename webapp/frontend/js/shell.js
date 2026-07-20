/* webapp/frontend/js/shell.js — shared sidebar + auth guard for logged-in pages. */

async function requireAuth() {
  const res = await Api.get("/api/auth/me");
  if (!res.authenticated) {
    window.location.href = "/login.html";
    return null;
  }
  return res.user;
}

function renderSidebar(activePage, user) {
  const initial = (user.username || "?").slice(0, 1).toUpperCase();
  const nav = [
    { href: "/chat.html", icon: "\u{1F4AC}", label: "Chat", key: "chat" },
    { href: "/profile.html", icon: "\u{1F464}", label: "Profile", key: "profile" },
    { href: "/settings.html", icon: "\u2699\uFE0F", label: "Settings", key: "settings" },
  ];

  const navHtml = nav
    .map(
      (n) => `<a class="nav-link${n.key === activePage ? " active" : ""}" href="${n.href}">
        <span>${n.icon}</span><span>${n.label}</span>
      </a>`
    )
    .join("");

  document.getElementById("sidebar-root").innerHTML = `
    <button class="btn btn-ghost btn-icon sidebar-toggle" id="sidebar-toggle-btn" aria-label="Toggle menu">\u2630</button>
    <aside class="sidebar glass" id="sidebar">
      <div class="sidebar-brand"><span class="logo-emoji">\u{1F3AC}</span> Netflix</div>
      <nav>${navHtml}</nav>
      <div class="sidebar-footer">
        <div class="user-chip">
          <div class="avatar-circle">${initial}</div>
          <div>${user.username}</div>
        </div>
        <button class="btn btn-ghost btn-block" id="logout-btn">\u{1F6AA} Log Out</button>
      </div>
    </aside>
  `;

  document.getElementById("sidebar-toggle-btn").addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("open");
  });

  document.getElementById("logout-btn").addEventListener("click", async () => {
    await Api.post("/api/auth/logout");
    window.location.href = "/login.html";
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}
