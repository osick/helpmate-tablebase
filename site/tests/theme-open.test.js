// theme-open.js opens the collapsed <details> a problem page links to.
// The module guards its DOM work behind `typeof document`, so importing it
// here is safe; these exercise the pure lookup with a fake document.
import test from "node:test";
import assert from "node:assert/strict";
import { openTarget } from "../js/theme-open.js";

function fakeDoc(nodes) {
  return { getElementById: (id) => nodes[id] || null };
}

test("opens the details element the hash names", () => {
  const el = { tagName: "DETAILS", open: false };
  assert.equal(openTarget("#mirror", fakeDoc({ mirror: el })), el);
  assert.equal(el.open, true);
});

test("handles a theme id containing a colon, which is not a valid selector", () => {
  const el = { tagName: "DETAILS", open: false };
  const doc = fakeDoc({ "single-piece:black": el });
  assert.equal(openTarget("#single-piece:black", doc), el);
  assert.equal(el.open, true);
});

test("decodes a percent-encoded hash", () => {
  const el = { tagName: "DETAILS", open: false };
  const doc = fakeDoc({ "single-piece:black": el });
  openTarget("#single-piece%3Ablack", doc);
  assert.equal(el.open, true);
});

test("an empty or unknown hash opens nothing and does not throw", () => {
  assert.equal(openTarget("", fakeDoc({})), null);
  assert.equal(openTarget("#nope", fakeDoc({})), null);
});

test("a non-details target is returned but not forced open", () => {
  const el = { tagName: "SECTION" };
  assert.equal(openTarget("#x", fakeDoc({ x: el })), el);
  assert.equal(el.open, undefined);
});
