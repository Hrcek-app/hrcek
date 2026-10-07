// After an hx-swap="delete" removes a row, focus lands somewhere the
// browser happens to pick rather than nowhere useful. This moves it to
// a sensible neighbour instead: the row's own next [data-focus-after-delete],
// its previous one, or a page-wide fallback, computed on
// htmx:before:swap while the row (and its siblings) are still in the
// document, then applied on htmx:after:swap once it is gone. See
// docs/dev/javascript.md.
let focusAfterDelete = null;

document.addEventListener("htmx:before:swap", (event) => {
  const main = event.detail.tasks?.find((task) => task.type === "main");
  if (main?.swapSpec?.style !== "delete") return;
  const removed = main.target;
  focusAfterDelete =
    removed.nextElementSibling?.querySelector("[data-focus-after-delete]") ??
    removed.previousElementSibling?.querySelector("[data-focus-after-delete]") ??
    document.querySelector("[data-focus-after-delete-fallback]");
});

document.addEventListener("htmx:after:swap", () => {
  focusAfterDelete?.focus();
  focusAfterDelete = null;
});
