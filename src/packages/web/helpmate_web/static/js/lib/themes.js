// Pure helpers for the theme surfaces. Kept out of mine.js/explorer.js so they
// are testable under `node --test` with no DOM.

// The theme names chosen in a <select multiple>, as a plain array.
export function selectedThemes(el) {
  if (!el || !el.selectedOptions) return [];
  return Array.from(el.selectedOptions, (o) => o.value);
}

// One line of prose for a position's detected themes.
export function themeSummary(names) {
  if (names === undefined || names === null) return "";
  return names.length ? names.join(" · ") : "no themes detected";
}

// True for a theme whose detector does not need full solution enumeration
// (needs "position" or "plane" rather than "solutions") -- these still
// answer on positions whose stored solution count has saturated (capped at
// 255), where a Needs::Solutions theme is silently skipped. Driven entirely
// by the `needs` field the server reports, never by name.
export function answersOnSaturated(theme) {
  return !!theme && theme.needs !== "solutions" && theme.needs !== undefined;
}

// Tooltip text for a theme picker option: its own definition, with a note
// appended when it also answers on saturated positions.
export function themeOptionTitle(theme) {
  const doc = (theme && theme.doc) || "";
  return answersOnSaturated(theme)
    ? `${doc} (also answers on positions with saturated solution counts)`
    : doc;
}

// A parametric theme (e.g. promotions:<types>) is queried as `base:value`;
// the server marks it with a non-null `parameter` field and a display name
// ending in `:<...>`. Driven by the field, never by the name.
export function isParametric(theme) {
  return !!theme && theme.parameter !== null && theme.parameter !== undefined;
}

// The base of a parametric display name: "promotions:<types>" -> "promotions".
export function parametricBase(theme) {
  const name = (theme && theme.name) || "";
  const i = name.indexOf(":");
  return i === -1 ? name : name.slice(0, i);
}

// The `theme` query list a search sends: every picked boolean name, plus
// `base:value` for each parametric theme whose input is non-empty. Whitespace
// is trimmed; the server canonicalises the value (order, case) and rejects a
// bad one with a 400 the screen shows verbatim.
export function themeQueryNames(selected, paramValues) {
  const out = Array.from(selected || []);
  for (const [base, raw] of Object.entries(paramValues || {})) {
    const v = String(raw || "").trim();
    if (v) out.push(`${base}:${v}`);
  }
  return out;
}
