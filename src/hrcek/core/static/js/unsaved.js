// Asks before leaving a form whose changes are not saved. See
// docs/dev/styling.md.
//
// A form opts in with data-guard-unsaved. It counts as changed when
// what it would submit differs from what it held when the page loaded,
// so typing something and deleting it again is not a change. A form
// the server sent back with errors carries data-unsaved="true": what
// was typed is on the page but saved nowhere, so it counts as changed
// from the start.
//
// Submitting the form is never interrupted. Any other way off the page
// (a link, reload, closing the tab) gets the browser's own "Leave
// site?" question; browsers do not let a page choose its wording.
(() => {
  const snapshot = (form) =>
    JSON.stringify(
      [...new FormData(form)]
        .filter(([name]) => name !== "csrfmiddlewaretoken")
        .map(([name, value]) => [
          name,
          value instanceof File ? [value.name, value.size] : value,
        ]),
    );

  for (const form of document.querySelectorAll("form[data-guard-unsaved]")) {
    const initial = snapshot(form);
    let submitting = false;

    form.addEventListener("submit", () => {
      submitting = true;
    });

    // Coming back to this page from the browser's cache, after a submit
    // that went elsewhere, starts the watch again.
    window.addEventListener("pageshow", (event) => {
      if (event.persisted) submitting = false;
    });

    window.addEventListener("beforeunload", (event) => {
      if (submitting) return;
      if (form.dataset.unsaved === "true" || snapshot(form) !== initial) {
        event.preventDefault();
        event.returnValue = "";
      }
    });
  }
})();
