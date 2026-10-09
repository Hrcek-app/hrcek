// A failed htmx request says so — visibly, in the page's #messages
// list, and in #status for screen readers — but only when nothing more
// specific already will. A 4xx a control swaps into itself (a
// validation error rendered back into a form, a 422, say) is its own
// feedback: the announcer stays quiet for that one, and acts only when
// htmx will not swap the response at all — a status in htmx's noSwap
// configuration (404 and every 5xx, set once in base.html), a control
// that declared hx-status:… "swap:none" for it (see
// docs/dev/javascript.md), or the request never getting a response
// back at all ("htmx:error": offline, a dropped connection).
const closestWithAttr = (element, attribute) => {
  for (let node = element; node; node = node.parentElement) {
    if (node.hasAttribute?.(attribute)) return node;
  }
  return null;
};

// Mirrors how htmx itself decides: for the exact code, then the
// two-digit wildcard, then the one-digit one, the configured noSwap
// list first and the control's hx-status second; first match wins.
const willNotSwap = (source, status) => {
  const noSwap = (window.htmx?.config?.noSwap ?? []).map(String);
  const code = `${status}`;
  for (const pattern of [code, `${code.slice(0, 2)}x`, `${code[0]}xx`]) {
    if (noSwap.includes(pattern)) return true;
    const attribute = `hx-status:${pattern}`;
    const node = source && closestWithAttr(source, attribute);
    if (node) return /(^|\s)swap:none(\s|$)/.test(node.getAttribute(attribute));
  }
  return false;
};

// The same look as a Django error message: one item in the page's
// messages list, replacing whatever it held, so two failures in a row
// show one error rather than a pile of them.
const showError = (text) => {
  const messages = document.getElementById("messages");
  if (!messages) return;
  const item = document.createElement("li");
  item.className = "error";
  item.textContent = text;
  messages.replaceChildren(item);
};

const sayRequestFailed = () => {
  // The live region is inert, and so unreadable — and unannounced,
  // however its text changes — while a modal dialog is open: close it
  // first, so the write that follows is actually heard, and the page
  // is not left waiting on a request that is not coming back.
  document.querySelector("dialog[open]")?.close();
  const status = document.getElementById("status");
  if (!status) return;
  const text = status.dataset.errorText;
  showError(text);
  // Cleared first: writing the same text twice running would
  // otherwise not register as a change, and go unannounced the second
  // time.
  status.textContent = "";
  status.textContent = text;
};

document.addEventListener("htmx:response:error", (event) => {
  const { ctx } = event.detail;
  if (willNotSwap(ctx.sourceElement, ctx.response?.status)) sayRequestFailed();
});

document.addEventListener("htmx:error", sayRequestFailed);
