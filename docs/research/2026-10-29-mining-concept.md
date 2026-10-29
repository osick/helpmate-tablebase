# Mining concept: what to search for next

Written 2026-10-29, after six pieces were completed and the first user asked
for counted themes. A collection of directions, not a plan: each item says
what it is, why problemists would want it, what it builds on, and a rough
cost. Items are picked up one at a time with their own design and plan; the
first, theme occurrence counts, is
`docs/superpowers/specs/2026-10-29-theme-occurrence-counts-design.md`.

## Where mining stands

`helpmate mine MATERIAL --dtm D` scans a table for positions at one depth,
filtered by solution count (`--count`), solution shape (`--starts`,
`--ends`) and themes (`--theme`, 33 detectors). A theme matches when some
solution shows it (`nocapture`, `nocheck`: every solution); `zilahi`,
`allumwandlung` and `promotions:<types>` compare whole solution sets. Every
optimal solution of a non-saturated position is enumerated exactly; the
`--interactive` shell refines a result set afterwards.

## 1. Counting, the rest of it

Theme occurrence counts (`promotion:4`, `ideal:2`) are designed. Left out on
purpose, worth adding when someone asks:

- **Exact and upper bounds:** `promotion:=4`, `promotion:<=2`. The resolver
  change is small; the syntax needs care so it reads well in a shell.
- **Per solution:** "every solution promotes" (`promotion:each`), "every
  solution ends in a model mate" (`model:each`). This is the generalisation
  of `nocapture`'s every-solution rule to all themes, and probably what many
  composers mean by "a problem with two model mates".
- **Counts for set themes:** "how many distinct promotion types" (AUW is 4).

## 2. Echo mates

Two solutions whose mating positions are the same picture moved (shifted,
mirrored, rotated) on the board — the high point of multi-solution
helpmates, and the natural next question after `model:2`. Variants: *echo*
(any geometric transformation), *chameleon echo* (the king on squares of
different colours), *diagonal-orthogonal echo*. Builds on the set-theme
machinery (`zilahi` already compares solutions). Cost: medium — define the
mating picture (king, its field, the units doing duty) and compare it under
the 8 board symmetries plus translation.

## 3. A quality score

One number per problem from what is already computed: legal diagram (no
illegal last move), quiet first move, no check in the diagram, economy (every
unit takes part; the model/ideal tests already decide this for the mate),
themes shown, and length. Uses:

- `mine --sort quality`, so the best problems come first instead of index
  order;
- DEEPEST picks the best of the positions at its depth instead of the first
  one, which would also replace most of the 87 illegal diagrams there
  without a separate mining run;
- the site's puzzles.

Cost: medium; the weights are a matter of taste and need a problemist's eye.

## 4. Theme statistics per class

How often each theme occurs among a class's unique positions, by depth: "in
KBvkrp, 0.3 % of unique h#5 end in an ideal mate". A site page per theme with
its rarest and longest examples. A by-product of a full mining pass over the
unique positions; expensive once per class, then static data like the
material pages.

## 5. User-defined themes

A small description language for themes, so a problemist can state a new
theme without C++: patterns over plies (who moves, from/to, capture,
promotion, check) and over the mating position. Turns requests like this
week's into configuration. Cost: high; worth it only once requests keep
coming.

## 6. Twins

A unique problem where moving, removing or swapping one unit gives a second
unique problem, often with a related solution. Problemists value twins
highly. Search: for each unique position, try the small changes and probe the
results — cheap per position, but the candidate space is large, so it needs
a good pre-filter (for example, only positions that already show a theme).

## 7. Smaller items

- **Counts on display:** `probe --themes` and the dashboard showing
  `promotion ×4`, once counted searches are in use.
- **A hint for impossible queries:** `--count 1 --theme ideal:2` can never
  match (one solution has one mate); the CLI could say so instead of
  returning nothing.
- **Replacing the 87 illegal diagrams in DEEPEST** with legal positions of the
  same depth (deferred on 2026-10-27; item 3 may make it unnecessary).
- **Seven pieces and the solution count:** if seven-piece tables store only
  DTM or a 2-bit uniqueness flag (discussed 2026-10-28), mining by count
  becomes a path check per candidate; this concept's features must then be
  re-costed.
