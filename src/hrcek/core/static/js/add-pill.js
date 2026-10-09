// The dashed "+ Label" and "+ Collection" pills on the entries list
// (details.add-pill): Escape inside an open one closes it and returns
// focus to its own summary. <details> already closes on a click on the
// summary itself (its own native behaviour, same element the CSS in
// static_src/hrcek.css relabels "Cancel" while open); this is the one
// thing it does not do by itself. One delegated listener on document,
// so a fragment swapped in later works without re-binding. See
// docs/dev/javascript.md.
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const details = event.target.closest("details.add-pill[open]");
  if (!details) return;
  details.open = false;
  details.querySelector("summary")?.focus();
});
