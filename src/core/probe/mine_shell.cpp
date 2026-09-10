#include "probe/mine_shell.h"

#include <algorithm>
#include <cerrno>
#include <climits>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
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

void print_hit(std::ostream& out, MineSet& set, Hit& h) {
    set.ensure_themes(h);
    set.ensure_solutions(h);
    out << h.fen << "\n";
    if (!h.unavailable.empty()) {
        out << "  unavailable: " << h.unavailable << "\n";
        return;
    }
    out << "  themes:";
    if (h.themes->empty()) out << " (none)";
    for (const auto& n : *h.themes) out << " " << n;
    out << "\n";
    for (const auto& line : *h.solutions) {
        if (line.empty()) continue;
        out << " ";
        for (const auto& mv : line) out << " " << mv;
        out << "\n";
    }
}

}  // namespace

int run_mine_shell(MineSet root, std::istream& in, std::ostream& out, std::ostream& err,
                    MineSet::Facets cli_facets) {
    std::vector<MineSet> stack;  // previous sets, most recent last
    MineSet cur = std::move(root);
    auto progress = [&](size_t done, size_t total) {
        // Every 100 done; the D==T tally line is redundant with the "N
        // positions" stdout line unless D%100==0 too, in which case it is
        // just a normal 100-multiple print, not a special final one.
        if (done % 100 == 0) err << "evaluating themes: " << done << "/" << total << "\n";
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
            try {
                narrowed(cur.with_theme(w[at], negate, progress));
            } catch (const std::invalid_argument& e) {
                err << "error: " << e.what() << "\nvalid themes:";
                for (const auto& t : themes::theme_registry()) err << " " << themes::display_name(t);
                err << "\n";
            }
        } else if (c == "count" || c == "starts" || c == "ends") {
            int n = 0;
            if (!need_int(w, n)) continue;
            narrowed(c == "count" ? cur.with_count(n) : c == "starts" ? cur.with_starts(n) : cur.with_ends(n));
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
            Hit h = cur.hits()[(size_t)i - 1];
            print_hit(out, cur, h);
        } else if (c == "themes") {
            auto hist = cur.theme_histogram(progress);
            size_t width = 0;
            for (const auto& [name, cnt] : hist) {
                (void)cnt;
                width = std::max(width, name.size());
            }
            for (const auto& [name, n] : hist) out << std::left << std::setw((int)width + 2) << name << n << "\n";
        } else if (c == "save") {
            if (w.size() < 2) {
                err << "save needs a FILE\n";
                continue;
            }
            const std::string& path = w[1];
            const bool json = path.size() >= 5 && path.compare(path.size() - 5, 5, ".json") == 0;
            std::ofstream f(path);
            if (!f) {
                err << "cannot write " << path << ": " << std::strerror(errno) << "\n";
                continue;
            }
            if (json) {
                MineSet::Facets fac{cli_facets.themes || cur.all_have_themes(), cli_facets.solutions};
                f << cur.to_json(fac, progress);
                out << "saved " << cur.size() << " positions to " << path << " (json" << (fac.themes ? ", themes" : "")
                    << (fac.solutions ? ", solutions" : "") << ")\n";
            } else {
                for (const auto& h : cur.hits()) f << h.fen << "\n";
                out << "saved " << cur.size() << " positions to " << path << " (fens)\n";
            }
        } else {
            err << "unknown command \"" << c << "\"; type help\n";
        }
    }
    return 0;
}

}  // namespace hm
