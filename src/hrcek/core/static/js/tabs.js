// Turns [data-tabs] > section[id] into an ARIA tab set. Without this
// script the sections simply stack. See docs/dev/javascript.md.
for (const root of document.querySelectorAll("[data-tabs]")) {
  const sections = [...root.querySelectorAll(":scope > section[id]")];
  if (sections.length < 2) continue;
  const list = document.createElement("div");
  list.setAttribute("role", "tablist");
  if (root.dataset.tabsLabel) list.setAttribute("aria-label", root.dataset.tabsLabel);
  const tabs = sections.map((section) => {
    const heading = section.querySelector("h2");
    const tab = document.createElement("button");
    tab.type = "button";
    tab.id = `${section.id}-tab`;
    tab.textContent = heading.textContent;
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-controls", section.id);
    section.setAttribute("role", "tabpanel");
    section.setAttribute("aria-labelledby", tab.id);
    section.tabIndex = 0;
    heading.classList.add("sr-only");
    list.append(tab);
    return tab;
  });
  root.prepend(list);
  // Tells the stylesheet the sections are tabs now, so the hairline
  // that separates them when stacked goes (one line under the tabs).
  root.classList.add("tabbed");
  // updateHash is false only for the very first selection: calling
  // replaceState there, before the browser's own scroll-to-fragment
  // step has run, is what used to land a plain visit scrolled past
  // the heading. A later switch (click or arrow key) still updates
  // the hash, with no new history entry.
  const select = (index, focus, updateHash = true) => {
    tabs.forEach((tab, i) => {
      const on = i === index;
      tab.setAttribute("aria-selected", String(on));
      tab.tabIndex = on ? 0 : -1;
      sections[i].hidden = !on;
    });
    if (focus) tabs[index].focus();
    if (updateHash) history.replaceState(null, "", `#${sections[index].id}`);
  };
  list.addEventListener("click", (event) => {
    const index = tabs.indexOf(event.target.closest("[role=tab]"));
    if (index >= 0) select(index, false);
  });
  list.addEventListener("keydown", (event) => {
    const current = tabs.indexOf(document.activeElement);
    const last = tabs.length - 1;
    const next = { ArrowRight: current + 1, ArrowLeft: current - 1, Home: 0, End: last }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    select((next + tabs.length) % tabs.length, true);
  });
  // Precedence for the tab open at load: a section a server-side error
  // marked data-open, else the one named by the page's #hash, else the
  // first.
  const opened = sections.findIndex((s) => s.dataset.open !== undefined);
  const hashed = sections.findIndex((s) => `#${s.id}` === location.hash);
  const initial = opened >= 0 ? opened : hashed >= 0 ? hashed : 0;
  select(initial, false, false);
}
