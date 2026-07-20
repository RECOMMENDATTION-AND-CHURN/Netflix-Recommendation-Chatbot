/* webapp/frontend/js/settings.js */

const PREF_KEY = "netflix_ui_prefs";

function loadUiPrefs() {
  try {
    return JSON.parse(localStorage.getItem(PREF_KEY)) || {};
  } catch (_e) {
    return {};
  }
}

function saveUiPrefs(prefs) {
  localStorage.setItem(PREF_KEY, JSON.stringify(prefs));
}

function wireToggles() {
  const prefs = loadUiPrefs();
  const compact = document.getElementById("toggle-compact");
  const sound = document.getElementById("toggle-sound");
  const autoscroll = document.getElementById("toggle-autoscroll");

  compact.checked = !!prefs.compact;
  sound.checked = !!prefs.sound;
  autoscroll.checked = prefs.autoscroll !== false;

  [compact, sound, autoscroll].forEach((el) =>
    el.addEventListener("change", () => {
      saveUiPrefs({
        compact: compact.checked,
        sound: sound.checked,
        autoscroll: autoscroll.checked,
      });
      showToast("Preference saved.", "success", 1500);
    })
  );
}

function wirePasswordForm() {
  const form = document.getElementById("password-form");
  const errorEl = document.getElementById("password-error");
  const submitBtn = document.getElementById("password-submit");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.textContent = "";
    submitBtn.disabled = true;

    const res = await Api.post("/api/settings/password", {
      current_password: document.getElementById("current-password").value,
      new_password: document.getElementById("new-password").value,
      confirm_password: document.getElementById("confirm-password").value,
    });

    submitBtn.disabled = false;
    if (res.ok) {
      showToast("Password updated.", "success");
      form.reset();
    } else {
      errorEl.textContent = res.error || "Could not update password.";
    }
  });
}

function wireFeedback() {
  document.getElementById("feedback-submit").addEventListener("click", async () => {
    const satisfaction = Number(document.getElementById("satisfaction").value);
    const comment = document.getElementById("comment").value;
    const res = await Api.post("/api/feedback", { satisfaction, comment });
    if (res.ok) {
      showToast("Thanks for the feedback!", "success");
      document.getElementById("comment").value = "";
    } else {
      showToast(res.error || "Could not submit feedback.", "error");
    }
  });
}

(async () => {
  const user = await requireAuth();
  if (!user) return;

  renderSidebar("settings", user);
  wireToggles();
  wirePasswordForm();
  wireFeedback();

  document.getElementById("page-loader").style.display = "none";
  document.getElementById("app-shell").style.display = "flex";
})();
