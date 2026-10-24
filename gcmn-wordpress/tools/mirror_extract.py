"""Read the offline copy of the old gcmnigeria.org (an HTTrack mirror) and write one clean JSON file of every page.

Input : the mirror folder (default C:\\My Web Sites\\Indigitous), which holds gcmnigeria.org/ with the real pages.
Output: <out>/mirror.json: { "/en/train-and-grow/...": {title, desc, blocks, tiles, images, words} }

Only pages of the Nigerian site are kept (paths under /en/ and /content/gcmnigeria/ng/en/). Pages of other Cru country sites, error
pages and image redirect stubs are skipped. Links are rewritten later by the importer.
Run:  python tools/mirror_extract.py [mirror-folder] [out-folder]
"""
import html
import json
import os
import re
import sys
import urllib.parse

sys.path.append(r"C:\Users\Segun\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\site-packages")
from bs4 import BeautifulSoup, NavigableString  # noqa: E402

MIRROR = sys.argv[1] if len(sys.argv) > 1 else r"C:\My Web Sites\Indigitous"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "_mirror")
os.makedirs(OUT, exist_ok=True)
ROOT = os.path.join(MIRROR, "gcmnigeria.org")


def norm(rel):
    p = rel.replace(os.sep, "/")
    p = re.sub(r"^content/gcmnigeria/ng/", "", p)
    p = re.sub(r"\.html$", "", p)
    return "/" + p


def keep(rel):
    n = norm(rel)
    if not n.startswith("/en/"):
        return False
    if re.search(r"/(_jcr_content|_https?_|_)(/|$)", n) or "/_/" in n or "archive" in n.rsplit("/", 1)[-1][:7]:
        return False
    return True


def inline(el):
    out = []
    for c in el.children:
        if isinstance(c, NavigableString):
            out.append(html.escape(str(c)))
        elif c.name in ("strong", "b"):
            out.append("<strong>" + inline(c) + "</strong>")
        elif c.name in ("em", "i"):
            out.append("<em>" + inline(c) + "</em>")
        elif c.name == "br":
            out.append("<br>")
        elif c.name == "a":
            href = c.get("href", "")
            out.append(f'<a href="{html.escape(href)}">' + inline(c) + "</a>")
        elif c.name in ("script", "style", "svg", "noscript", "button"):
            continue
        elif hasattr(c, "children"):
            out.append(inline(c))
    return "".join(out)


def plain(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def img_of(el):
    for im in el.find_all("img"):
        src = im.get("src") or im.get("data-src") or ""
        if src and "logo" not in src.lower() and not src.startswith("data:"):
            return src, im.get("alt", "")
    return None


def walk(el, out, tiles):
    n = el.name
    if n in ("h1", "h2", "h3", "h4", "h5", "h6"):
        t = inline(el).strip()
        if plain(t):
            out.append(("h2" if n in ("h1", "h2") else "h3" if n == "h3" else "h4", t))
    elif n == "p":
        t = inline(el).replace("\xa0", " ").strip()
        if plain(t):
            out.append(("p", t))
    elif n in ("ul", "ol"):
        items = [inline(li).strip() for li in el.find_all("li", recursive=False)]
        items = [i for i in items if plain(i)]
        if items:
            out.append((n, items))
    elif n == "blockquote":
        t = inline(el).strip()
        if plain(t):
            out.append(("blockquote", t))
    elif n == "img":
        src = el.get("src") or el.get("data-src") or ""
        if src and "logo" not in src.lower() and not src.startswith("data:"):
            out.append(("img", (src, el.get("alt", ""))))
    elif n == "iframe":
        src = el.get("src", "")
        if "youtube" in src or "vimeo" in src:
            out.append(("video", src))
    elif n in ("script", "style", "noscript", "svg", "button", "select", "form", "nav"):
        return
    else:
        classes = " ".join(el.get("class", []))
        if "legacy-tile" in classes or (n == "div" and "tile" in classes.split() and el.find("h3")):
            a = el.find("a", href=True)
            h = el.find(["h3", "h2", "h4"])
            ps = [plain(inline(p)) for p in el.find_all("p")]
            tiles.append({"title": plain(inline(h)) if h else (plain(inline(a)) if a else ""), "text": " ".join(x for x in ps if x),
                          "href": a["href"] if a else "", "img": img_of(el)})
            return
        for c in el.children:
            if hasattr(c, "name") and c.name:
                walk(c, out, tiles)


def extract(path):
    h = open(path, encoding="utf8", errors="replace").read()
    s = BeautifulSoup(h, "html.parser")
    title = ""
    t = s.find("meta", property="og:title")
    if t and t.get("content"):
        title = t["content"]
    elif s.find("title"):
        title = s.find("title").get_text(strip=True)
    title = html.unescape(re.sub(r"\s*\|\s*Great Commission Movement of Nigeria.*$", "", title)).strip()
    desc = ""
    m = s.find("meta", attrs={"name": "description"})
    if m and m.get("content"):
        desc = html.unescape(m["content"]).strip()
    body = s.find("body") or s
    blocks, tiles = [], []
    for c in body.find_all(recursive=False):
        if c.name in ("footer", "script", "style") or c.get("id") in ("cru-header-nav", "okta-config", "search-overlay", "fb-root"):
            continue
        cl = " ".join(c.get("class", []))
        if "visible-print" in cl or "alert" in cl or "modal" in cl:
            continue
        walk(c, blocks, tiles)
    words = sum(len(plain(v if isinstance(v, str) else " ".join(v)).split()) for k, v in blocks if k in ("p", "h2", "h3", "h4", "blockquote", "ul", "ol"))
    return {"title": title, "desc": desc, "blocks": blocks, "tiles": tiles, "words": words}


def main():
    pages = {}
    for r, _, fs in os.walk(ROOT):
        for f in fs:
            if not f.endswith(".html"):
                continue
            p = os.path.join(r, f)
            rel = os.path.relpath(p, ROOT)
            if os.path.getsize(p) < 6000 or not keep(rel):
                continue
            n = norm(rel)
            # prefer the plain /en/ copy over the /content/... copy
            if n in pages and rel.replace(os.sep, "/").startswith("content/"):
                continue
            try:
                pages[n] = extract(p)
                pages[n]["file"] = rel.replace(os.sep, "/")
            except Exception as e:  # a page that cannot be read is reported, not hidden
                print("  could not read", rel, e)
    json.dump(pages, open(os.path.join(OUT, "mirror.json"), "w", encoding="utf8"), ensure_ascii=False)
    print(len(pages), "pages")
    rich = sum(1 for v in pages.values() if v["words"] >= 80)
    print(rich, "with 80 or more words;", sum(1 for v in pages.values() if v["tiles"]), "with tiles")


main()
