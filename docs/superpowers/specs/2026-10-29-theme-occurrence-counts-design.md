# Theme occurrence counts (`--theme promotion:4`, `--theme ideal:2`) — design

Status: proposed 2026-10-29, awaiting approval. Plan:
`docs/superpowers/plans/2026-10-29-theme-occurrence-counts.md`.

## The request

A user (problemist) asked for two things, in their words:

> a) es wäre schön, ein Thema zu haben, dass die Anzahl der Umwandlungen in
> allen Lösungen einer Stellung zählt (und danach suchen zu können):
> `--theme promotion:4` sucht also bei 1 oder 2 oder mehr Lösungen nach 4
> Umwandlungen
>
> b) es wäre super, wenn man Themen nach Anzahl suchen könnte:
> `--theme ideal:2`, `--theme model:2` usw.

Decided with the maintainer on 2026-10-29: b) counts **occurrences**, not
solutions, "because many themes could occur several times in one solution".
With that, a) is b) applied to `promotion`, and one mechanism serves both.

## Semantics

`--theme NAME:N` matches a position when the theme NAME occurs **at least N
times in total, summed over all of the position's optimal solutions**.

- `promotion:4`: four promotions altogether — in one solution, or two in
  each of two solutions, or one in each of four.
- `ideal:2`: two ideal mates altogether. A solution ends in one mate, so this
  means at least two solutions end in an ideal mate.
- `switchback:3`: three switchbacks altogether, by any units, in any
  solutions.

Further rules:

1. **At least, not exactly.** `promotion:4` also matches 5 promotions. An
   exact search is `promotion:4` without `promotion:5`, which the query
   language cannot say; it is out of scope (see the end).
2. **Combines with everything else** as today: several `--theme` options are
   all required (AND), and `--count C` restricts the number of solutions.
   `--count 2 --theme ideal:2` is "two solutions, both ending in an ideal
   mate".
3. **`NAME:1` is plain `NAME`** for every theme that matches when *some*
   solution shows it. For the two themes that need *every* solution
   (`nocapture`, `nocheck`), `nocapture:N` means "at least N solutions are
   capture-free" — a different question from plain `nocapture` ("all
   solutions are capture-free"). The theme list says so.
4. **Exact counts.** `mine` enumerates every optimal solution of a position
   whose count is below the saturation value (255) and never enumerates a
   saturated one; a counted theme needs solutions, so saturated positions are
   skipped exactly as for any solution theme today. The 100-solution cap of
   `probe` does not apply to `mine`. The `mine --interactive` shell, which
   filters a result set after the fact, judges a saturated position on its
   first 100 solutions, as it already does for every theme; there a count is
   a lower bound, and the shell's existing "saturated" note says so.

## Syntax and name resolution

A trailing `:<digits>` is always a count. The rest of the name is resolved
exactly as today.

| typed | meaning |
|---|---|
| `promotion:4` | `promotion`, at least 4 occurrences |
| `excelsior:white:2` | `excelsior:white`, at least 2 |
| `maslar:black-white:2` | `maslar:black-white`, at least 2 |
| `ideal:02` | same as `ideal:2`; the canonical name prints `ideal:2` |
| `promotions:qrr` | unchanged: the parametric multiset theme |
| `promotion:qrr` | unchanged error: `did you mean promotions:qrr?` |

Errors, exact wording (the error names the theme as typed):

| typed | message |
|---|---|
| `ideal:0` | `theme "ideal:0": a count must be at least 1` |
| `ideal:10000` | `theme "ideal:10000": a count must be at most 9999` |
| `set-play:2` | `theme "set-play:2": set-play cannot be counted -- it is a property of the position, not something a solution shows several times` |
| `zilahi:2`, `allumwandlung:2` | same wording with "a property of the whole solution set" |
| `promotions:qrr:2` | same wording as zilahi, for `promotions` |
| `pure:yes` | `theme "pure:yes": pure takes no value; a count is a whole number, e.g. pure:2` |

The upper bound 9999 only guards against nonsense input: a solution has at
most a few dozen plies and a position at most 254 enumerated solutions.

## What one occurrence is

Principle: **an occurrence is one completion of the theme**, identified by
what completes it — the mating position (mate themes), a ply (move themes) or
a unit (unit themes). For every theme, a solution has at least one occurrence
if and only if the existing detector says it shows the theme; this
equivalence is tested over the whole fixture set, so no existing answer
changes.

| theme | occurrences in one solution |
|---|---|
| pure, model, ideal, mirror | 1 if its mate is of that kind, else 0 |
| umnov-mate | 1 if the mating move lands on the square Black's last move vacated |
| promotion | promoting plies |
| underpromotion | plies promoting to rook, bishop or knight |
| excelsior, excelsior:white, excelsior:black | pawns (of that colour) that start on their own second rank and promote |
| switchback | returns: positions *i* in a unit's trajectory with square[*i*] = square[*i*+2] (a pendulum A-B-A-B has two) |
| closed-walk | completed circuits per unit, counted left to right without overlap: A-B-C-A is 1, A-B-C-A-B-C-A is 2 |
| pendulum | units whose trajectory is a pendulum |
| self-block | squares of the black king's field that a black unit moved onto and holds, unattacked, in the mate |
| single-piece, single-piece:white, single-piece:black | 1 if the solution is single-piece (for that side) |
| en-passant | en-passant plies |
| kniest | capturing plies whose destination is the square the black king is mated on |
| zajic | black-king recaptures on the mating square that follow an earlier capture there |
| phoenix | promoting plies that re-create a type the same side lost earlier in the solution |
| schnoebelen | promotions whose promoted unit is captured on its promotion square without having moved |
| nocapture | 1 if the solution captures nothing |
| nocheck | 1 if no ply before the mate gives check |
| umnov | plies landing on the square the preceding ply vacated |
| klasinc | leave-and-return windows of a unit that a line piece passes over |
| indian | plies that complete an Indian (the discovering move) |
| maslar, maslar:black-white | plies that complete a Maslar (the line piece's capture) |

Not countable, because they are not something a single solution shows:
`set-play` (a property of the position), `zilahi`, `allumwandlung` and
`promotions:<types>` (properties of the whole solution set).

## Where it is available

Everything that accepts a theme name goes through one resolver
(`themes::resolve_theme`), so the count works everywhere a theme name is
accepted, with no surface-specific code for the filter itself:

- CLI `helpmate mine --theme promotion:4`, and the `mine --interactive` shell;
- Python `Tablebase.mine(..., themes=["ideal:2"])` and `check_theme`;
- the HTTP API `/v1/mine?theme=ideal:2` (a bad count is a 400 with the
  resolver's message, as for any bad theme today).

Additionally:

- **`helpmate themes`** prints `countable: yes` or `countable: no` for every
  theme, plus one line explaining `NAME:N`.
- **`/v1/themes` and Python `themes()`** gain a boolean field `countable`.
- **Dashboard (mine screen):** a free-text field *Count filters*, for example
  `promotion:4 ideal:2`, whose words are added to the theme list of the
  query. The server validates; an error shows as today.
- **`mine --themes --json` / `--jsonl`:** each hit gains
  `"theme_counts": {"promotion": 4, "ideal": 2}` with every countable theme
  that occurs at least once, so a search result can be checked. Text output
  is unchanged, and so is the existing `"themes"` list (the site and booklet
  pipelines read it).

`probe` output is unchanged.

## Out of scope (noted in the mining concept)

Exact counts (`=N`) and upper bounds; counting per solution ("every solution
promotes"); counts for the set-wide themes; echo detection; a quality score.
See `docs/research/2026-10-29-mining-concept.md`.
