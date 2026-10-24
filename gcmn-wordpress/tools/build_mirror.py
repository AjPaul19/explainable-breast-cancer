"""Turn the extracted offline copy of the old site (tools/_mirror/mirror.json) into pages of the content bundle.

Run order:  mirror_extract.py  ->  build_content.py  ->  build_sections.py  ->  build_mirror.py   (or: python tools/build_all.py)
Adds to gcmn-core/content/gcmn-content.json:
  - every real page of the old site as a page (same path as before, so old links and search results keep working),
  - the personal testimonies as Stories,
  - menus with drop-downs and sub-drop-downs,
  - "redirects" from every old address to the new one.
Pages already written by hand in build_content.py (who-we-are, giving, partnership ...) keep their text; the matching old
addresses redirect to them. Always run build_sections.py first: this step edits the pages that one writes.
"""
import hashlib
import html
import json
import os
import posixpath
import re
import sys

sys.path.append(r"C:\Users\Segun\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\site-packages")
from PIL import Image  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MIRROR = r"C:\My Web Sites\Indigitous"
SRC = json.load(open(os.path.join(HERE, "_mirror", "mirror.json"), encoding="utf8"))
BUNDLE = os.path.join(ROOT, "gcmn-core", "content", "gcmn-content.json")
MEDIA = os.path.join(ROOT, "gcmn-core", "content", "media")
B = json.load(open(BUNDLE, encoding="utf8"))

# ---------------------------------------------------------------- what the hand-written pages stand for
CURATED = {  # old path -> new address (slug path, or strategies/..., stories/..., resources/...)
    "/en/about": "who-we-are", "/en/about/our-mission-in-nigeria": "who-we-are", "/en/about/storeorder": "who-we-are",
    "/en/about/values": "who-we-are/our-values", "/en/about/statement-of-faith": "who-we-are/statement-of-faith",
    "/en/about/what-we-do": "what-we-do", "/en/50th-anniversary": "who-we-are/our-history", "/en/about/contact-us": "contact",
    "/en/givetoharvest": "giving", "/en/opportunities/join": "serve", "/en/ministries/opportunity-for-involvement": "serve",
    "/en/talk-to-mentor": "talk-to-a-mentor", "/en/need-prayer": "need-prayer", "/en/ng": "who-we-are",
    "/en/how-to-know-god/would-you-like-to-know-god-personally": "resources/the-four-spiritual-laws",
    "/en/how-to-know-god/kgp-archive": "resources/the-four-spiritual-laws",
    "/en/train-and-grow/spiritual-growth/5-spiritual-disciplines-to-help-grow-your-walk-with-god": "resources/five-spiritual-disciplines",
    "/en/train-and-grow/spiritual-growth/5-things-you-need-to-live-the-life-god-intended": "resources/five-things-to-live-the-life-god-intended",
    "/en/digitalministry/apps-tools": "resources/apps-and-tools",
    "/en/ministries/campus": "strategies/campus-student-led-movements", "/en/ministries/prayer": "strategies/prayer",
    "/en/ministries/digital-ministry": "strategies/digital-strategies", "/en/digitalministry": "strategies/digital-strategies",
    "/en/ministries/familylife": "strategies/familylife", "/en/ministries/family-life": "strategies/familylife",
    "/en/ministries/the-jesus-film-project": "strategies/jesus-film-project", "/en/ministries/leaderimpact": "strategies/leaderimpact",
    "/en/ministries/priority-associates": "strategies/priority-associates-nigeria", "/en/ministries/globa-church": "strategies/global-church-movements",
    "/en/ministries/ahaf": "strategies/agape-humanitarian-aid-foundation", "/en/ministries/police-and-military-ministry": "strategies/police-and-military-ministry",
    "/en/ministries/athletes-in-action": "strategies/athletes-in-action", "/en/ministries/bca": "strategies/bethany-christian-academy",
    "/en/ministries/acts-ilu": "strategies/acts-ilu", "/en/ministries/operations": "strategies/operations", "/en/ministries/ldhr": "strategies/ldhr",
    "/en/ministries/fund-development": "strategies/fund-development", "/en/campus": "strategies/campus-student-led-movements",
    "/en/how-to-know-god/buddhism-to-christianity": "stories/buddhism-to-christianity", "/en/how-to-know-god/judaism-to-christianity": "stories/judaism-to-christianity",
    "/en/how-to-know-god/judaism-to-christianity1": "stories/judaism-to-christianity", "/en/how-to-know-god/mormonism-to-christianity": "stories/mormonism-to-christianity",
    "/en/how-to-know-god/islam-to-christianity": "stories/islam-to-christianity",
    "/en/how-to-know-god/my-story-a-life-changed/my-story-de-winget": "stories/atheism-to-christianity",
    "/en/ministries": "ministries", "/en/opportunities": "opportunities",
    "/en/opportunities/gcmn-intership": "opportunities/internship-application",
    "/en/opportunities/internship-reference-form": "opportunities/reference-questionnaire",
    "/en/opportunities/internships": "opportunities/internship-programme",
}
# pages that are the same text in another place: the preferred path is kept, the others redirect to it
PREFER = ["/en/train-and-grow/", "/en/digitalministry/", "/en/how-to-know-god/", "/en/blog/", "/en/ministries/", "/en/training"]
DROP_TITLES = {"404", "null", "page1", "Investment Form", "Student DO2020", "Pledge"}
ALWAYS_DROP = re.compile(r"(/en/page1|\.\d$|\.html\s*$|/en/cru17|/10-the-new-testament\.5$|/personal-guide-to-fasting\.9$|/who-is-jesus-god-or-just-a-good-man/who-is-jesus)")
# hand-written pages the mirror versions replace
SUPERSEDED = {"how-to-know-god", "life-questions", "common-questions", "train-and-grow", "spiritual-growth", "bible-studies", "life-and-relationships",
              "share-the-gospel", "help-others-grow", "leadership-training"}
STORY_DIR = "/en/how-to-know-god/my-story-a-life-changed/"
tops = {"how-to-know-god", "train-and-grow", "ministries", "opportunities", "about-us"}
NAV_ORDER = {"train-and-grow": ["spiritual-growth", "life-and-relationships", "bible-studies", "share-the-gospel", "help-others-grow", "leadership-training",
                                "language-resources", "transferable-concepts", "10-basic-steps", "discover-god", "core-essentials", "classic-cru", "email-series-sign-up", "articles"]}
DEPT = {"how-to-know-god": "Campus (Student-Led Movements)", "train-and-grow": "Leadership Development and Human Resource (LDHR)",
        "digitalministry": "Digital Strategies", "blog": "Communications", "about": "Leadership", "opportunities": "Leadership Development and Human Resource (LDHR)",
        "ministries": "Leadership", "communities": "Communications"}
JUNK = re.compile(r"^(download|load comments|comments|previous story|next story|related topics:?|share( this)?|print|subscribe|sign up|watch|listen)\b", re.I)


def plain(s):
    s = re.sub(r"\[\[img:[^\]]*\]\]", " ", s)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def clean_path(p):
    p = p.split("#")[0].split("?")[0]
    p = re.sub(r"^/content/gcmnigeria/ng", "", p)
    p = re.sub(r"\.html$", "", p)
    return p.rstrip("/") or "/"


def resolve(href, base_path):
    """Make an href from the mirror into either a site path (/en/...), or an external URL."""
    if not href or href.startswith(("mailto:", "tel:", "#", "javascript:")):
        return href
    if re.match(r"https?://(www\.)?gcmnigeria\.org", href):
        return clean_path(re.sub(r"^https?://(www\.)?gcmnigeria\.org", "", href))
    if re.match(r"https?://", href):
        return href
    base = "/gcmnigeria.org" + base_path + ".html"
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(base), href.split("#")[0].split("?")[0]))
    m = re.match(r"^/(www\.gcmnigeria\.org|gcmnigeria\.org)(/.*)?$", joined)
    if m:
        return clean_path(m.group(2) or "/")
    m = re.match(r"^/([^/]+\.[a-z]{2,})(/.*)?$", joined)
    if m:
        return "https://" + m.group(1) + (m.group(2) or "")
    return clean_path(joined)


def real(v):
    if v["title"] in DROP_TITLES or not v["title"]:
        return False
    if v["words"] >= 40:
        return True
    return len([t for t in v["tiles"] if t["title"]]) >= 2


# ---------------------------------------------------------------- choose the pages
keep = {}
for path, v in SRC.items():
    if ALWAYS_DROP.search(path) or not real(v):
        continue
    keep[path] = v
groups = {}
for path, v in keep.items():
    groups.setdefault((v["title"].lower(), v["words"] // 25), []).append(path)
alias = {}
for key, paths in groups.items():
    if len(paths) > 1:
        paths.sort(key=lambda p: (next((i for i, pre in enumerate(PREFER) if p.startswith(pre)), 99), len(p)))
        for other in paths[1:]:
            alias[other] = paths[0]
for other in alias:
    keep.pop(other, None)
for old in CURATED:
    keep.pop(old, None)

B["pages"] = [p for p in B["pages"] if p["slug"] not in SUPERSEDED and not p.get("mirror")]
B["items"] = [i for i in B["items"] if not i.get("mirror")]
for p in B["pages"]:
    p.setdefault("path", p["slug"] if not p.get("parent") else p["parent"] + "/" + p["slug"])


def slug_of(seg):
    seg = re.sub(r"[^a-z0-9]+", "-", seg.lower()).strip("-")
    return seg or "page"


def slugpath(path):
    return "/".join(slug_of(x) for x in path[len("/en/"):].split("/"))


stories = {p for p in keep if p.startswith(STORY_DIR) and SRC[p]["words"] >= 300 and not SRC[p]["tiles"]}
pages_paths = [p for p in keep if p not in stories]

# ---------------------------------------------------------------- addresses
NEWPATH = {}  # old path -> final slug path (what the address becomes)
for p in sorted(pages_paths, key=lambda x: x.count("/")):
    segs = slugpath(p).split("/")
    parent = ""
    for n in range(len(segs) - 1, 0, -1):
        cand = "/".join(segs[:n])
        if cand in NEWPATH.values() or cand in tops:
            parent = cand
            break
    if not parent and segs[0] in tops and len(segs) > 1:
        parent = segs[0]
    if p.startswith("/en/about/") and not parent:
        parent = "about-us"
    if p.startswith("/en/digitalministry") and not parent:
        parent = "ministries"
    if p.startswith("/en/blog/"):
        parent = "train-and-grow/articles"
    NEWPATH[p] = (parent + "/" if parent else "") + segs[-1]


def new_url(old):
    """The address an old path now has, or None."""
    old = clean_path(old)
    if old in CURATED:
        return "/" + CURATED[old] + "/"
    if old in NEWPATH:
        return "/" + NEWPATH[old] + "/"
    if old in stories:
        return "/stories/" + slug_of(old.rsplit("/", 1)[-1]) + "/"
    if old in alias and alias[old] != old:
        return new_url(alias[old])
    return None


def link_fix(html_text, base):
    def sub(m):
        href = html.unescape(m.group(1))
        r = resolve(href, base)
        if r is None:
            return m.group(0)
        if r.startswith(("http", "mailto:", "tel:")):
            return f'<a href="{html.escape(r)}">'
        if r.startswith("#"):
            return m.group(0)
        u = new_url(r)
        return f'<a href="{u}">' if u else "<a-drop>"
    s = re.sub(r'<a href="([^"]*)">', sub, html_text)
    return re.sub(r"<a-drop>(.*?)</a>", r"\1", s, flags=re.S)


# ---------------------------------------------------------------- images
os.makedirs(MEDIA, exist_ok=True)
IMG_DONE = {}


def local_image(src, base):
    if src.startswith("http"):
        return ""
    j = posixpath.normpath(posixpath.join(posixpath.dirname("/gcmnigeria.org" + base + ".html"), src.split("?")[0]))
    fp = MIRROR + j.replace("/", os.sep)
    if not (os.path.exists(fp) and os.path.getsize(fp) > 3000):
        return ""
    if fp in IMG_DONE:
        return IMG_DONE[fp]
    try:
        im = Image.open(fp)
        im.load()
    except Exception:
        IMG_DONE[fp] = ""
        return ""
    if im.width < 200:
        IMG_DONE[fp] = ""
        return ""
    name = "m-" + hashlib.md5(fp.encode()).hexdigest()[:10] + ".jpg"
    dest = os.path.join(MEDIA, name)
    if not os.path.exists(dest):
        if im.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            rgba = im.convert("RGBA")
            bg.paste(rgba, mask=rgba.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        if im.width > 900:
            im = im.resize((900, int(im.height * 900 / im.width)), Image.LANCZOS)
        im.save(dest, "JPEG", quality=72, optimize=True)
    IMG_DONE[fp] = name
    return name


# ---------------------------------------------------------------- content
def render_blocks(blocks, title, base):
    out = []
    first = True
    for k, v in blocks:
        if k == "img":
            name = local_image(v[0], base)
            if name:
                out.append(f"[[img:{name}|{html.escape(v[1])}]]")
            continue
        if k == "video":
            out.append(f'<p><a href="{html.escape(v)}">Watch the video</a></p>')
            continue
        txt = plain(v if isinstance(v, str) else " ".join(v))
        if not txt or JUNK.match(txt):
            continue
        if k in ("ul", "ol"):
            items = [i for i in v if plain(i)]
            if len(out) < 3 and all(re.fullmatch(r"\s*<a [^>]*>[^<]*</a>\s*", i) for i in items):
                continue  # breadcrumb or section menu
            out.append(f"<{k}>" + "".join(f"<li>{link_fix(i, base)}</li>" for i in items) + f"</{k}>")
            continue
        if k in ("h2", "h3", "h4"):
            if first and plain(v).lower() == title.lower():
                first = False
                continue
            first = False
            tag = "h2" if k == "h2" else "h3"
            out.append(f"<{tag}>{re.sub(r'</?strong>', '', link_fix(v, base))}</{tag}>")
        elif k == "p":
            first = False
            out.append("<p>" + re.sub(r"(<br>)+$", "", link_fix(v, base)).strip() + "</p>")
        elif k == "blockquote":
            out.append(f"<blockquote>{link_fix(v, base)}</blockquote>")
    return "\n".join(out)


def short(t, n=120):
    t = plain(t)
    if len(t) <= n:
        return t
    return t[:n].rsplit(" ", 1)[0].rstrip(",;:-") + "…"


def tile_url(t, base):
    r = resolve(t["href"], base)
    if not r:
        return None
    return r if r.startswith("http") else new_url(r)


# ---------------------------------------------------------------- build pages and stories
new_pages, new_items = [], []
for old in sorted(pages_paths, key=lambda x: x.count("/")):
    v = SRC[old]
    np_ = NEWPATH[old]
    parent, _, slug = np_.rpartition("/")
    section = old.split("/")[2]
    title = html.unescape(v["title"]).strip()
    tiles, inline_tiles = [], []
    for t in v["tiles"]:
        if not t["title"]:
            continue
        u = tile_url(t, old)
        if u:
            tiles.append({"title": short(t["title"], 70), "text": short(t["text"], 110), "url": u})
        else:
            inline_tiles.append(t)
    body = render_blocks(v["blocks"], title, old)
    for t in inline_tiles:
        body += f"\n<h3>{html.escape(t['title'])}</h3>\n<p>{link_fix(html.escape(t['text']), old)}</p>"
    m = re.match(r"\s*<p>(.*?)</p>", body, re.S)
    eyebrow = parent.split("/")[-1].replace("-", " ").title() if parent else ""
    entry = {"slug": slug, "path": np_, "title": title, "dept": DEPT.get(section, "Communications"), "excerpt": short(v["desc"] or plain(body), 160),
             "order": 50, "mirror": True, "old": old}
    if parent:
        entry["parent"] = parent
    if len(tiles) >= 2:
        lead = ""
        if m and len(plain(m.group(1))) <= 260:
            lead = plain(m.group(1))
            body = body[m.end():].strip()
        lead = lead or short(v["desc"], 200)
        entry["layout"] = {"type": "list" if len(tiles) > 16 else "hub", "eyebrow": eyebrow, "lead": lead, "tiles": tiles}
        entry["content"] = ""
        if len(plain(body)) > 40:
            entry["layout"]["extra"] = body
    else:
        entry["layout"] = {"type": "doc", "eyebrow": eyebrow}
        if len(tiles) == 1:
            body += f'\n<p><a href="{tiles[0]["url"]}">{html.escape(tiles[0]["title"])}</a></p>'
        entry["content"] = body
    new_pages.append(entry)

for old in sorted(stories):
    v = SRC[old]
    title = html.unescape(v["title"]).strip()
    body = render_blocks(v["blocks"], title, old)
    new_items.append({"type": "gcmn_story", "slug": slug_of(old.rsplit("/", 1)[-1]), "title": title, "excerpt": short(v["desc"] or plain(body), 170),
                      "content": body, "dept": "Campus (Student-Led Movements)", "meta": {}, "mirror": True, "old": old})

# the Articles page lists every article
art = sorted((e for e in new_pages if e.get("parent") == "train-and-grow/articles"), key=lambda e: e["title"])
new_pages.append({"slug": "articles", "path": "train-and-grow/articles", "parent": "train-and-grow", "title": "Articles", "dept": "Communications", "order": 99, "mirror": True,
                  "excerpt": "Longer reads on faith, relationships, spiritual growth and sharing the gospel.", "content": "",
                  "layout": {"type": "list", "eyebrow": "Train and grow", "lead": "Longer reads on faith, relationships, spiritual growth and sharing the gospel.",
                             "tiles": [{"title": e["title"], "text": "", "url": "/" + e["path"] + "/"} for e in art]}})

# a page that is only an introduction to the pages below it becomes a hub of them
by_path = {e["path"]: e for e in new_pages}
children = {}
for e in new_pages:
    children.setdefault(e.get("parent", ""), []).append(e)
for e in new_pages:
    ch = children.get(e["path"], [])
    lay = e.get("layout", {})
    words = len(plain(e["content"]).split())
    if lay.get("type") == "doc" and ch and (words < 400 or (len(ch) >= 4 and words < 700)):
        order = NAV_ORDER.get(e["path"], [])
        ch = sorted(ch, key=lambda c: (order.index(c["slug"]) if c["slug"] in order else 99, c["title"]))
        body = e["content"]
        m = re.match(r"\s*<p>(.*?)</p>", body, re.S)
        lead = ""
        if m and len(plain(m.group(1))) <= 260:
            lead = plain(m.group(1))
            body = body[m.end():].strip()
        e["layout"] = {"type": "hub" if len(ch) <= 16 else "list", "eyebrow": lay.get("eyebrow", ""), "lead": lead or short(e["excerpt"], 200),
                       "tiles": [{"title": short(c["title"], 70), "text": short(c["excerpt"], 110), "url": "/" + c["path"] + "/"} for c in ch]}
        e["content"] = ""
        if len(plain(body)) > 40 and len(ch) < 4:
            e["layout"]["extra"] = body

# order pages by their position among the tiles of their parent hub
for e in new_pages:
    e["order"] = 50
for e in new_pages + [p for p in B["pages"] if not p.get("mirror")]:
    for i, t in enumerate(e.get("layout", {}).get("tiles", [])):
        child = by_path.get((t.get("url") or t.get("page") or "").strip("/"))
        if child and child.get("parent") == (e.get("path") or e["slug"]):
            child["order"] = i + 1
for par, order in NAV_ORDER.items():
    for i, sl in enumerate(order):
        c = by_path.get(par + "/" + sl)
        if c:
            c["order"] = i + 1

# the Ministries, About us and Opportunities hubs show everything
P = {p["slug"]: p for p in B["pages"] if not p.get("parent")}
strategies = [s for s in B["items"] if s["type"] == "gcmn_strategy"]
if "ministries" in P:
    P["ministries"]["layout"] = {"type": "hub", "eyebrow": "Ministries", "lead": "Great Commission Movement of Nigeria has a number of strategies that offer many ministry opportunities.",
                                 "tiles": [{"title": short(s["title"], 60), "text": short(s.get("excerpt", ""), 90), "item": "gcmn_strategy:" + s["slug"]} for s in strategies]}
if "about-us" in P:
    for sl, nm in (("about-us/our-leadership", "Our leadership"), ("about-us/billy-graham", "Billy Graham"), ("about-us/las-vegas-shooting", "Las Vegas shooting"),
                   ("about-us/privacy", "Your privacy"), ("about-us/terms-of-use", "Terms of use")):
        c = by_path.get(sl)
        if c:
            P["about-us"]["layout"]["tiles"].append({"title": nm, "text": short(c["excerpt"], 80), "page": sl})
if "opportunities" in P and by_path.get("opportunities/email-series-sign-up"):
    P["opportunities"]["layout"]["tiles"].append({"title": "Learn to share your faith", "text": "A 5-part email series on creating and sharing your story.", "page": "opportunities/email-series-sign-up"})

B["pages"] += new_pages
B["items"] += new_items

# ---------------------------------------------------------------- redirects (old address -> new)
redirects = {}
for old in SRC:
    u = new_url(old)
    if u:
        redirects[old] = u
        redirects[old + ".html"] = u
        redirects[old.replace("/en/", "/content/gcmnigeria/ng/en/", 1)] = u
B["redirects"] = redirects

# ---------------------------------------------------------------- menus: sections, their pages, and the pages under those
kids = {}
for e in B["pages"]:
    kids.setdefault(e.get("parent", ""), []).append(e)
for k in kids:
    kids[k].sort(key=lambda e: (e.get("order", 50), e["title"]))


def sub_entries(path, depth):
    out = []
    for c in kids.get(path, []):
        d = {"title": c["title"], "page": c["path"]}
        if depth < 3:
            grand = kids.get(c["path"], [])
            hubs = [g for g in grand if kids.get(g["path"])]
            d["children"] = [{"title": g["title"], "page": g["path"]} for g in (hubs or grand)][:8]
        out.append(d)
    return out[:14]


def section(title, slug, first=None):
    return {"title": title, "page": slug, "children": (first or []) + sub_entries(slug, 2)}


ministries_kids = [{"title": s["title"], "item": "gcmn_strategy:" + s["slug"]} for s in strategies]
about_first = [{"title": "Our mission", "page": "who-we-are"}, {"title": "Our values", "page": "our-values"}, {"title": "What we do", "page": "what-we-do"},
               {"title": "Our history", "page": "our-history"}, {"title": "Statement of faith", "page": "statement-of-faith"}, {"title": "Contact", "page": "contact"}]
B["menus"]["primary"] = [
    section("How to know God", "how-to-know-god", [{"title": "Four Spiritual Laws", "item": "gcmn_resource:the-four-spiritual-laws"}, {"title": "Stories", "archive": "gcmn_story"}]),
    section("Train and grow", "train-and-grow"),
    {"title": "Ministries", "page": "ministries", "children": ministries_kids},
    section("Opportunities", "opportunities", [{"title": "Join the Great Commission", "page": "serve"}]),
    section("About us", "about-us", about_first),
    {"title": "Need prayer", "page": "need-prayer"},
    {"title": "Talk to a mentor", "page": "talk-to-a-mentor"},
    {"title": "Give", "page": "giving", "class": "g-nav-give"},
]

# ---------------------------------------------------------------- write
BAD_CHARS = re.compile("[\ufffd\ud800-\udfff]+")


def scrub(x):
    if isinstance(x, str):
        return BAD_CHARS.sub("", x)
    if isinstance(x, list):
        return [scrub(i) for i in x]
    if isinstance(x, dict):
        return {k: scrub(v) for k, v in x.items()}
    return x


B = scrub(B)
json.dump(B, open(BUNDLE, "w", encoding="utf8"), ensure_ascii=False, indent=1)
used = {n for n in IMG_DONE.values() if n}
print("pages added", len(new_pages), "| stories added", len(new_items), "| redirects", len(redirects), "| images", len(used),
      round(sum(os.path.getsize(os.path.join(MEDIA, n)) for n in used) / 1e6, 1), "MB")
