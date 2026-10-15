// Run before stylesheets so a saved preference applies before the first paint.
(() => {
  const key = "serve-html.theme.v1";
  const root = document.documentElement;
  let theme = "light";
  try {
    const saved = localStorage.getItem(key);
    if (saved === "light" || saved === "dark") theme = saved;
  } catch { /* Storage policy must not prevent reading or toggling. */ }

  function updateControl() {
    const button = document.getElementById("theme-toggle");
    if (!button) return;
    button.setAttribute("aria-pressed", String(theme === "dark"));
    button.hidden = false;
  }

  function apply() {
    root.dataset.theme = theme;
    document.querySelector('meta[name="color-scheme"]').content = theme;
    updateControl();
  }
  apply();
  document.addEventListener("readystatechange", updateControl);
  document.addEventListener("click", (event) => {
    const button = document.getElementById("theme-toggle");
    if (!button || !button.contains(event.target)) return;
    theme = theme === "dark" ? "light" : "dark";
    apply();
    try { localStorage.setItem(key, theme); } catch { /* Current-page state still works. */ }
    document.dispatchEvent(new CustomEvent("serve-html-themechange"));
  });
})();
