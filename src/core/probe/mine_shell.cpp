#include "probe/mine_shell.h"

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <climits>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "themes/registry.h"

namespace hm {
namespace {

std::vector<std::string> split(const std::string& line) {
    std::istringstream ss(line);
    std::vector<std::string> w;
    for (std::string t; ss >> t;) w.push_back(t);
    return w;
}

bool positive_int(const std::string& s, int& out) {
    if (s.empty()) return false;
    for (char c : s)
        if (c < '0' || c > '9') return false;
    try {
        long v = std::stol(s);
        if (v < 1 || v > INT_MAX) return false;
        out = (int)v;
        return true;
    } catch (const std::exception&) { return false; }
}

void help(std::ostream& out) {
    out << "commands:\n"
           "  theme NAME       keep positions showing NAME (promotions:qrr allowed)\n"
           "  not theme NAME   drop positions showing NAME\n"
           "  count N          keep positions with exactly N optimal solutions\n"
           "  starts N         keep positions with N distinct first moves\n"
           "  ends N           keep positions with N distinct mating moves\n"
           "  back             undo the last narrowing\n"
           "  reset            return to the loaded set\n"
           "  list [FROM [N]]  print FENs FROM..FROM+N-1 (default 1, 20)\n"
           "  show I           print hit I with its themes and every solution\n"
           "  themes           how many positions show each theme\n"
           "  save FILE        write the set: FILE.json as JSON, otherwise bare FENs\n"
           "  help             this list\n"
           "  quit             leave (exit and EOF do too)\n";
}

}  // namespace

int run_mine_shell(MineSet root, std::istream& in, std::ostream& out, std::ostream& err,
                   MineSet::Facets cli_facets, const std::string& tables_dir) {
    std::vector<MineSet> stack;  // previous sets, most recent last
    MineSet cur = std::move(root);
    // Every 100 hits OR every second, per the spec: 100 alone goes quiet for
    // minutes on slow enrichment, a timer alone floods a fast one. The D==T
    // tally line is redundant with the "N positions" stdout line unless it
    // happens to fall on a tick, in which case it is just a normal tick.
    auto last_tick = std::chrono::steady_clock::now();
    auto progress = [&](size_t done, size_t total) {
        auto now = std::chrono::steady_clock::now();
        if (done % 100 != 0 && now - last_tick < std::chrono::seconds(1)) return;
        last_tick = now;
        err << "evaluating: " << done << "/" << total << "\n";
    };
    // Enrichment inside a narrowing or a tally can find a table missing; the
    // hit is kept and marked, and the user is told once, here, how to fix it.
    // Must be read off `cur` BEFORE `narrowed` moves it away: it is the
    // source set, not the result, whose hits get marked.
    auto note_unavailable = [&](size_t before) {
        const size_t now = cur.unavailable_count();
        if (now <= before) return;
        err << "note: " << (now - before)
            << " position(s) could not be annotated: a table their solutions reach is missing"
               " (each says which in show/save); run: helpmate gen "
            << cur.material().name() << " --tables " << tables_dir << "\n";
    };
    auto narrowed = [&](MineSet next) {
        stack.push_back(std::move(cur));
        cur = std::move(next);
        out << cur.size() << " positions\n";
    };
    auto need_int = [&](const std::vector<std::string>& w, int& n) {
        if (w.size() < 2 || !positive_int(w[1], n)) {
            err << w[0] << " needs a positive integer\n";
            return false;
        }
        return true;
    };

    std::string line;
    while (true) {
        err << "[" << cur.size() << "] mine> ";
        if (!std::getline(in, line)) break;
        auto w = split(line);
        if (w.empty()) continue;
        const std::string& c = w[0];
        if (c == "quit" || c == "exit") break;
        if (c == "help") {
            help(out);
        } else if (c == "theme" || (c == "not" && w.size() >= 2 && w[1] == "theme")) {
            const bool negate = c == "not";
            const size_t at = negate ? 2 : 1;
            if (w.size() <= at) {
                err << "theme needs a NAME\n";
                continue;
            }
            const size_t before = cur.unavailable_count();
            try {
                MineSet next = cur.with_theme(w[at], negate, progress);
                note_unavailable(before);
                narrowed(std::move(next));
            } catch (const std::invalid_argument& e) {
                err << "error: " << e.what() << "\nvalid themes:";
                for (const auto& t : themes::theme_registry()) err << " " << themes::display_name(t);
                err << "\n";
            }
        } else if (c == "count" || c == "starts" || c == "ends") {
            int n = 0;
            if (!need_int(w, n)) continue;
            const size_t before = cur.unavailable_count();
            MineSet next = c == "count"    ? cur.with_count(n)
                           : c == "starts" ? cur.with_starts(n)
                                           : cur.with_ends(n);
            note_unavailable(before);
            narrowed(std::move(next));
        } else if (c == "back") {
            if (stack.empty()) {
                err << "already at the root set\n";
            } else {
                cur = std::move(stack.back());
                stack.pop_back();
            }
            out << cur.size() << " positions\n";
        } else if (c == "reset") {
            if (!stack.empty()) {
                cur = std::move(stack.front());
                stack.clear();
            }
            out << cur.size() << " positions\n";
        } else if (c == "list") {
            int from = 1, n = 20;
            if (w.size() >= 2 && !positive_int(w[1], from)) {
                err << "list needs a positive integer\n";
                continue;
            }
            if (w.size() >= 3 && !positive_int(w[2], n)) {
                err << "list needs a positive integer\n";
                continue;
            }
            if ((size_t)from > cur.size()) {
                err << "no hit " << from << " (set has " << cur.size() << ")\n";
                continue;
            }
            for (size_t i = (size_t)from - 1; i < cur.size() && i < (size_t)from - 1 + (size_t)n; ++i)
                out << std::setw(6) << (i + 1) << "  " << cur.hits()[i].fen << "\n";
        } else if (c == "show") {
            int i = 0;
            if (w.size() < 2 || !positive_int(w[1], i) || (size_t)i > cur.size()) {
                err << "no hit " << (w.size() >= 2 ? w[1] : "?") << " (set has " << cur.size() << ")\n";
                continue;
            }
            // Enrich IN the set, not on a copy: USAGE promises `show` caches,
            // and a second `show` (or a later `save`) must not pay again.
            Hit& h = cur.hit((size_t)i - 1);
            cur.ensure_themes(h);
            cur.ensure_solutions(h);
            cur.ensure_shape(h);  // so a saturated hit says so here too, as in to_text/to_json
            cur.write_hit(out, h, {true, true});
        } else if (c == "themes") {
            const size_t before = cur.unavailable_count();
            auto hist = cur.theme_histogram(progress);
            note_unavailable(before);
            size_t width = 0;
            for (const auto& [name, cnt] : hist) {
                (void)cnt;
                width = std::max(width, name.size());
            }
            for (const auto& [name, n] : hist)
                out << std::left << std::setw((int)width + 2) << name << n << "\n";
            out << std::right;  // adjustfield is sticky; restore before `list` reuses `out`
        } else if (c == "save") {
            if (w.size() < 2) {
                err << "save needs a FILE\n";
                continue;
            }
            // The whole rest of the line is the path: `save my file.json`
            // used to write a file called "my" and report success.
            std::string path = w[1];
            for (size_t k = 2; k < w.size(); ++k) path += " " + w[k];
            const bool json = path.size() >= 5 && path.compare(path.size() - 5, 5, ".json") == 0;
            std::ofstream f(path);
            if (!f) {
                err << "cannot write " << path << ": " << std::strerror(errno) << "\n";
                continue;
            }
            std::string wrote;
            if (json) {
                // An empty set trivially "has all themes"; claiming (json,
                // themes) for a file with no positions in it is a lie.
                MineSet::Facets fac{cli_facets.themes || (cur.size() > 0 && cur.all_have_themes()),
                                    cli_facets.solutions};
                f << cur.to_json(fac, progress);
                wrote = std::string("json") + (fac.themes ? ", themes" : "") +
                        (fac.solutions ? ", solutions" : "");
            } else {
                for (const auto& h : cur.hits()) f << h.fen << "\n";
                wrote = "fens";
            }
            // A full disk or a quota only shows up at flush; without this the
            // shell reports "saved" over a truncated or empty file.
            f.flush();
            if (!f) {
                err << "cannot write " << path << ": " << std::strerror(errno) << "\n";
                continue;
            }
            out << "saved " << cur.size() << " positions to " << path << " (" << wrote << ")\n";
        } else {
            err << "unknown command \"" << c << "\"; type help\n";
        }
    }
    return 0;
}

}  // namespace hm
