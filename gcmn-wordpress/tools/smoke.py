"""Smoke test against a running Playground (http://127.0.0.1:9410) that has the test fixture imported.
Checks that every template renders, no PHP errors leak, rules hold (<= 2 buttons per section, no internal ownership text),
and that expired items are gone. Run:  python tools/smoke.py
"""
import re
import sys
import urllib.request

BASE = "http://127.0.0.1:9410"
fails = []


def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "smoke"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf8", "replace")


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (" :: " + detail if detail and not cond else ""))
    if not cond:
        fails.append(name)


PAGES = ["/", "/who-we-are/", "/giving/", "/partnership/", "/serve/", "/contact/", "/strategies/", "/stories/", "/events/",
         "/resources/", "/prayer/", "/partner/opportunities/", "/news/", "/strategies/test-strategy/", "/stories/test-story/",
         "/events/test-event/", "/resources/test-resource/", "/prayer/test-prayer/", "/partner/opportunities/test-opportunity/",
         "/test-news/", "/this-page-does-not-exist/"]
BAD = re.compile(r"(Fatal error|Parse error|Warning:|Notice:|Deprecated:|Uncaught|Stack trace)", re.I)
OWNER_WORDS = re.compile(r"(content owner|owned by|last reviewed|next review|needs approved content|content slot|lorem ipsum)", re.I)

html = {}
for p in PAGES:
    code, body = get(p)
    html[p] = body
    want = 404 if "does-not-exist" in p else 200
    check(f"{p} returns {want}", code == want, str(code))
    check(f"{p} has no PHP errors", not BAD.search(body), (BAD.search(body) or [""])[0] if BAD.search(body) else "")
    check(f"{p} shows no ownership or filler text", not OWNER_WORDS.search(body), OWNER_WORDS.search(body).group(0) if OWNER_WORDS.search(body) else "")

home = html["/"]
check("home shows the imported tagline", "Test tagline for the smoke test" in home)
check("home numbers: complete line shown", "Test things counted" in home)
check("home numbers: line without a source is hidden", "Missing source line" not in home)
check("past event is not listed", "Past Event" not in html["/events/"] and "Past Event" not in home)
check("upcoming event is listed", "Test Event" in html["/events/"])
check("giving page shows the account", "0000000000" in html["/giving/"] and "Copy account number" not in html["/giving/"])
check("contact page shows the form and details", "gcmn_enquiry" in html["/contact/"] and "test@example.org" in html["/contact/"])
check("fonts are self-hosted (no external font host)", "fonts.googleapis.com" not in home and "fonts.gstatic.com" not in home)
check("WordPress sample content is gone", "Hello world" not in home and "Sample Page" not in home)
check("one stylesheet from the theme loads", "assets/css/theme.css" in home)

# at most two buttons per section on the home page
sections = re.split(r"<(?:section|footer)\b", home)
worst = 0
for s in sections:
    n = len(re.findall(r'class="[^"]*(?<![-\w])btn(?![-\w])', s))
    worst = max(worst, n)
check("no home section has more than 2 buttons", worst <= 2, str(worst))
check("the header has only the menu button", len(re.findall(r'class="[^"]*(?<![-\w])btn(?![-\w])', home.split("</header>")[0])) == 0 and "menu-btn" in home)


# strict design rule: with the Menu button, no screen offers more than two actions
BTN = re.compile(r'class="[^"]*(?<![-\w])btn(?![-\w])')
for p in PAGES:
    body = html[p].split("</header>", 1)[-1].split("<footer", 1)[0]
    n = len(BTN.findall(body))
    check(f"{p} offers at most one extra action beside the menu", n <= 1 or p in ("/contact/", "/"), str(n))

# search engine optimisation
check("home has a meta description", re.search(r'<meta name="description" content="[^"]{20,}', home) is not None)
check("home has Open Graph and Twitter tags", 'property="og:title"' in home and 'name="twitter:card"' in home and 'property="og:image"' in home)
check("home has a canonical link", 'rel="canonical"' in home)
check("home has Organization and WebSite structured data", '"@type":"Organization"' in home and '"@type":"WebSite"' in home)
for p, want in (("/strategies/test-strategy/", "BreadcrumbList"), ("/events/test-event/", "\"@type\":\"Event\""), ("/contact/", "ContactPage")):
    check(f"{p} has {want} structured data", want in html[p])
check("404 page is not indexed", "noindex" in html["/this-page-does-not-exist/"])
code, sm = get("/wp-sitemap.xml")
check("sitemap exists", code == 200 and "<sitemapindex" in sm)
code, rb = get("/robots.txt")
check("robots.txt points to the sitemap", "Sitemap:" in rb)
for p in PAGES:
    if "does-not-exist" in p:
        continue
    check(f"{p} has exactly one h1", len(re.findall(r"<h1\b", html[p])) == 1)
    check(f"{p} images all have alt text", all(re.search(r'\balt="', i) for i in re.findall(r"<img\b[^>]*>", html[p])))

print("\n%d failed" % len(fails))
sys.exit(1 if fails else 0)
