// The options of a choice field (entries/_options_editor.html), edited
// in place. Without this script every ↑ ↓ × and Add button submits the
// whole form and the server draws the changed list; with it, the same
// buttons change the list on the page and only Save is sent. Rows can
// also be dragged by their handle; ↑ and ↓ stay the keyboard's way.
//
// The form carries its own wording, translated, in data-label-* and
// data-say-* attributes, with {option}, {position} and {total} filled
// in here. What changed is read out through the page's one status
// region. Delegated listeners on document, as everywhere else. See
// docs/dev/javascript.md.
(() => {
  const EDITOR = "[data-options-editor]";

  const fill = (template, values) =>
    template.replace(/\{(\w+)\}/g, (match, key) =>
      key in values ? String(values[key]) : match,
    );

  const rowsOf = (editor) => [...editor.querySelectorAll("li.option-row")];
  const textOf = (row) => row.querySelector("input[name=option]").value.trim();

  const say = (editor, key, values) => {
    const status = document.getElementById("status");
    if (status) status.textContent = fill(editor.dataset[key], values);
  };

  // Ids, labels, button values and which arrows can be pressed all
  // follow from a row's position and text, so after any change they are
  // simply worked out again.
  const refresh = (editor) => {
    const rows = rowsOf(editor);
    const { labelOption, labelUp, labelDown, labelRemove } = editor.dataset;
    rows.forEach((row, index) => {
      const option = textOf(row);
      const input = row.querySelector("input[name=option]");
      const label = row.querySelector("label");
      input.id = `option-${index}`;
      label.htmlFor = input.id;
      label.textContent = fill(labelOption, { position: index + 1 });
      for (const [action, wording] of [
        ["up", labelUp],
        ["down", labelDown],
        ["remove", labelRemove],
      ]) {
        const button = row.querySelector(`button[value^="${action}:"]`);
        button.value = `${action}:${index}`;
        button.setAttribute("aria-label", fill(wording, { option }));
      }
      row.querySelector('button[value^="up:"]').disabled = index === 0;
      row.querySelector('button[value^="down:"]').disabled =
        index === rows.length - 1;
    });
  };

  const announceMove = (editor, row) => {
    const rows = rowsOf(editor);
    say(editor, "sayMoved", {
      option: textOf(row),
      position: rows.indexOf(row) + 1,
      total: rows.length,
    });
  };

  const move = (editor, row, direction) => {
    const sibling =
      direction === "up" ? row.previousElementSibling : row.nextElementSibling;
    if (!sibling) return;
    if (direction === "up") sibling.before(row);
    else sibling.after(row);
    refresh(editor);
    // Focus stays with the row. At the top or bottom the arrow just
    // pressed is disabled, and a disabled button cannot hold focus.
    const other = direction === "up" ? "down" : "up";
    const pressed = row.querySelector(`button[value^="${direction}:"]`);
    (pressed.disabled
      ? row.querySelector(`button[value^="${other}:"]`)
      : pressed
    ).focus();
    announceMove(editor, row);
  };

  const remove = (editor, row) => {
    const option = textOf(row);
    const next = row.nextElementSibling || row.previousElementSibling;
    row.remove();
    refresh(editor);
    (next
      ? next.querySelector('button[value^="remove:"]')
      : editor.querySelector("input[name=new_option]")
    ).focus();
    say(editor, "sayRemoved", { option });
  };

  const add = (editor) => {
    const input = editor.querySelector("input[name=new_option]");
    const option = input.value.trim();
    if (!option) return;
    const row = editor
      .querySelector("template[data-option-template]")
      .content.querySelector("li")
      .cloneNode(true);
    row.querySelector("input[name=option]").value = option;
    row.querySelector("input[name=original]").value = "";
    row.querySelector(".option-used").textContent = "";
    editor.querySelector(".options-list").append(row);
    refresh(editor);
    input.value = "";
    input.focus();
    say(editor, "sayAdded", { option });
  };

  document.addEventListener("click", (event) => {
    const button = event.target.closest(`${EDITOR} button[name=op]`);
    if (!button) return;
    const [action] = button.value.split(":");
    if (!["up", "down", "remove", "add"].includes(action)) return;
    event.preventDefault();
    const editor = button.closest(EDITOR);
    if (action === "add") add(editor);
    else if (action === "remove") remove(editor, button.closest("li"));
    else move(editor, button.closest("li"), action);
  });

  // Enter in the new option adds it, rather than saving the form.
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    const input = event.target.closest(`${EDITOR} input[name=new_option]`);
    if (!input) return;
    event.preventDefault();
    add(input.closest(EDITOR));
  });

  // A renamed row's buttons are named after its new text.
  document.addEventListener("input", (event) => {
    const input = event.target.closest(`${EDITOR} input[name=option]`);
    if (input) refresh(input.closest(EDITOR));
  });

  // Dragging by the handle. Pointer events cover mouse, pen and touch
  // alike; the row moves among its siblings as the pointer passes their
  // middles.
  let dragging = null;

  document.addEventListener("pointerdown", (event) => {
    const handle = event.target.closest(`${EDITOR} .option-handle`);
    if (!handle || event.button !== 0) return;
    event.preventDefault();
    const row = handle.closest("li");
    dragging = { row, editor: handle.closest(EDITOR) };
    dragging.start = rowsOf(dragging.editor).indexOf(row);
    handle.setPointerCapture(event.pointerId);
    row.classList.add("dragging");
  });

  document.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    const { row, editor } = dragging;
    const others = rowsOf(editor).filter((each) => each !== row);
    const before = others.find((each) => {
      const box = each.getBoundingClientRect();
      return event.clientY < box.top + box.height / 2;
    });
    if (before) {
      if (row.nextElementSibling !== before) before.before(row);
    } else if (others.length && others.at(-1).nextElementSibling !== row) {
      others.at(-1).after(row);
    }
  });

  const drop = () => {
    if (!dragging) return;
    const { row, editor, start } = dragging;
    dragging = null;
    row.classList.remove("dragging");
    refresh(editor);
    if (rowsOf(editor).indexOf(row) !== start) announceMove(editor, row);
  };
  document.addEventListener("pointerup", drop);
  document.addEventListener("pointercancel", drop);
})();
