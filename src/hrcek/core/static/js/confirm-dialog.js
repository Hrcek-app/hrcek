// A link marked data-confirm-dialog="ID" opens the <dialog> with that
// id instead of navigating; without this script the link simply goes
// to the confirmation page. See docs/dev/javascript.md.
document.addEventListener("click", (event) => {
  const cancel = event.target.closest("dialog [data-dialog-cancel]");
  if (cancel) {
    event.preventDefault();
    cancel.closest("dialog").close();
    return;
  }
  const link = event.target.closest("a[data-confirm-dialog]");
  if (!link) return;
  const dialog = document.getElementById(link.dataset.confirmDialog);
  if (!dialog || typeof dialog.showModal !== "function") return;
  event.preventDefault();
  dialog.showModal();
  dialog.addEventListener("close", () => link.focus(), { once: true });
});
