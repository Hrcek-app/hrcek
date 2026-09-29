// The light/dark toggle in the page header. See docs/dev/styling.md.
//
// Two states only: follow the system, or pin the opposite of what the
// system shows. Pressing the button always flips what you see. If the
// flip lands on the system's own theme, the pin is dropped rather than
// stored, so there is always a way back to following the system.
//
// A pin is never removed behind somebody's back: if the system later
// changes to match it, it stays until the button is pressed again.
//
// The inline script in base.html applies a stored pin before the first
// paint; this file only wires up the button.
(() => {
  const KEY = "hrcek-theme";
  const root = document.documentElement;
  const meta = document.querySelector('meta[name="color-scheme"]');
  const system = window.matchMedia("(prefers-color-scheme: dark)");
  const button = document.querySelector("button.theme-toggle");
  if (!button) return;

  const systemTheme = () => (system.matches ? "dark" : "light");
  const shown = () => root.dataset.theme || systemTheme();

  const render = () => {
    button.setAttribute("aria-pressed", String(shown() === "dark"));
  };

  const apply = (pin) => {
    if (pin === "light" || pin === "dark") {
      root.dataset.theme = pin;
      meta.content = pin;
    } else {
      delete root.dataset.theme;
      meta.content = "light dark";
    }
    render();
  };

  button.addEventListener("click", () => {
    const next = shown() === "dark" ? "light" : "dark";
    const pin = next === systemTheme() ? null : next;
    try {
      if (pin) localStorage.setItem(KEY, pin);
      else localStorage.removeItem(KEY);
    } catch {
      // Storage refused (private mode, blocked site data): the choice
      // still holds for this page, it just is not remembered.
    }
    apply(pin);
  });

  // The system theme can change while the page is open; so can the pin,
  // from another tab.
  system.addEventListener("change", render);
  window.addEventListener("storage", (event) => {
    if (event.key === KEY) apply(event.newValue);
  });

  render();
  button.hidden = false;
})();
