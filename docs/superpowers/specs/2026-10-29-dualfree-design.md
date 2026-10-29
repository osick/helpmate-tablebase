# `mine --dualfree` — design

Status: proposed 2026-10-29, awaiting approval. Plan:
`docs/superpowers/plans/2026-10-29-dualfree.md`.

## The request

After counted themes (#95), a search such as `--count 2 --theme model:2`
also finds positions whose two solutions end in **the same mate**, reached by
different move orders or routes — for example KBBvk
`8/6k1/6B1/8/8/B7/8/1K6 w`, h#4.5: Black plays Kg8, Kh8 or Kh8, Kg8 and both
solutions end Kh6, Bf8#. The maintainer, 2026-10-29: add `--dualfree`, which
removes every position in which at least two solutions are duals of each
other. Decided: two solutions are **duals when they end in the identical
final position** (the same mating picture), however they got there. That
covers a pure reordering of the same moves and a different route to the same
mate.

## Semantics

`mine --dualfree` keeps a position only if **no two of its optimal solutions
end in the same final position**. Equivalently: the number of distinct final
positions equals the number of solutions.

- A position with one solution is dual-free (there is nothing to compare).
- Combines with every other filter (AND): `--count 2 --theme model:2
  --dualfree` is "two solutions, two model mates, and the two mates are
  different positions".
- "Final position" is the board after the mating move: piece placement and
  side to move (always Black after White's mate). Castling and en-passant
  rights play no part (the tables hold no castling; an en-passant right
  after a mate cannot matter).
- Needs every solution, so a saturated position (count 255) cannot be
  decided: `mine` skips it and counts it in `skipped_saturated`, as it does
  for `--starts`/`--ends` and solution themes. The `--interactive` shell,
  which judges saturated hits on their first 100 solutions everywhere, does
  the same here; there a saturated hit can only be found *not* dual-free.

This is a filter, not a theme: as a theme, every one-solution position would
carry a `dualfree` tag, which would flood `probe --themes`, the site and the
booklet.

## Surfaces

| surface | form |
|---|---|
| CLI | `helpmate mine ... --dualfree` (no value) |
| JSON / JSONL header | `"filter": {..., "dualfree": true}` (false when not given) |
| interactive shell | `dualfree` keeps dual-free hits, `not dualfree` keeps the others |
| Python | `Tablebase.mine(..., dualfree=False)` |
| HTTP API | `/v1/mine?...&dualfree=true` |
| dashboard (mine screen) | checkbox *dual-free only* |

`probe`, `line` and the theme list are unchanged.

## Out of scope

Other dual notions of problem chess (a dual in the play that does not change
the final position, minor duals, "twins"); reporting *which* solutions are
duals. Noted in `docs/research/2026-10-29-mining-concept.md` if asked for.
