"""Every word the DEEPEST booklet prints, in English, German and French.

`tools/deepest_booklet.py --lang de` picks one of these. Values are LaTeX;
`<name>` marks a slot the booklet fills (see `fill`), so LaTeX's own braces
need no escaping. The chess itself -- diagrams, figurine moves, h#n, the
material names -- is the same in every language and is not here.

Problem-chess terms follow the literature of each language: a helpmate is a
Hilfsmatt / mat aidé, a sound problem korrekt / correct, a man a Stein /
pièce, a ply a Halbzug / demi-coup.
"""
from __future__ import annotations

LANGS = ("en", "de", "fr")

# As in LICENSE.
MAINTAINER = "Oliver Sick"


def fill(template: str, **slots) -> str:
    """Put `slots` into the `<name>` places of a template."""
    for k, v in slots.items():
        template = template.replace(f"<{k}>", str(v))
    return template


TEXT: dict[str, dict] = {
    "en": {
        "babel": "english",
        "decimal": ".",
        "footer": "Longest helpmates with up to six men",
        "title": r"Longest Helpmates\\[0.3em] with up to Six Men",
        "subtitle": r"One problem per material class:\\ the longest helpmate that still has a single solution",
        "all_classes": "All <n> material classes from three to six men",
        "generated": r"Generated from the helpmate tablebase.\\ Every diagram, length and solution in this booklet is machine-derived.",
        "brief_title": "The tablebase in brief",
        "brief": [
            r"A \emph{helpmate} is a chess problem in which both sides cooperate: Black moves first and"
            r" helps White deliver mate. \textbf{h\#n} asks for mate on White's \(n\)th move; in"
            r" \textbf{h\#n.5} White starts, so the solution opens \(1\ldots\) and takes one half-move"
            r" more. A problem is \emph{sound} only if its solution is unique: a second solution is a cook.",
            r"The helpmate tablebase solves every legal position of every material class with up to six"
            r" men. For each position and each side to move it stores the distance to mate under"
            r" cooperation and the number of distinct shortest solutions, so a sound problem is simply"
            r" a position whose count is one.",
        ],
        "facts": {
            "classes": "Classes in this booklet", "classes_v": "<n> (three to six men)",
            "positions": "Positions in them", "positions_v": "<n> (both sides to move)",
            "helpmates": "With a helpmate", "unique": "With a unique solution",
            "deepest": "Longest unique problem", "longest": "Longest helpmate",
            "published": "Published compositions found",
        },
        "built": r"The tables are built by a C++ generator that works through each class depth by depth,"
                 r" from the mates outwards, after first building every table a capture or promotion"
                 r" leads to. They are checked by an independent solver on sampled positions, by an"
                 r" exhaustive cross-check of KQvk against python-chess, and by the requirement that a"
                 r" run on many threads writes byte for byte the same file as a run on one. Every table"
                 r" contributed from outside passes a seven-step verification before it is published.",
        "credit": "<name> (<n> tables)", "and": " and ",
        "code": "Code", "tables": "Tables",
        "about_title": "Authorship and contributors",
        "about": [
            r"The helpmate tablebase and this booklet are the work of <maintainer>, who maintains the"
            r" project: the generator, the verification and the selection of the problems.",
            r"Most of the six-man tables were computed by <who> on their own machines and checked"
            r" before publication. T31M also made the generator and the search for problems many"
            r" times faster.",
        ],
        "maintainer": "Maintainer", "contributors": "Contributors",
        "prior_title": "Prior publication",
        "prior": r"The search for earlier publications is not complete. Each position was compared"
                 r" with a collection of published helpmates, and the matches found are named on the"
                 r" problem's page. A page without such a box does \emph{not} mean that the position"
                 r" has never been published: no claim of originality or priority is made for any"
                 r" position in this booklet. Published problems remain the intellectual property of"
                 r" their composers. Earlier publications we have missed are welcome as an issue on"
                 r" GitHub.",
        "read_title": "How to read a page",
        "read": [
            r"Every class has one page. The \textcolor{ink}{header} names the material, White's men"
            r" first, and gives the problem's stipulation. Next comes the class at a glance: its longest"
            r" unique problem, how many positions reach that length with a unique solution, its longest"
            r" helpmate and its size, beside a chart of all its positions by distance to mate (bars),"
            r" with the number of unique solutions at each distance on a logarithmic scale (line) and"
            r" the problem's own length dotted.",
            r"Under the diagram stand the stipulation and the material count, white men plus black men."
            r" The solution is numbered in helpmate order, Black's move first. Where the position, or a"
            r" close relative, has been published as a composition, the box under the solution names the"
            r" author and sources. The \emph{solve} link in the header and the QR code open the position"
            r" in the Helpmate Analyzer (\texttt{helpman.komtera.lt}) with the stipulation already set.",
        ],
        "stats_title": "The corpus in numbers",
        "stats_intro": r"This booklet covers <classes> material classes holding <indexed> indexed positions."
                       r" The longest unique problem in the whole corpus is \textbf{<deep>} in <mat>"
                       r" (page~\pageref{hm:<mat>}).",
        "coverage_title": "Coverage",
        "coverage": r"Every material class from three to six men in which a mate can exist is solved. Both"
                    r" orders count separately --- White mates, so KRPvkb and KBvkrp are different problems"
                    r" --- which gives <comb> classes on paper. Of those, <bare> have White with nothing but"
                    r" a bare king and cannot hold a mate, leaving the <poss> counted here.",
        "coverage_head": r"men & with a unique problem & can hold a mate & share \\",
        "total": "total",
        "no_page": r"A class can be solved completely and still have no page: either no mate exists in it"
                   r" at all, or no depth in it holds a position with a single solution. Such a class has"
                   r" no unique problem to show.",
        "depth_title": "How long a unique problem gets",
        "depth": "Distribution of the longest unique length across all <classes> classes.",
        "depth_x": r"longest unique length (h\#n)", "classes": "classes",
        "gap_title": "The gap to the class maximum",
        "gap": r"How much length uniqueness costs: the class's longest helpmate minus its longest unique"
               r" one, in plies. It is never zero.",
        "gap_x": "gap (plies)",
        "gap_summary": r"Mean <mean> plies, median <median>, worst <max> --- <mat>, which runs to <maxd>"
                       r" but whose longest unique problem is only <d> (page~\pageref{hm:<mat>}).",
        "ten_title": "The ten longest",
        "ten_head": r"material & unique & class max & gap & positions \\",
        "rarity_title": "Rarity",
        "rarity": r"At its longest unique length a class may hold a single position and nothing else. <n>"
                  r" classes are like that, and <few> hold ten or fewer. Those are the positions with no"
                  r" margin at all: change one man and the problem is gone.",
        "singletons": "classes with exactly one position at their longest unique length",
        "chapters": {3: "Three men", 4: "Four men", 5: "Five men", 6: "Six men"},
        "chapter_intro": "<n> of the <poss> material classes with <men> men that can hold a mate, longest unique problem first.",
        "men": "<n> men", "white_moves": "White to move", "black_moves": "Black to move",
        "no": "No.", "solve": "solve",
        "deepest_unique": "longest unique", "unique_there": "unique at that length",
        "position": "position", "positions": "positions",
        "longest_mate": "longest mate", "in_class": "in the class",
        "class_size": r"<p> positions,\\ <h> with a helpmate",
        "solution": "solution", "scan": "scan to solve", "themes": "themes",
        "no_themes": "none detected", "note": "Note",
        "chart_x": "plies to mate", "chart_y": "positions", "chart_unique": "unique (log)",
        "chart_units": ("billions", "millions", "thousands"),
        "published": "published", "this_position": "this position",
        "related_position": "related position", "source_unknown": "source unknown",
        "quality": {
            "illegal": "the diagram has no legal last move, so it cannot arise in a game",
            "check": "the side to move is in check in the diagram",
            "capture_first": "the solution begins with a capture",
        },
        "index_title": "Index of material classes",
        "index_intro": r"Sorted by how long a unique problem gets. \emph{class max} is the longest helpmate"
                       r" in that material at any solution count.",
        "index_head": r"material & men & unique & class max & gap & published by & page \\",
        "big": ("trillion", "billion", "million", "thousand"),
        "themes_map": {
            "umnov": "Umnov", "set-play": "set play", "nocapture": "no capture", "nocheck": "no check",
            "closed-walk": "closed walk", "single-piece": "single piece", "indian": "Indian",
            "klasinc": "Klasinc", "kniest": "Kniest", "maslar": "Maslar", "zajic": "Zajic",
        },
    },
    "de": {
        "babel": "ngerman",
        "decimal": ",",
        "footer": "Längste Hilfsmatts mit maximal 6 Steinen",
        "title": r"Längste Hilfsmatts\\[0.3em] mit maximal 6 Steinen",
        "subtitle": r"Eine Aufgabe je Materialklasse:\\ das längste Hilfsmatt, das noch eine einzige Lösung hat",
        "all_classes": "Alle <n> Materialklassen von drei bis sechs Steinen",
        "generated": r"Erzeugt aus der Hilfsmatt-Tablebase.\\ Jedes Diagramm, jede Länge und jede Lösung in diesem Heft ist maschinell ermittelt.",
        "brief_title": "Die Tablebase in Kürze",
        "brief": [
            r"Ein \emph{Hilfsmatt} ist eine Schachaufgabe, in der beide Seiten zusammenarbeiten: Schwarz"
            r" zieht an und hilft Weiß, matt zu setzen. \textbf{h\#n} verlangt Matt im \(n\)-ten Zug von"
            r" Weiß; bei \textbf{h\#n.5} beginnt Weiß, die Lösung beginnt also mit \(1\ldots\) und dauert"
            r" einen Halbzug länger. \emph{Korrekt} ist eine Aufgabe nur, wenn ihre Lösung eindeutig ist:"
            r" eine zweite Lösung ist eine Nebenlösung.",
            r"Die Hilfsmatt-Tablebase löst jede legale Stellung jeder Materialklasse mit bis zu sechs"
            r" Steinen. Für jede Stellung und jedes Zugrecht speichert sie die Entfernung zum Matt bei"
            r" Zusammenarbeit und die Zahl der verschiedenen kürzesten Lösungen; eine korrekte Aufgabe ist"
            r" also einfach eine Stellung, deren Zahl eins ist.",
        ],
        "facts": {
            "classes": "Klassen in diesem Heft", "classes_v": "<n> (drei bis sechs Steine)",
            "positions": "Stellungen darin", "positions_v": "<n> (beide Zugrechte)",
            "helpmates": "Mit Hilfsmatt", "unique": "Mit eindeutiger Lösung",
            "deepest": "Längste eindeutige Aufgabe", "longest": "Längstes Hilfsmatt",
            "published": "Gefundene veröffentlichte Aufgaben",
        },
        "built": r"Die Tabellen erzeugt ein C++-Generator, der jede Klasse Tiefe um Tiefe vom Matt aus"
                 r" nach außen durcharbeitet, nachdem er zuvor jede Tabelle gebaut hat, in die ein Schlag"
                 r" oder eine Umwandlung führt. Geprüft werden sie durch einen unabhängigen Löser an"
                 r" Stichproben, durch einen vollständigen Abgleich von KQvk mit python-chess und durch die"
                 r" Forderung, dass ein Lauf auf vielen Threads Byte für Byte dieselbe Datei schreibt wie"
                 r" ein Lauf auf einem. Jede von außen beigesteuerte Tabelle durchläuft vor der"
                 r" Veröffentlichung eine Prüfung in sieben Schritten.",
        "credit": "<name> (<n> Tabellen)", "and": " und ",
        "code": "Code", "tables": "Tabellen",
        "about_title": "Urheberschaft und Mitwirkende",
        "about": [
            r"Die Hilfsmatt-Tablebase und dieses Heft sind ein Werk von <maintainer>, der das"
            r" Projekt betreut: Generator, Verifikation und Auswahl der Aufgaben.",
            r"Die meisten Sechssteiner-Tabellen haben <who> auf eigenen Rechnern berechnet; vor der"
            r" Veröffentlichung wurden sie geprüft. T31M hat außerdem den Generator und die Suche"
            r" nach Aufgaben um ein Vielfaches beschleunigt.",
        ],
        "maintainer": "Betreuer", "contributors": "Mitwirkende",
        "prior_title": "Frühere Veröffentlichungen",
        "prior": r"Die Suche nach früheren Veröffentlichungen ist nicht vollständig. Jede Stellung wurde"
                 r" mit einer Sammlung veröffentlichter Hilfsmatts abgeglichen; gefundene Treffer stehen"
                 r" auf der Seite der Aufgabe. Fehlt dort ein solcher Kasten, heißt das \emph{nicht},"
                 r" dass die Stellung unveröffentlicht ist: Für keine Stellung in diesem Heft wird"
                 r" Originalität oder Priorität beansprucht. Veröffentlichte Aufgaben bleiben geistiges"
                 r" Eigentum ihrer Autoren. Hinweise auf übersehene Vorgänger nehmen wir gern als Issue"
                 r" auf GitHub entgegen.",
        "read_title": "So liest man eine Seite",
        "read": [
            r"Jede Klasse hat eine Seite. Der \textcolor{ink}{Kopf} nennt das Material, die weißen Steine"
            r" zuerst, und die Forderung der Aufgabe. Darunter steht die Klasse im Überblick: ihre längste"
            r" eindeutige Aufgabe, wie viele Stellungen diese Länge mit eindeutiger Lösung erreichen, ihr"
            r" längstes Hilfsmatt und ihre Größe; daneben ein Schaubild aller ihrer Stellungen nach"
            r" Entfernung zum Matt (Balken), mit der Zahl der eindeutigen Lösungen je Entfernung auf"
            r" logarithmischer Skala (Linie) und der Länge der Aufgabe selbst gepunktet.",
            r"Unter dem Diagramm stehen die Forderung und die Steinzahl, weiße plus schwarze Steine. Die"
            r" Lösung ist in Hilfsmatt-Reihenfolge nummeriert, der schwarze Zug zuerst. Ist die Stellung"
            r" oder eine nahe Verwandte als Komposition veröffentlicht, nennt der Kasten unter der Lösung"
            r" Autor und Quellen. Der Link \emph{lösen} im Kopf und der QR-Code öffnen die Stellung im"
            r" Helpmate Analyzer (\texttt{helpman.komtera.lt}) mit bereits gesetzter Forderung.",
        ],
        "stats_title": "Der Bestand in Zahlen",
        "stats_intro": r"Dieses Heft umfasst <classes> Materialklassen mit <indexed> indizierten Stellungen."
                       r" Die längste eindeutige Aufgabe des ganzen Bestands ist \textbf{<deep>} in <mat>"
                       r" (Seite~\pageref{hm:<mat>}).",
        "coverage_title": "Abdeckung",
        "coverage": r"Jede Materialklasse von drei bis sechs Steinen, in der ein Matt möglich ist, ist"
                    r" gelöst. Beide Seitenverteilungen zählen getrennt -- Weiß setzt matt, also sind"
                    r" KRPvkb und KBvkrp verschiedene Aufgaben --, das ergibt auf dem Papier <comb> Klassen."
                    r" Davon haben <bare> auf weißer Seite nur den nackten König und können kein Matt"
                    r" enthalten; es bleiben die hier gezählten <poss>.",
        "coverage_head": r"Steine & mit eindeutiger Aufgabe & Matt möglich & Anteil \\",
        "total": "gesamt",
        "no_page": r"Eine Klasse kann vollständig gelöst sein und trotzdem keine Seite haben: entweder"
                   r" gibt es in ihr überhaupt kein Matt, oder keine Tiefe enthält eine Stellung mit nur"
                   r" einer Lösung. Eine solche Klasse hat keine eindeutige Aufgabe zu zeigen.",
        "depth_title": "Wie lang eine eindeutige Aufgabe wird",
        "depth": "Verteilung der größten eindeutigen Länge über alle <classes> Klassen.",
        "depth_x": r"größte eindeutige Länge (h\#n)", "classes": "Klassen",
        "gap_title": "Der Abstand zum Klassenmaximum",
        "gap": r"Was Eindeutigkeit an Länge kostet: das längste Hilfsmatt der Klasse minus ihre längste"
               r" eindeutige Aufgabe, in Halbzügen. Er ist nie null.",
        "gap_x": "Abstand (Halbzüge)",
        "gap_summary": r"Mittel <mean> Halbzüge, Median <median>, größter <max> -- <mat>, das bis <maxd>"
                       r" reicht, dessen längste eindeutige Aufgabe aber nur <d> ist"
                       r" (Seite~\pageref{hm:<mat>}).",
        "ten_title": "Die zehn längsten",
        "ten_head": r"Material & eindeutig & Klassenmax. & Abstand & Stellungen \\",
        "rarity_title": "Seltenheit",
        "rarity": r"In ihrer größten eindeutigen Länge kann eine Klasse eine einzige Stellung enthalten und"
                  r" sonst nichts. <n> Klassen sind so, und <few> enthalten zehn oder weniger. Das sind die"
                  r" Stellungen ganz ohne Spielraum: ein Stein anders, und die Aufgabe ist dahin.",
        "singletons": "Klassen mit genau einer Stellung in ihrer größten eindeutigen Länge",
        "chapters": {3: "Drei Steine", 4: "Vier Steine", 5: "Fünf Steine", 6: "Sechs Steine"},
        "chapter_intro": "<n> der <poss> Materialklassen mit <men> Steinen, in denen ein Matt möglich ist, längste eindeutige Aufgabe zuerst.",
        "men": "<n> Steine", "white_moves": "Weiß am Zug", "black_moves": "Schwarz am Zug",
        "no": "Nr.", "solve": "lösen",
        "deepest_unique": "längste eindeutige", "unique_there": "eindeutig bei dieser Länge",
        "position": "Stellung", "positions": "Stellungen",
        "longest_mate": "längstes Matt", "in_class": "in der Klasse",
        "class_size": r"<p> Stellungen,\\ <h> mit Hilfsmatt",
        "solution": "Lösung", "scan": "scannen zum Lösen", "themes": "Themen",
        "no_themes": "keine erkannt", "note": "Hinweis",
        "chart_x": "Halbzüge bis Matt", "chart_y": "Stellungen", "chart_unique": "eindeutig (log)",
        "chart_units": ("Mrd.", "Mio.", "Tsd."),
        "published": "veröffentlicht", "this_position": "diese Stellung",
        "related_position": "verwandte Stellung", "source_unknown": "Quelle unbekannt",
        "quality": {
            "illegal": "das Diagramm hat keinen legalen letzten Zug, kann also in keiner Partie entstehen",
            "check": "die Partei am Zug steht im Diagramm im Schach",
            "capture_first": "die Lösung beginnt mit einem Schlag",
        },
        "index_title": "Verzeichnis der Materialklassen",
        "index_intro": r"Sortiert nach der Länge der eindeutigen Aufgabe. \emph{Klassenmax.} ist das längste"
                       r" Hilfsmatt in diesem Material bei beliebiger Lösungszahl.",
        "index_head": r"Material & Steine & eindeutig & Klassenmax. & Abstand & veröffentlicht von & Seite \\",
        "big": ("Billionen", "Milliarden", "Millionen", "Tausend"),
        "themes_map": {
            "set-play": "Satzspiel", "pure": "reines Matt", "model": "Mustermatt", "ideal": "Idealmatt",
            "mirror": "Spiegelmatt", "promotion": "Umwandlung", "underpromotion": "Unterverwandlung",
            "excelsior": "Excelsior", "switchback": "Switchback", "closed-walk": "Rundlauf",
            "umnov": "Umnov", "nocapture": "ohne Schlag", "nocheck": "ohne Schach",
            "self-block": "Selbstblock", "single-piece": "ein Stein zieht", "indian": "Inder",
            "klasinc": "Klasinc", "kniest": "Kniest", "maslar": "Maslar", "pendulum": "Pendel",
            "phoenix": "Phönix", "zajic": "Zajic",
        },
    },
    "fr": {
        "babel": "french",
        "decimal": ",",
        "footer": "Les plus longs mats aidés jusqu'à six pièces",
        "title": r"Les plus longs mats aidés\\[0.3em] jusqu'à six pièces",
        "subtitle": r"Un problème par classe de matériel:\\ le plus long mat aidé qui n'a encore qu'une seule solution",
        "all_classes": "Les <n> classes de matériel de trois à six pièces",
        "generated": r"Tiré de la base de mats aidés.\\ Chaque diagramme, longueur et solution de ce livret est calculé par machine.",
        "brief_title": "La base en bref",
        "brief": [
            r"Un \emph{mat aidé} est un problème d'échecs où les deux camps coopèrent: les Noirs jouent"
            r" d'abord et aident les Blancs à mater. \textbf{h\#n} demande le mat au \(n\)\textsuperscript{e}"
            r" coup blanc; dans \textbf{h\#n.5} les Blancs commencent, la solution s'ouvre donc par"
            r" \(1\ldots\) et dure un demi-coup de plus. Un problème n'est \emph{correct} que si sa"
            r" solution est unique: une seconde solution le démolit.",
            r"La base de mats aidés (\emph{tablebase}) résout toutes les positions légales de toutes les"
            r" classes de matériel jusqu'à six pièces. Pour chaque position et chaque trait, elle"
            r" enregistre la distance au mat en coopération et le nombre de solutions les plus courtes"
            r" distinctes; un problème correct est donc simplement une position dont ce nombre vaut un.",
        ],
        "facts": {
            "classes": "Classes dans ce livret", "classes_v": "<n> (trois à six pièces)",
            "positions": "Positions", "positions_v": "<n> (les deux traits)",
            "helpmates": "Avec un mat aidé", "unique": "Avec une solution unique",
            "deepest": "Problème unique le plus long", "longest": "Mat aidé le plus long",
            "published": "Compositions publiées trouvées",
        },
        "built": r"Les tables sont produites par un générateur C++ qui traite chaque classe profondeur par"
                 r" profondeur, des mats vers l'extérieur, après avoir construit toutes les tables"
                 r" auxquelles mène une prise ou une promotion. Elles sont vérifiées par un solveur"
                 r" indépendant sur des positions tirées au hasard, par une comparaison exhaustive de KQvk"
                 r" avec python-chess, et par l'exigence qu'un calcul sur de nombreux threads écrive octet"
                 r" pour octet le même fichier qu'un calcul sur un seul. Toute table fournie de"
                 r" l'extérieur passe une vérification en sept étapes avant d'être publiée.",
        "credit": "<name> (<n> tables)", "and": " et ",
        "code": "Code", "tables": "Tables",
        "about_title": "Paternité et contributions",
        "about": [
            r"La base de mats aidés et ce livret sont l'œuvre de <maintainer>, qui maintient le"
            r" projet: le générateur, la vérification et le choix des problèmes.",
            r"La plupart des tables à six pièces ont été calculées par <who> sur leurs propres"
            r" machines, puis vérifiées avant publication. T31M a en outre rendu le générateur et la"
            r" recherche de problèmes beaucoup plus rapides.",
        ],
        "maintainer": "Mainteneur", "contributors": "Contributeurs",
        "prior_title": "Publications antérieures",
        "prior": r"La recherche de publications antérieures n'est pas exhaustive. Chaque position a été"
                 r" comparée à une collection de mats aidés publiés, et les correspondances trouvées sont"
                 r" indiquées sur la page du problème. L'absence d'un tel cadre ne signifie \emph{pas}"
                 r" que la position est inédite: aucune originalité ni priorité n'est revendiquée pour"
                 r" les positions de ce livret. Les problèmes publiés restent la propriété intellectuelle"
                 r" de leurs auteurs. Les publications antérieures qui nous auraient échappé peuvent être"
                 r" signalées par une issue sur GitHub.",
        "read_title": "Comment lire une page",
        "read": [
            r"Chaque classe a sa page. L'\textcolor{ink}{en-tête} donne le matériel, les pièces blanches"
            r" d'abord, et l'énoncé du problème. Vient ensuite la classe en un coup d'œil: son problème"
            r" unique le plus long, le nombre de positions qui atteignent cette longueur avec une"
            r" solution unique, son plus long mat aidé et sa taille, à côté d'un graphique de toutes ses"
            r" positions selon la distance au mat (barres), avec le nombre de solutions uniques à chaque"
            r" distance sur une échelle logarithmique (ligne) et la longueur du problème en pointillé.",
            r"Sous le diagramme figurent l'énoncé et le nombre de pièces, blanches plus noires. La"
            r" solution est numérotée dans l'ordre du mat aidé, le coup noir d'abord. Si la position, ou"
            r" une proche parente, a été publiée comme composition, le cadre sous la solution en indique"
            r" l'auteur et les sources. Le lien \emph{résoudre} de l'en-tête et le code QR ouvrent la"
            r" position dans le Helpmate Analyzer (\texttt{helpman.komtera.lt}), l'énoncé déjà réglé.",
        ],
        "stats_title": "Le corpus en chiffres",
        "stats_intro": r"Ce livret couvre <classes> classes de matériel totalisant <indexed> positions"
                       r" indexées. Le problème unique le plus long de tout le corpus est"
                       r" \textbf{<deep>} en <mat> (page~\pageref{hm:<mat>}).",
        "coverage_title": "Couverture",
        "coverage": r"Toutes les classes de matériel de trois à six pièces dans lesquelles un mat peut"
                    r" exister sont résolues. Les deux répartitions comptent séparément --- les Blancs"
                    r" matent, donc KRPvkb et KBvkrp sont des problèmes différents ---, ce qui donne <comb>"
                    r" classes sur le papier. Parmi elles, <bare> n'ont que le roi blanc seul et ne peuvent"
                    r" contenir aucun mat; restent les <poss> comptées ici.",
        "coverage_head": r"pièces & avec problème unique & mat possible & part \\",
        "total": "total",
        "no_page": r"Une classe peut être entièrement résolue et n'avoir pourtant aucune page: soit aucun"
                   r" mat n'y existe, soit aucune longueur n'y contient de position à solution unique."
                   r" Une telle classe n'a pas de problème unique à montrer.",
        "depth_title": "Quelle longueur atteint un problème unique",
        "depth": "Répartition de la plus grande longueur unique sur les <classes> classes.",
        "depth_x": r"plus grande longueur unique (h\#n)", "classes": "classes",
        "gap_title": "L'écart au maximum de la classe",
        "gap": r"Ce que coûte l'unicité en longueur: le plus long mat aidé de la classe moins son"
               r" problème unique le plus long, en demi-coups. Il n'est jamais nul.",
        "gap_x": "écart (demi-coups)",
        "gap_summary": r"Moyenne <mean> demi-coups, médiane <median>, maximum <max> --- <mat>, qui va"
                       r" jusqu'à <maxd> mais dont le problème unique le plus long n'est que <d>"
                       r" (page~\pageref{hm:<mat>}).",
        "ten_title": "Les dix plus longs",
        "ten_head": r"matériel & unique & max. classe & écart & positions \\",
        "rarity_title": "Rareté",
        "rarity": r"À sa plus grande longueur unique, une classe peut ne contenir qu'une seule"
                  r" position. <n> classes sont dans ce cas, et <few> en contiennent dix ou moins. Ce sont"
                  r" les positions sans aucune marge: changez une pièce et le problème disparaît.",
        "singletons": "classes ayant exactement une position à leur plus grande longueur unique",
        "chapters": {3: "Trois pièces", 4: "Quatre pièces", 5: "Cinq pièces", 6: "Six pièces"},
        "chapter_intro": "<n> des <poss> classes de matériel à <men> pièces pouvant contenir un mat, le problème unique le plus long d'abord.",
        "men": "<n> pièces", "white_moves": "trait aux Blancs", "black_moves": "trait aux Noirs",
        "no": "nº", "solve": "résoudre",
        "deepest_unique": "unique le plus long", "unique_there": "uniques à cette longueur",
        "position": "position", "positions": "positions",
        "longest_mate": "mat le plus long", "in_class": "dans la classe",
        "class_size": r"<p> positions,\\ <h> avec mat aidé",
        "solution": "solution", "scan": "scanner pour résoudre", "themes": "thèmes",
        "no_themes": "aucun détecté", "note": "Remarque",
        "chart_x": "demi-coups jusqu'au mat", "chart_y": "positions", "chart_unique": "uniques (log)",
        "chart_units": ("milliards", "millions", "milliers"),
        "published": "publié", "this_position": "cette position",
        "related_position": "position apparentée", "source_unknown": "source inconnue",
        "quality": {
            "illegal": "le diagramme n'a pas de dernier coup légal, il ne peut donc pas survenir dans une partie",
            "check": "le camp au trait est en échec dans le diagramme",
            "capture_first": "la solution commence par une prise",
        },
        "index_title": "Index des classes de matériel",
        "index_intro": r"Trié selon la longueur du problème unique. \emph{max. classe} est le plus long"
                       r" mat aidé de ce matériel, quel que soit le nombre de solutions.",
        "index_head": r"matériel & pièces & unique & max. classe & écart & publié par & page \\",
        "big": ("billions", "milliards", "millions", "milliers"),
        "themes_map": {
            "set-play": "jeu apparent", "pure": "mat pur", "model": "mat modèle", "ideal": "mat idéal",
            "mirror": "mat miroir", "promotion": "promotion", "underpromotion": "sous-promotion",
            "excelsior": "Excelsior", "switchback": "aller-retour", "closed-walk": "circuit",
            "umnov": "Umnov", "nocapture": "sans prise", "nocheck": "sans échec",
            "self-block": "auto-blocage", "single-piece": "pièce unique", "indian": "indien",
            "klasinc": "Klasinc", "kniest": "Kniest", "maslar": "Maslar", "pendulum": "pendule",
            "phoenix": "phénix", "zajic": "Zajic",
        },
    },
}
