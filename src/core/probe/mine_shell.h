#pragma once
#include <istream>
#include <ostream>

#include "probe/mine_set.h"

namespace hm {

// The `mine --interactive` loop: reads one command per line from `in`,
// narrows/inspects/saves `root` and its descendants, replies on `out`. The
// prompt, progress and every error go to `err`, so stdout stays a clean
// record of results. Returns 0 on quit/exit/EOF. Never throws for user
// input; a MissingTableError from enrichment is absorbed by MineSet.
// `cli_facets`: which of --themes/--solutions were given on the command
// line; they decide what `save FILE.json` includes.
int run_mine_shell(MineSet root, std::istream& in, std::ostream& out, std::ostream& err,
                    MineSet::Facets cli_facets);

}  // namespace hm
