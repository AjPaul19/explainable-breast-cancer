"""Smoke test of the REAL site content, against a Playground that activated the plugin and theme (tools/blueprint-real.json).
Checks every page renders, the real facts are present, nothing placeholder or internal leaks, every internal link works and
no section has more than two buttons. Run:  python tools/smoke_real.py [port]
"""
import re
import sys
import urllib.request
import urllib.parse

PORT = sys.argv[1] if len(sys.argv) > 1 else "9420"
BASE = f"http://127.0.0.1:{PORT}"
fails = []
total = 0


def get(path):
    req = urllib.request.Request(path if path.startswith("http") else BASE + path, headers={"User-Agent": "smoke"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, r.read().decode("utf8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""


def check(name, cond, detail=""):
    global total
    total += 1
    if not cond:
        print("FAIL " + name + (" :: " + str(detail) if detail else ""))
        fails.append(name)


STRATEGIES = ["campus-student-led-movements", "prayer", "digital-strategies", "familylife", "jesus-film-project", "leaderimpact", "priority-associates-nigeria",
              "global-church-movements", "agape-humanitarian-aid-foundation", "police-and-military-ministry", "athletes-in-action", "bethany-christian-academy",
              "acts-ilu", "operations", "ldhr", "fund-development"]
STORIES = ["buddhism-to-christianity", "judaism-to-christianity", "mormonism-to-christianity", "islam-to-christianity", "atheism-to-christianity"]
RESOURCES = ["five-things-to-live-the-life-god-intended", "five-spiritual-disciplines", "the-four-spiritual-laws", "apps-and-tools"]
PAGES = ["/", "/who-we-are/", "/who-we-are/our-values/", "/who-we-are/statement-of-faith/", "/who-we-are/our-history/", "/what-we-do/", "/giving/",
         "/partnership/", "/serve/", "/contact/", "/how-to-know-god/", "/train-and-grow/", "/ministries/", "/opportunities/", "/about-us/", "/need-prayer/", "/talk-to-a-mentor/", "/train-and-grow/spiritual-growth/", "/train-and-grow/bible-studies/", "/train-and-grow/life-and-relationships/", "/train-and-grow/share-the-gospel/", "/train-and-grow/help-others-grow/", "/train-and-grow/leadership-training/", "/opportunities/internship-programme/", "/opportunities/internship-application/", "/opportunities/reference-questionnaire/", "/strategies/", "/stories/", "/resources/", "/news/", "/gcmn-marks-50-years/"]
import json
import os
BUNDLE = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gcmn-core", "content", "gcmn-content.json"), encoding="utf8"))
MIRROR_PAGES = ["/" + (p.get("path") or p["slug"]) + "/" for p in BUNDLE["pages"] if p.get("mirror")]
MIRROR_STORIES = ["/stories/" + i["slug"] + "/" for i in BUNDLE["items"] if i["type"] == "gcmn_story" and i.get("mirror")]
PAGES += [p for p in MIRROR_PAGES if p not in PAGES] + MIRROR_STORIES
PAGES += [f"/strategies/{s}/" for s in STRATEGIES] + [f"/stories/{s}/" for s in STORIES] + [f"/resources/{s}/" for s in RESOURCES]

BAD = re.compile(r"(Fatal error|Parse error|Warning: |Notice: |Deprecated: |Uncaught |Stack trace)")
FILLER = re.compile(r"(lorem ipsum|content slot|needs approved content|content owner|owned by|last reviewed|next review|dummy|placeholder|test tagline|sample page|hello world)", re.I)
STALE = re.compile(r"(Pray2020|by the end of 2020|10 ?million multiplying disciples by 2020)", re.I)

html = {}
links = set()
for p in PAGES:
    code, body = get(p)
    html[p] = body
    check(f"{p} returns 200", code == 200, code)
    check(f"{p} has no PHP errors", not BAD.search(body))
    check(f"{p} has no filler or internal text", not FILLER.search(body), FILLER.search(body).group(0) if FILLER.search(body) else "")
    check(f"{p} has no outdated 2020 targets", p in MIRROR_PAGES or p in MIRROR_STORIES or not STALE.search(body))
    for m in re.finditer(r'href="([^"#]+)"', body):
        u = m.group(1)
        if u.startswith(BASE):
            links.add(u)
        elif u.startswith("/") and not u.startswith("//"):
            links.add(BASE + u)

home = html["/"]
check("hero shows the tagline", "Win. Build. Send." in home)
check("the site is named after the organisation", "Great Commission Movement of Nigeria" in home and "My WordPress Website" not in home)
for n in ("89", "29", "170", "1969"):
    check(f"home shows the number {n}", f'>{n}<' in home.replace(" ", ""), n)
SECTIONS = ("How to know God", "Train and grow", "Ministries", "Opportunities", "About us", "Give", "Need prayer", "Talk to a mentor")
tiles = home.split("g-tiles", 1)[1] if "g-tiles" in home else ""
for label in SECTIONS:
    check(f"home has a tile for {label}", f">{label}<" in tiles, label)
check("home has exactly eight tiles", len(re.findall(r'class="[^"]*(?<![-\w])g-tile(?![-\w])', home)) == 8)
check("hero has one action", len(re.findall(r'class="[^"]*(?<![-\w])g-cta(?![-\w])', home)) == 1)
nav = home.split('class="nav-list"')[1].split("</nav>")[0] if 'class="nav-list"' in home else ""
for label in SECTIONS:
    check(f"main menu has {label}", f">{label}<" in nav, label)
check("menu has drop-downs for the five content sections", nav.count("has-sub") >= 5)
check("Give is the highlighted menu item", "g-nav-give" in nav)
sheet = home.split('id="menu-sheet"')[1].split("</nav>")[0] if 'id="menu-sheet"' in home else ""
for label in ("Four Spiritual Laws", "Bible Studies", "Jesus Film Project", "Internship application", "Statement of faith"):
    check(f"phone menu lists {label}", f">{label}<" in sheet, label)
for p, want in (("/how-to-know-god/", "Four Spiritual Laws"), ("/train-and-grow/", "Bible Studies"), ("/ministries/", "Jesus Film Project"), ("/opportunities/", "Internship"), ("/about-us/", "Statement of faith")):
    check(f"{p} hub lists {want}", want in html[p], want)
for p in ("/need-prayer/", "/talk-to-a-mentor/"):
    check(f"{p} has the request form", 'name="topic"' in html[p] and 'name="message"' in html[p] and 'name="email"' in html[p] and 'name="name"' in html[p])
check("the Four Spiritual Laws page is linked from the first section", "/resources/the-four-spiritual-laws/" in html["/how-to-know-god/"])
check("give page shows the accounts before the long text", html["/giving/"].find("0003805731") != -1 and html["/giving/"].find("0003805731") < html["/giving/"].find("Why we ask you"))
check("pages carry Elementor-ready layout classes", all("g-screen" in html[p] for p in ("/", "/ministries/", "/giving/", "/need-prayer/")))
check("footer links to the Facebook page", "facebook.com/gcmnig" in home)
check("footer shows the phone and email", "+234 810 003 9399" in home and "info@gcmnigeria.org" in home)

check("giving shows both accounts", "0003805731" in html["/giving/"] and "0025707701" in html["/giving/"])
check("giving explains why staff raise support", "no central funds" in html["/giving/"])
check("contact lists the national office address and state offices", "10 Secretariat Road" in html["/contact/"] and "Maiduguri" in html["/contact/"] and 'name="topic"' in html["/contact/"])
check("who-we-are carries the mission and founders", "Win, Build and Send" in html["/who-we-are/"] and "Yemi and Sue Ladipo" in html["/who-we-are/"])
check("statement of faith has its 16 articles", html["/who-we-are/statement-of-faith/"].count("<li>") >= 16, html["/who-we-are/statement-of-faith/"].count("<li>"))
check("values lists Faith, Growth and Fruitfulness", all(w in html["/who-we-are/our-values/"] for w in ("Faith", "Growth", "Fruitfulness")))
check("history reaches 1969 and 1997", "1969" in html["/who-we-are/our-history/"] and "1997" in html["/who-we-are/our-history/"])
check("strategies page shows all 16", html["/strategies/"].count('class="card card-') == 16, html["/strategies/"].count('class="card card-'))
check("strategy cards have photos", html["/strategies/"].count("card-img") >= 15, html["/strategies/"].count("card-img"))
check("jesus film shows the highest language count", "170" in html["/strategies/jesus-film-project/"] and "145" not in html["/strategies/jesus-film-project/"])
check("prayer page invites a prayer request", "topic=prayer" in html["/strategies/prayer/"])
check("fonts are self-hosted", "fonts.googleapis.com" not in home)

sections = re.split(r"<(?:section|footer)\b", home)
check("no home section has more than 2 buttons", max(len(re.findall(r'class="[^"]*(?<![-\w])btn(?![-\w])', s)) for s in sections) <= 2)
check("header has only the menu button", len(re.findall(r'class="[^"]*(?<![-\w])btn(?![-\w])', home.split("</header>")[0])) == 0)

dead = []
for u in sorted(links):
    if re.search(r"\.(css|js|png|jpe?g|woff2|webp|gif|ico)(\?|$)", u) or "wp-json" in u or "xmlrpc" in u or "wp-login" in u or "feed" in u or "oembed" in u or "wp-admin" in u:
        continue
    code, _ = get(u)
    if code >= 400:
        dead.append((u.replace(BASE, ""), code))
check("every internal link works", not dead, dead[:8])

print(f"\n{total} checks, {len(fails)} failed, {len(links)} internal links followed")
sys.exit(1 if fails else 0)
