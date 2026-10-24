"""Give every page a background picture, and every tile a picture where the old site has one for that topic.

Reads the offline copy of the old site (the pictures in content/dam), picks the picture for each section and topic, shrinks it
to 1600 pixels wide, and sets  "bg"  on pages and  "img"  on tiles in gcmn-core/content/gcmn-content.json.
Run after build_mirror.py (python tools/build_all.py does all steps).
"""
import hashlib
import json
import os
import re
import sys

sys.path.append(r"C:\Users\Segun\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\site-packages")
from PIL import Image  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MIRROR = r"C:\My Web Sites\Indigitous\gcmnigeria.org"
BUNDLE = os.path.join(ROOT, "gcmn-core", "content", "gcmn-content.json")
MEDIA = os.path.join(ROOT, "gcmn-core", "content", "media")
B = json.load(open(BUNDLE, encoding="utf8"))

# every usable picture of the old site: path -> words in its name
INDEX = []
for r, _, fs in os.walk(os.path.join(MIRROR, "content", "dam")):
    if "transform" in r and "CruMarketingCover" not in r:
        continue
    for f in fs:
        p = os.path.join(r, f)
        try:
            if os.path.getsize(p) < 60000:
                continue
            head = open(p, "rb").read(4)
        except OSError:
            continue
        if not (head[:3] == b"\xff\xd8\xff" or head[:4] == b"\x89PNG"):
            continue
        rel = os.path.relpath(p, MIRROR)
        name = re.sub(r"\.(jpe?g|png).*$", "", f, flags=re.I)
        words = {w.rstrip("s") for w in re.split(r"[^a-z]+", name.lower()) if len(w) > 3}
        INDEX.append((p, rel, words))


def find(sub):
    sub = sub.replace("/", os.sep)
    hits = [p for p, rel, _ in INDEX if sub.lower() in rel.lower()]
    return hits[0] if hits else ""


SECTION = {
    "home": "homepage-hero-night-landscape-silhouette",
    "how-to-know-god": "how-to-know-god\\CruHeader_3_Overlay.jpg_",
    "train-and-grow": "train-and-grow\\CruHeader_10_Overlay.jpg_",
    "ministries": "communities\\CruHeader_16_Overlay.jpg_",
    "opportunities": "opportunities-banner-151218",
    "about-us": "about\\helena-lopes-459331",
    "giving": "about\\ben-white-181034",
    "need-prayer": "kgp-man-praying",
    "talk-to-a-mentor": "students-talking-with-tea",
    "who-we-are": "about\\helena-lopes-459331",
    "contact": "about\\remi-walle",
    "partnership": "about\\ben-white-165045",
    "serve": "opportunities-banner-151218",
    "what-we-do": "about\\edward-cisneros",
}
GENERIC = {"life", "story", "with", "your", "that", "this", "from", "what", "have", "make", "into", "series", "tile", "header", "banner", "overlay", "main", "hero"}
DONE = {}


def shrink(src):
    if not src:
        return ""
    if src in DONE:
        return DONE[src]
    try:
        im = Image.open(src)
        im.load()
    except Exception:
        DONE[src] = ""
        return ""
    name = "bg-" + hashlib.md5(src.encode()).hexdigest()[:10] + ".jpg"
    dest = os.path.join(MEDIA, name)
    if not os.path.exists(dest):
        if im.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            rgba = im.convert("RGBA")
            bg.paste(rgba, mask=rgba.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        if im.width > 1400:
            im = im.resize((1400, int(im.height * 1400 / im.width)), Image.LANCZOS)
        im.save(dest, "JPEG", quality=62, optimize=True, progressive=True)
    DONE[src] = name
    return name


def topic_image(slug_words):
    best, score = "", 0
    for p, rel, words in INDEX:
        w = words - GENERIC
        s = len(w & slug_words)
        if s == 1 and len(w) > 1:
            continue  # one shared word in a long file name is not enough
        if s > score or (s == score and s and len(rel) < len(best)):
            best, score = p, s
    return best if score else ""


pages = {(p.get("path") or p["slug"]): p for p in B["pages"]}


def top_of(path):
    return path.split("/")[0]


def own_bg(path):
    """The picture that belongs to this page itself (not inherited)."""
    last = path.rsplit("/", 1)[-1]
    if path in SECTION:
        return shrink(find(SECTION[path]))
    if last in SECTION:
        return shrink(find(SECTION[last]))
    words = {w.rstrip("s") for w in re.split(r"[^a-z]+", last) if len(w) > 3} - GENERIC
    return shrink(topic_image(words)) if words else ""


own = {}
for path in pages:
    own[path] = own_bg(path)


def inherited(path):
    parts = path.split("/")
    for n in range(len(parts), 0, -1):
        c = "/".join(parts[:n])
        if own.get(c):
            return own[c]
    return own.get(top_of(path), "") or shrink(find(SECTION["home"]))


for path, p in pages.items():
    p["bg"] = inherited(path)
    p["bg_own"] = bool(own.get(path))
if "home" in pages:
    pages["home"]["bg"] = shrink(find(SECTION["home"]))

# tiles take the picture of the page they lead to, when that page has one of its own
by_url = {"/" + k + "/": v for k, v in pages.items()}
items = {(i["type"] + ":" + i["slug"]): i for i in B["items"]}
for p in pages.values():
    for t in p.get("layout", {}).get("tiles", []):
        tgt = by_url.get(t.get("url", "")) if t.get("url") else (pages.get(t.get("page")) if t.get("page") else None)
        if tgt and tgt.get("bg_own"):
            t["img"] = tgt["bg"]
        elif t.get("item") and items.get(t["item"], {}).get("image"):
            t["img"] = items[t["item"]]["image"]
for p in pages.values():
    p.pop("bg_own", None)

json.dump(B, open(BUNDLE, "w", encoding="utf8"), ensure_ascii=False, indent=1)
used = {p["bg"] for p in pages.values() if p.get("bg")}
tiles = sum(1 for p in pages.values() for t in p.get("layout", {}).get("tiles", []) if t.get("img"))
size = sum(os.path.getsize(os.path.join(MEDIA, n)) for n in used) / 1e6
print("background pictures", len(used), round(size, 1), "MB | pages with a picture", sum(1 for p in pages.values() if p.get("bg")), "of", len(pages), "| tiles with a picture", tiles)

# a plain list of which picture each page got, to check by eye
name_to_src = {v: os.path.relpath(k, MIRROR) for k, v in DONE.items() if v}
with open(os.path.join(HERE, "_mirror", "bg_map.txt"), "w", encoding="utf8") as fh:
    for path, p in sorted(pages.items()):
        fh.write(f"{path[:70]:72s} {name_to_src.get(p.get('bg'), '?')[-80:]}\n")
