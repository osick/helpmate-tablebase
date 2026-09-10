#pragma once
#include <istream>
#include <ostream>
#include <string>

#include "probe/mine_set.h"

namespace hm {

// The `mine --interactive` loop: reads one command per line from `in`,
// narrows/inspects/saves `root` and its descendants, replies on `out`. The
// prompt, progress and every error go to `err`, so stdout stays a clean
// record of results. Returns 0 on quit/exit/EOF. Never throws for user
// input; a MissingTableError from enrichment is absorbed by MineSet.
// `cli_facets`: which of --themes/--solutions were given on the command
// line; they decide what `save FILE.json` includes. `tables_dir` is the
// --tables directory, needed only to spell out the `helpmate gen` command in
// the note printed when enrichment finds a table missing.
int run_mine_shell(MineSet root, std::istream& in, std::ostream& out, std::ostream& err,
                   MineSet::Facets cli_facets, const std::string& tables_dir);

}  // namespace hm
