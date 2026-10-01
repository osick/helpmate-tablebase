// Pure logic for the Materials page and the front page's contributor block.
export const STATES = ["open", "claimed", "in review", "done", "not needed"];
const KEYS = ["pieces", "state", "prio", "pawns", "contributor", "q"];

export function priorityLabel(p) { return p ? `P${p}` : "—"; }

function sides(s) {
  const m = /^K([QRBNP?]*)vk([qrbnp?]*)$/.exec(s);
  return m ? [m[1], m[2]] : null;
}
function sideMatch(have, pat) {
  if (have.length !== pat.length) return false;
  const rest = [...have];
  for (const c of pat) {
    if (c === "?") continue;
    const i = rest.indexOf(c);
    if (i < 0) return false;
    rest.splice(i, 1);
  }
  return true;
}
export function wildcardMatch(name, pattern) {
  const p = (pattern || "").trim();
  if (!p) return true;
  if (!p.includes("?")) return name.toLowerCase().includes(p.toLowerCase());
  const n = sides(name), q = sides(p);
  return !!(n && q && sideMatch(n[0], q[0]) && sideMatch(n[1], q[1]));
}

export function mergeStatus(rows, status) {
  const st = status && status.materials ? status.materials : {};
  return rows.map((r) => {
    const s = st[r.material];
    const state = s ? s.state : r.done ? "done" : r.priority === null ? "not needed" : "open";
    return { ...r, state, contributor: s ? s.contributor : null,
      hf_pr: s ? s.hf_pr : null, claim: s ? s.claim : null };
  });
}

const on = (v) => v !== undefined && v !== "" && v !== "all";
export function filterRows(rows, f) {
  return rows.filter((r) =>
    (!on(f.pieces) || String(r.pieces) === String(f.pieces)) &&
    (!on(f.state) || r.state === f.state) &&
    (!on(f.prio) || String(r.priority) === String(f.prio)) &&
    (!on(f.pawns) || String(r.pawns) === String(f.pawns)) &&
    (!on(f.contributor) || r.contributor === f.contributor) &&
    wildcardMatch(r.material, f.q));
}

export function defaultOrder(rows) {
  const rank = (r) => STATES.indexOf(r.state);
  const pr = (r) => (r.priority === null || r.priority === undefined ? 99 : r.priority);
  return [...rows].sort((a, b) => rank(a) - rank(b) || pr(a) - pr(b) || a.pawns - b.pawns ||
    (a.material < b.material ? -1 : a.material > b.material ? 1 : 0));
}

export function parseQuery(hash) {
  const i = (hash || "").indexOf("?");
  if (i < 0) return {};
  const out = {};
  for (const [k, v] of new URLSearchParams(hash.slice(i + 1))) if (KEYS.includes(k)) out[k] = v;
  return out;
}
export function toQuery(obj) {
  const p = new URLSearchParams();
  for (const k of KEYS) if (on(obj[k])) p.set(k, obj[k]);
  return p.toString();
}

export function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}
