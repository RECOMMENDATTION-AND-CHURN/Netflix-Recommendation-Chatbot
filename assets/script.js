/* ===================================================================
   script.js — small progressive-enhancement layer for the chatbot UI.
   Injected into the parent Streamlit document via components.html
   (same-origin iframe trick). Everything here is optional polish;
   the app works fully without it.
   =================================================================== */
(function () {
  function run() {
    var doc = window.parent ? window.parent.document : document;
    if (!doc || doc.body.dataset.nfEnhanced) return;
    doc.body.dataset.nfEnhanced = "1";

    // 1) Auto-scroll the main chat area to the latest message whenever
    //    Streamlit re-renders (new message, new movie cards, etc).
    var main = doc.querySelector('section.main') || doc.querySelector('[data-testid="stAppViewContainer"]');
    if (main) {
      var scrollToBottom = function () {
        main.scrollTo({ top: main.scrollHeight, behavior: "smooth" });
      };
      var observer = new MutationObserver(function () {
        clearTimeout(window.__nfScrollTimer);
        window.__nfScrollTimer = setTimeout(scrollToBottom, 120);
      });
      observer.observe(main, { childList: true, subtree: true });
    }

    // 2) Tap-to-expand movie overview text on small screens (nice-to-have).
    doc.addEventListener("click", function (e) {
      var card = e.target.closest && e.target.closest(".nf-movie-card");
      if (card && window.innerWidth <= 768) {
        card.classList.toggle("nf-card-expanded");
      }
    });
  }

  // Streamlit mounts asynchronously — try a few times.
  var attempts = 0;
  var iv = setInterval(function () {
    attempts += 1;
    try { run(); } catch (err) { /* no-op: purely cosmetic */ }
    if (attempts > 20) clearInterval(iv);
  }, 500);
})();