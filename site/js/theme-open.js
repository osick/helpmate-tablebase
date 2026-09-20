// The theme index collapses each theme into a <details>. Two things stop
// that from costing the reader anything.
//
// 1. A problem page links to `themes.html#mirror`, and the target is a
//    collapsed <details>. Recent browsers open it on fragment navigation,
//    but not all of them and not in older versions, and a link that scrolls
//    to a closed box looks broken. Opening it explicitly is five lines and
//    works everywhere.
// 2. Find-in-page does not search inside a closed <details> outside Chrome,
//    so "open all" restores Ctrl+F over the whole index.

export function openTarget(hash, doc = document) {
  // The id can be a theme like `single-piece:black`, whose colon is not
  // valid in a CSS selector, so look it up by id rather than querySelector.
  const id = (hash || "").replace(/^#/, "");
  if (!id) return null;
  const el = doc.getElementById(decodeURIComponent(id));
  if (el && el.tagName === "DETAILS") {
    el.open = true;
    return el;
  }
  return el;
}

if (typeof document !== "undefined") {
  const reveal = () => {
    const el = openTarget(location.hash);
    // Re-run the jump: the browser already scrolled while the box was shut,
    // so the heading is in the wrong place once it expands.
    if (el) el.scrollIntoView({ block: "start" });
  };
  reveal();
  window.addEventListener("hashchange", reveal);

  const button = document.getElementById("open-all");
  if (button) {
    const all = [...document.querySelectorAll("details.theme-block")];
    const sync = () => {
      const shut = all.filter((d) => !d.open).length;
      button.textContent = shut ? "Open all themes" : "Close all themes";
      return shut;
    };
    button.addEventListener("click", () => {
      const opening = sync() > 0;
      all.forEach((d) => { d.open = opening; });
      sync();
    });
    all.forEach((d) => d.addEventListener("toggle", sync));
    sync();
  }
}
