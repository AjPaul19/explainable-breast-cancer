"""Build gcmn-core/content/gcmn-content.json (and its media folder) from the crawled old website (gcmnigeria.org).

Input : a folder with extracted2.json (the old site's pages as text blocks) and tiles.json (ministry tile images).
Output: gcmn-core/content/gcmn-content.json and gcmn-core/content/media/*.
Every fact comes from the old site. Where the old site gave different figures for the same thing, the highest is used.
Run:  python tools/build_content.py <crawl-folder>
"""
import html as H
import json
import os
import re
import sys
import urllib.request

CRAWL = sys.argv[1] if len(sys.argv) > 1 else "."
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "gcmn-core", "content")
MEDIA = os.path.join(OUT, "media")
os.makedirs(MEDIA, exist_ok=True)

BASE = "https://www.gcmnigeria.org"
R = json.load(open(os.path.join(CRAWL, "extracted2.json"), encoding="utf8"))
TILES = {t[0].replace(BASE, ""): t[1] for t in json.load(open(os.path.join(CRAWL, "tiles.json")))}


def page(path):
    return R[BASE + path]


# ------------------------------------------------------------------ links
LINKMAP = {
    "/en/about.html": "/who-we-are/",
    "/en/about/what-we-do.html": "/what-we-do/",
    "/en/about/our-mission-in-nigeria.html": "/who-we-are/",
    "/en/about/values.html": "/who-we-are/our-values/",
    "/en/about/statement-of-faith.html": "/who-we-are/statement-of-faith/",
    "/en/about/our-leadership.html": "/who-we-are/",
    "/en/about/contact-us.html": "/contact/",
    "/en/50th-anniversary.html": "/who-we-are/our-history/",
    "/en/givetoharvest.html": "/giving/",
    "/en/investment-form.html": "/contact/?topic=giving",
    "/en/need-prayer.html": "/contact/?topic=prayer",
    "/en/talk-to-mentor.html": "/contact/",
    "/en/opportunities.html": "/serve/",
    "/en/opportunities/internships.html": "/serve/",
    "/en/opportunities/join.html": "/serve/",
    "/en/opportunities/gcmn-intership.html": "/contact/?topic=serve",
    "/en/ministries/opportunity-for-involvement.html": "/serve/",
    "/en/ministries.html": "/strategies/",
}
STRATS = {  # old path -> (slug, title)
    "/en/ministries/campus.html": ("campus-student-led-movements", "Campus (Student-Led Movements)"),
    "/en/ministries/prayer.html": ("prayer", "Prayer"),
    "/en/ministries/digital-ministry.html": ("digital-strategies", "Digital Strategies"),
    "/en/ministries/familylife.html": ("familylife", "FamilyLife"),
    "/en/ministries/the-jesus-film-project.html": ("jesus-film-project", "Jesus Film Project"),
    "/en/ministries/leaderimpact.html": ("leaderimpact", "LeaderImpact"),
    "/en/ministries/priority-associates.html": ("priority-associates-nigeria", "Priority Associates of Nigeria (PAN)"),
    "/en/ministries/globa-church.html": ("global-church-movements", "Global Church Movements (GCM)"),
    "/en/ministries/ahaf.html": ("agape-humanitarian-aid-foundation", "Agape Humanitarian Aid Foundation (AHAF)"),
    "/en/ministries/police-and-military-ministry.html": ("police-and-military-ministry", "Police and Military Ministry"),
    "/en/ministries/athletes-in-action.html": ("athletes-in-action", "Athletes in Action"),
    "/en/ministries/bca.html": ("bethany-christian-academy", "Bethany Christian Academy (BCA)"),
    "/en/ministries/acts-ilu.html": ("acts-ilu", "Africa Centre for Theological Studies (ACTS) and International Leadership University (ILU)"),
    "/en/ministries/operations.html": ("operations", "Operations"),
    "/en/ministries/ldhr.html": ("ldhr", "Leadership Development and Human Resource (LDHR)"),
    "/en/ministries/fund-development.html": ("fund-development", "Fund Development (FD)"),
}
for p, (slug, _t) in STRATS.items():
    LINKMAP[p] = f"/strategies/{slug}/"
LINKMAP["/en/campus.html"] = "/strategies/campus-student-led-movements/"
LINKMAP["/en/digitalministry.html"] = "/strategies/digital-strategies/"


def fix_link(href):
    if href.startswith(BASE) or href.startswith("https://gcmnigeria.org"):
        path = re.sub(r"^https://(www\.)?gcmnigeria\.org", "", href).split("#")[0]
        path = re.sub(r"^/content/gcmnigeria/ng", "", path)
        if path in ("", "/"):
            return "/"
        if path in LINKMAP:
            return LINKMAP[path]
        return None  # a page that is not on the new site: drop the link, keep the words
    return href


def clean_inline(s):
    """Fix links inside an inline HTML string."""
    def sub(m):
        new = fix_link(H.unescape(m.group(1)))
        return f'<a href="{H.escape(new)}">' if new else "<a-drop>"
    s = re.sub(r'<a href="([^"]*)">', sub, s)
    # remove dropped anchors, keep their text
    s = re.sub(r"<a-drop>(.*?)</a>", r"\1", s, flags=re.S)
    s = s.replace("\xa0", " ")
    return s.strip()


def plain(s):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def render(blocks, title, drop=(), skip_ul=True, skip_h3_links=True, first_h2_is_title=True):
    """Blocks -> clean HTML. `drop` is a list of regexes; any block whose text matches is left out."""
    out = []
    first = True
    for kind, val in blocks:
        if kind == "img":
            continue
        txt = plain(val if isinstance(val, str) else " ".join(val))
        if any(re.search(d, txt, re.I) for d in drop):
            continue
        if kind in ("ul", "ol"):
            if skip_ul and kind == "ul":
                continue
            items = [clean_inline(i) for i in val if plain(i)]
            if items:
                out.append(f"<{kind}>" + "".join(f"<li>{i}</li>" for i in items) + f"</{kind}>")
            continue
        if not txt:
            continue
        if kind in ("h2", "h3", "h4"):
            if first_h2_is_title and first and plain(val).lower() == title.lower():
                first = False
                continue
            first = False
            if skip_h3_links and val.strip().startswith("<a "):
                continue
            if re.match(r"^(join |latest stories)", txt, re.I):
                continue
            tag = "h2" if kind == "h2" else "h3"
            out.append(f"<{tag}>{re.sub(r'</?strong>', '', clean_inline(val))}</{tag}>")
        elif kind == "p":
            first = False
            c = clean_inline(val)
            c = re.sub(r"<br\s*/?>\s*$", "", c).strip()
            if c and not re.fullmatch(r"(<br>|\s)*", c):
                out.append(f"<p>{c}</p>")
        elif kind == "blockquote":
            out.append(f"<blockquote>{clean_inline(val)}</blockquote>")
    return "\n".join(out)


def first_sentences(html, limit=190):
    t = plain(re.sub(r"<h[23]>.*?</h[23]>", "", html))
    t = re.sub(r"“\s+", "“", t)
    t = re.sub(r"\s+”", "”", t)
    if len(t) <= limit:
        return t
    cut = t[:limit]
    m = max(cut.rfind(". "), cut.rfind("? "))
    return (cut[: m + 1] if m > 60 else cut.rsplit(" ", 1)[0] + "…").strip()



# ------------------------------------------------------------------ polish
PROPER = ["God", "Christ", "Jesus", "Him", "His", "Holy", "Spirit", "Lord", "Bible", "Savior", "Father", "Son"]


def sentence_case(t):
    """ALL-CAPS headings read as shouting; make them sentence case, keeping holy names capitalised."""
    if len(t) > 12 and t == t.upper():
        t = t.lower()
        t = t[:1].upper() + t[1:]
        for w in PROPER:
            t = re.sub(rf"\b{w.lower()}\b", w, t)
        t = t.replace("god&#x27;s", "God&#x27;s")
    return t


def polish(html, strip_heads=(), cut_at=(), drop_p=()):
    # cut off trailing teaser material
    for marker in cut_at:
        i = html.find(marker)
        if i > 0:
            html = html[:i]
    html = re.sub(r"<p>(?:<br\s*/?>|\s)*$", "", html)
    html = html.replace("&nbsp;", " ")
    html = re.sub(r"(<h[23]>)(.*?)(</h[23]>)", lambda m: m.group(1) + re.sub(r"<br\s*/?>", " ", m.group(2)).strip() + m.group(3), html, flags=re.S)

    # split paragraphs that hold line breaks
    def split_br(m):
        parts = [x.strip() for x in re.split(r"<br\s*/?>", m.group(1)) if x.strip()]
        return "".join(f"<p>{x}</p>" for x in parts)

    html = re.sub(r"<p>(.*?)</p>", split_br, html, flags=re.S)
    html = re.sub(r"<p>\s*</p>", "", html)
    # a paragraph that is only bold text is really a subheading
    html = re.sub(r"<p><strong>([^<]{2,80})</strong></p>", r"<h3>\1</h3>", html)
    # drop requested paragraphs
    for d in drop_p:
        html = re.sub(rf"<p>(?:(?!</p>).)*?{d}(?:(?!</p>).)*</p>", "", html, flags=re.I | re.S)
        html = re.sub(rf"<h3>\s*{d}[^<]*</h3>", "", html, flags=re.I)
    # leading headings that only repeat the page name
    heads = [x.lower() for x in strip_heads]
    while True:
        m = re.match(r"\s*<h[23]>([^<]*)</h[23]>\s*", html)
        if m and plain(m.group(1)).lower() in heads:
            html = html[m.end():]
        else:
            break
    # consecutive duplicate headings
    html = re.sub(r"(<h[23]>[^<]*</h[23]>)\s*\1", r"\1", html)
    html = re.sub(r"<h[23]>([^<]*)</h[23]>\s*(<h[23]>\1</h[23]>)", r"\2", html)
    html = re.sub(r"<br\s*/?>", " ", html)
    # lettered or numbered paragraphs (a) b) c) / i. ii.) become lists
    pieces = re.split(r"(?<=</p>)|(?<=</h2>)|(?<=</h3>)|(?<=</ul>)|(?<=</ol>)|(?<=</blockquote>)", html)
    out, buf = [], []

    def flush():
        if buf:
            out.append("<ul>" + "".join(f"<li>{x}</li>" for x in buf) + "</ul>")
            buf.clear()

    for ln in pieces:
        m = re.match(r"\s*<p>\s*(?:[a-z]\)|[ivx]+\.|\d+\.)\s+(.*)</p>\s*$", ln, flags=re.S)
        if m:
            buf.append(m.group(1).strip())
        else:
            flush()
            if ln.strip():
                out.append(ln)
    flush()
    html = "".join(out)
    html = re.sub(r"<h([23])>([^<]*)</h\1>", lambda m: f"<h{m.group(1)}>{sentence_case(m.group(2))}</h{m.group(1)}>", html)
    html = re.sub(r"(</(?:p|h2|h3|ul|ol|blockquote)>)", r"\1\n", html)
    html = re.sub(r"\n{2,}", "\n", html).strip()
    html = re.sub(r"“\s+", "“", html)
    html = re.sub(r"\s+”", "”", html)
    return html


# ------------------------------------------------------------------ media
def fetch(url_path, name):
    dest = os.path.join(MEDIA, name)
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        return name
    url = url_path if url_path.startswith("http") else BASE + url_path
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=40).read()
        if len(data) < 1000:
            return ""
        open(dest, "wb").write(data)
        return name
    except Exception as e:  # an image that cannot be fetched is simply left out
        print("  no image:", url_path[:80], str(e)[:40])
        return ""


def big(path):
    return path.replace("CruHalf432x243", "CruWhole848x477")


items = []
pages = []

# ------------------------------------------------------------------ strategies
DEPT_FOR = {}
for old, (slug, title) in STRATS.items():
    r = page(old)
    drop = [r"^Pray2020", r"10 ?million Christ-centered multiplying disciples, and 5 million", r"WE COLLABORATE", r"Set a daily alarm|^Ask God to fulfill|^Pray: .Lord, MOLD", r"^Visit the .* website$"]
    body = render(r["blocks"], title if slug not in ("acts-ilu",) else r["blocks"][0][1], drop=drop, skip_ul=True)
    # the page repeats its own name as an h3 right after the h2; remove a leading heading equal to the title
    body = re.sub(r"^<h[23]>[^<]*</h[23]>\n?", "", body) if re.match(r"^<h[23]>", body) and plain(body.split("</h")[0]).lower().startswith(plain(title).lower()[:12]) else body
    body = polish(body, strip_heads=(title, "Digital Ministry", "Campus", "Operations", "Fund Development (FD)", "Student-Led Movements (SLM)"), drop_p=(r"SLM Global Launch", r"GLOBAL LAUNCH is a global"))
    body = re.sub(r"<h3>SLM Global Launch</h3>\s*", "", body)
    ex = None
    if slug == "prayer":
        body = (
            "<p>Prayer is essential to our mission. Dr. Bill and Vonette Bright founded this ministry on prayer, and it is through prayer that we have been blessed to make such a significant contribution to fulfilling the Great Commission.</p>\n"
            "<p>Our long-term objective is to mobilize, train and deploy Biblical, strategic praying intercessors to each of the 774 local government areas across Nigeria.</p>\n"
            "<p>As we answer God’s call to the Great Commission, to go and “make disciples of all nations” (Matthew 28:19), we realize that this is not something we can do alone. Apart from God we can accomplish nothing. Through the power of the Holy Spirit, there is no end to what can be achieved. The body of Christ needs to join together and, through prayer, work with God to accomplish the works that He intends to do through us.</p>\n"
            "<h2>How to pray with us</h2>\n"
            "<p><strong>Mold</strong> our hearts to be one with God’s. Pray Romans 12:1-2: that as believers everywhere, we will live holy lives pleasing to God, and that our hearts and minds will be increasingly like His.</p>\n"
            "<p><strong>Multiply</strong> our lives into the lives of others. Pray 2 Timothy 2:2: that God will lead us to others we can show how to walk with God, so that they in turn can share that same joy with others.</p>\n"
            "<p><strong>Mobilize</strong> laborers through our prayer and ministry efforts. Pray Luke 10:2: ask the Lord of the harvest to send out workers into His harvest field, in our homes, in our places of work, neighborhoods and communities.</p>\n"
            "<p>Set a daily alarm for 8:20 PM and pray: “Lord, MOLD my heart… MULTIPLY my life… MOBILIZE others.”</p>\n"
            "<h2>Need prayer?</h2>\n"
            '<p>Tell us what you are facing and a member of the team will pray with you. <a href="/contact/?topic=prayer">Send a prayer request</a>.</p>'
        )
        ex = "An intercessor in every tribe and city. Prayer is essential to our mission."
    elif slug == "jesus-film-project":
        body = (
            "<p>The Jesus Film Project helps provide media tools, training, strategies and resources for abundant follow-through evangelism in every needed language.</p>\n"
            "<ul><li>Year founded: 1979</li><li>Jesus film translation in Nigeria started in 1983</li>"
            "<li>Over 170 Nigerian languages translated so far</li>"
            "<li>The film has been seen in every country in the world and translated into hundreds of languages</li></ul>\n"
            "<p>It also supports the Walking With Jesus Bible study manual in Nigeria.</p>"
        )
        ex = "Media tools, training and resources for follow-through evangelism in every needed language."
    elif slug == "familylife":
        body = (
            "<p><strong>FamilyLife provides transferable, biblically based help for you at every stage of your marriage and family life.</strong></p>\n"
            "<p>Your family is important. No matter what your current circumstances are, or what your family history has been, we believe that God is able to transform your situation. Whether you are looking to strengthen your marriage, or learning how to build a strong relationship with your child, we are here to help.</p>\n"
            "<h2>Build Up Your Spouse. Nurture Your Child and Build a Stronger Home.</h2>\n"
            "<p>FamilyLife Nigeria runs courses including The Art of Marriage®, The Art of Marriage® Connect and A Weekend To Remember.</p>\n"
            '<h2>Talk to us</h2>\n<p>Call <a href="tel:+2347036189008">0703 618 9008</a> to find out more and join FamilyLife.</p>'
        )
        ex = "Equipping couples with practical, scripture-based approaches to real-world issues through conferences, broadcasts and resources."
    elif slug == "leaderimpact":
        body = (
            "<p>We believe God puts leaders in positions of influence in all segments of society and in all the nations of the world to fulfil His purpose.</p>\n"
            "<p>We exist to encourage and empower these leaders to step into their God-given role as transformational leaders: to experience life to the full, not satisfied by status or success, but by stepping deeply into the call of God’s plan that was uniquely designed for them.</p>\n"
            "<p>As these leaders join with others, integrate their faith into their home and work life and form a vision for their city, we believe God will use us to transform our cities, nations and, ultimately, the world for Christ.</p>\n"
            "<h2>How it works</h2>\n"
            "<p>Leaders make things happen, and leaders who are fully devoted followers of Christ have a special call. The core process of LeaderImpact is a simple one: Win, Build, Send. The strategy starts with mission-focused communities, offering collective learning and mentorship for marketplace leaders through regular peer groups, leadership forums and global exchanges.</p>"
        )
        ex = "Spreading the Jesus experience among leaders through peer groups, leadership forums and global exchanges."
    elif slug == "athletes-in-action":
        body = body.replace('<p><a href="https://athletesinaction.org.ng">', "<p><a href=\"https://athletesinaction.org.ng\">")
    if ex is None:
        ex = first_sentences(body)
    # website links given as plain text: keep them
    img = TILES.get(old, "")
    imgname = ""
    if img:
        ext = os.path.splitext(img)[1].lower() or ".jpg"
        imgname = fetch(big(img), f"{slug}{ext}")
    DEPT_FOR[slug] = title
    items.append({
        "type": "gcmn_strategy", "slug": slug, "title": title, "excerpt": ex, "content": body,
        "image": imgname, "dept": title, "meta": {},
    })

# strategy-specific meta
for it in items:
    if it["slug"] == "campus-student-led-movements":
        it["meta"]["locations"] = "Universities and other higher institutions across Nigeria"
    if it["slug"] == "bethany-christian-academy":
        it["meta"]["locations"] = "Barkin Ladi, near Jos, Plateau State"
    if it["slug"] == "acts-ilu":
        it["meta"]["locations"] = "Ilupeju, Lagos"
    if it["slug"] == "familylife":
        it["meta"]["contact"] = "0703 618 9008"

# ------------------------------------------------------------------ history (Nigeria entries from the 50th anniversary page)
hist = page("/en/50th-anniversary.html")["blocks"]
years = []
cur = None
for kind, val in hist:
    if kind == "h2":
        cur = [plain(val), []]
        years.append(cur)
    elif kind == "p" and cur:
        cur[1].append(clean_inline(val))
FIX = {"lMaiduguri": "Maiduguri", "I lorin": "Ilorin", "comtnunity": "community", "NI,809,000": "N1,809,000"}


def nig_part(paras, heading):
    """For a global year that also has an 'IN NIGERIA' paragraph, keep only the Nigeria part."""
    out = []
    for p in paras:
        if "IN NIGERIA" in p:
            out.append(re.sub(r"^.*?IN NIGERIA:?\s*", "", p, flags=re.S).strip())
    return out


timeline = []
for head, paras in years:
    nig = "Nigeria" in head
    if nig:
        year = head.split("-")[0].strip()
        text = [p for p in paras]
    else:
        ps = nig_part(paras, head)
        if not ps:
            continue
        year, text = head, ps
    body = "".join(f"<p>{p}</p>" for p in text)
    for a, b in FIX.items():
        body = body.replace(a, b)
    body = re.sub(r"First edition MT xplosive Christian living was published\.?", "", body)
    body = re.sub(r"<br\s*/?>", "<br>", body)
    body = body.replace("\n", "<br>")
    timeline.append((year, body))
founders_img = fetch(big("/en/about/our-leadership/_jcr_content/content-parsys/tile_copy.transform/CruHalf432x243/img.jpeg"), "yemi-and-sue-ladipo.jpeg")
hist_html = (
    "<p>Great Commission Movement of Nigeria is an affiliate ministry of Campus Crusade for Christ International (CCCI), which was founded in 1951 by Bill and Vonette Bright on the campus of the University of California, Los Angeles.</p>\n"
    "<p>In 1969, Rev. Yemi and Sue Ladipo pioneered the ministry in Nigeria on the campus of the University of Lagos under the name “Great Commission Movement”. It was the norm with the ministry to adopt a locally acceptable name in whichever of the over 190 countries Campus Crusade for Christ is registered.</p>\n"
    "<h2>Our story in Nigeria, year by year</h2>\n"
    + "\n".join(f"<h3>{y}</h3>\n{b}" for y, b in timeline)
    + "\n<h3>2019</h3>\n<p>Great Commission Movement of Nigeria marked its 50th anniversary in August 2019, with visits to churches in different states of Nigeria from January to August.</p>"
)
pages.append({"slug": "our-history", "title": "Our history", "parent": "who-we-are", "order": 4, "content": hist_html, "dept": "Leadership",
              "excerpt": "How the ministry began in Nigeria in 1969 and grew, year by year."})

# ------------------------------------------------------------------ values & faith (verbatim)
val = page("/en/about/values.html")["blocks"]
vals_html = ["<p>We lead from values, so that others will walk passionately with God, grow and bear fruit.</p>"]
section = None
for kind, v in val:
    t = re.sub(r"<[^>]+>", "", v if isinstance(v, str) else "").strip()
    t = H.unescape(t)
    if kind == "h2" and re.match(r"^(Faith|Growth|Fruitfulness)", t):
        if section:
            vals_html.append("</ul>")
        vals_html.append(f"<h2>{t}</h2>")
        section = t
        vals_html.append("<ul>")
        started = False
    elif kind == "h4" and section:
        if re.match(r"^(i|ii|iii|iv|v|vi|vii|viii)\.", t):
            vals_html.append("<li>" + re.sub(r"^[ivx]+\.\s*", "", t) + "</li>")
        elif t and not t.startswith("About") and "What We Do" not in t and "Our Leadership" not in t:
            vals_html.insert(len(vals_html) - 1, f"<p>{t}</p>")
if section:
    vals_html.append("</ul>")
vals = "\n".join(vals_html)
pages.append({"slug": "our-values", "title": "Our values", "parent": "who-we-are", "order": 2, "content": vals, "dept": "Leadership",
              "excerpt": "Faith, Growth and Fruitfulness."})

sof = page("/en/about/statement-of-faith.html")["blocks"]
sof_html = []
for kind, v in sof:
    if kind == "p":
        sof_html.append(f"<p>{clean_inline(v).replace('<br>', '').strip()}</p>")
    elif kind == "ol":
        sof_html.append("<ol>" + "".join(f"<li>{clean_inline(i)}</li>" for i in v if plain(i)) + "</ol>")
pages.append({"slug": "statement-of-faith", "title": "Statement of faith", "parent": "who-we-are", "order": 3, "content": "\n".join(sof_html), "dept": "Leadership",
              "excerpt": "What we believe about the gospel and our call to serve every nation."})

# ------------------------------------------------------------------ who we are
who = f"""
<p>For over 50 years, the Great Commission Movement of Nigeria has been bringing the message of Jesus to people everywhere: on campuses and in corporate offices, in cities and in rural communities, among families, athletes and security forces, online, and through humanitarian aid for people displaced from their homes. Millions across the country have watched the JESUS film, which we have produced and translated into 170 Nigerian languages.</p>
<p>Our approach comes down to three simple moves: <strong>Win, Build and Send.</strong></p>
<h2>Our mission in Nigeria</h2>
<p>Position and empower teams of mission-minded people in the 36 States and Federal Capital Territory who Win, Build and Send Christ-centered Multiplying Disciples to reach each State with the Gospel and raise labourers and resources for the global harvest.</p>
<p><em>A team does not consist only of full-time staff, but of all categories of manpower.</em></p>
<h2>Our global mission, vision and values</h2>
<h3>Mission</h3>
<p>Win, build and send Christ-centered multiplying disciples.</p>
<h3>Vision</h3>
<p>Movements everywhere so that everyone knows someone who truly follows Jesus.</p>
<h3>Values</h3>
<p>Faith, Growth and Fruitfulness. <a href="/who-we-are/our-values/">Read what each one means</a>.</p>
<h2>Our calling</h2>
<p>To help fulfil the Great Commission by winning, building and sending in the power of the Holy Spirit, and helping the Body of Christ do evangelism and discipleship.</p>
<h2>Where we come from</h2>
<p>Great Commission Movement of Nigeria is an affiliate ministry of Campus Crusade for Christ International (CCCI), an international Christian organisation founded in 1951 by Bill and Vonette Bright on the campus of the University of California, Los Angeles.</p>
<p>Rev. Yemi and Sue Ladipo brought the ministry to Nigeria in 1969 and first settled in Lagos, focusing on the University of Lagos. <a href="/who-we-are/our-history/">See our story year by year</a>.</p>
<p>In August 2019 we marked our 50th anniversary with visits to churches in different states of Nigeria between January and August.</p>
<h2>Keep exploring</h2>
<ul>
<li><a href="/what-we-do/">What we do</a></li>
<li><a href="/who-we-are/our-values/">Our values</a></li>
<li><a href="/who-we-are/statement-of-faith/">Statement of faith</a></li>
<li><a href="/who-we-are/our-history/">Our history</a></li>
</ul>
"""
pages.append({"slug": "who-we-are", "title": "Who we are", "order": 1, "content": who, "dept": "Leadership",
              "excerpt": "Over 50 years of bringing the message of Jesus to people across Nigeria."})

what = """
<p>When you take on the task of reaching the world, you have to think big. Our leaders and staff accepted Jesus Christ’s command to go to the world, the whole world, and teach what He said. The church calls it the Great Commission (Matthew 28:18-20).</p>
<p>We have never believed the task was ours alone. As an international parachurch mission organisation, we want to speed up the work of others by creating strategies and giving them away. You may have worked with us and not even known we were alongside you.</p>
<p><strong>Our vision for the states and the Federal Capital Territory:</strong> positioned and empowered Kingdom citizens advancing the mission of Jesus for the well-being of every state and the FCT.</p>
<h2>Tools to help you tell others about Jesus</h2>
<p>In 1965, the founder of Campus Crusade, Bill Bright, wrote what he called “the distilled essence of the gospel” into a booklet, <em>Have You Heard of the Four Spiritual Laws?</em> It has been translated into more than 200 languages, giving Christians a simple way to share God’s love, truth and hope. A second tract, <em>Have You Made the Wonderful Discovery of the Spirit-Filled Life?</em>, teaches Christians to live the Christian life in God’s power, not their own.</p>
<h2>The world’s most translated film</h2>
<p>The <em>JESUS</em> film first showed in 250 theatres in 1979. Today it has been translated into more than 1,500 languages of the world, including 170 Nigerian languages. People learn about Jesus and hear what He said in their own mother tongue, and at the end are invited to say yes to Jesus. Versions exist for children, for football fans and for women.</p>
<h2>Different stages of life</h2>
<p>A good message bears repeating, but people at different stages of life do not hear it the same way. We speak to different groups in ways that are easy for them to engage with.</p>
<h3>Students</h3>
<p>Since 1951 we have gone to universities to turn “me-centred leaders” into “Christ-centred labourers”. Every year we host DESTINY, a nationwide faith-building event for students, and we turn school breaks into mission trips.</p>
<h3>Marriages and families</h3>
<p>FamilyLife equips couples with practical, Bible-based help through conferences, broadcasts and resources, including a Sunday programme on JayFM in Jos.</p>
<h3>Online</h3>
<p><a href="https://www.everystudent.com">EveryStudent.com</a> is our most prominent evangelistic website, reaching over 24 million students and adults each year. Articles and videos answer people’s questions about life and God, and people can email a personal question and get a personal reply. An average of at least 1,000 people each day tell us they have asked Jesus into their lives on the site. It is now in 43 languages.</p>
<h2>All our strategies</h2>
<p>Every strategy has its own page, so you can see what it does and how to get involved. <a href="/strategies/">Meet the strategies</a>.</p>
"""
pages.append({"slug": "what-we-do", "title": "What we do", "order": 5, "content": what, "dept": "Leadership",
              "excerpt": "How we journey with everyone towards a relationship with Jesus."})

# ------------------------------------------------------------------ giving
giving = """
<p>Your giving keeps people on the field and the gospel moving. Here is how it works, and how to give.</p>
<h2>Why we ask you to support our staff</h2>
<h3>Why do staff members raise support instead of GCMN raising it for them?</h3>
<p>We are a nonprofit organisation and have no central funds. Staff members, including the President of Campus Crusade for Christ International, raise support to cover salaries, benefits and expenses. Each staff member then has a team of partners who pray for him or her.</p>
<p>Central fundraising would limit the number of staff members. Because we have many staff members, hundreds of thousands of people hear the good news of God’s love. As the largest mission agency in the world, it would not be possible to have as many missionaries as we do if each staff member did not raise his or her own support.</p>
<h3>How is my staff member’s salary determined?</h3>
<p>Salaries are determined by age, number of children and geographic factors. A staff member may also raise funds for a retirement plan.</p>
<h3>When should I begin to send in contributions for my staff member?</h3>
<p>Right away, if you can. Many new staff members work part time or full time while raising support. As soon as enough is coming in, they can leave their other jobs and focus on ministry. The more time they can spend raising support, the sooner they can report to their ministries.</p>
<h3>How long am I expected to support my staff member?</h3>
<p>That is a decision between you and the Lord. Our desire is that you would support your staff member for as long as the Lord enables you.</p>
<h3>Does all my support go to my staff member?</h3>
<p>All contributions designated for the ministry of a staff member go into that staff member’s account, which is managed and dispensed by Great Commission Movement of Nigeria.</p>
<h2>What you can give to</h2>
<h3>Great Commission Movement of Nigeria</h3>
<p>You can invest in all kinds of GCMN administrative and ministry expenses.</p>
<h3>Full-time staff</h3>
<p>Each of our full-time staff trusts God to raise a team of ministry partners to finance the ministry.</p>
<h3>GCMN projects</h3>
<p>You can invest in any of our projects.</p>
<h2>How to give</h2>
<p>Give through the GCMN office nearest to you (<a href="/contact/">see our offices</a>), or transfer or deposit to one of the bank accounts below. Then tell us what your gift is for using the <a href="/contact/?topic=giving">giving form</a>, so we can direct it correctly.</p>
"""
pages.append({"slug": "giving", "title": "Give", "order": 8, "content": giving, "dept": "Finance",
              "excerpt": "Give to the work of Great Commission Movement of Nigeria."})

# ------------------------------------------------------------------ partnership
partner = """
<p>The harvest is big and the work is bigger than any one of us. You can be part of it, with your prayers, your gifts, your skills and your time.</p>
<h2>Become a L.I.F.E. partner</h2>
<p>L.I.F.E. stands for <strong>L</strong>eadership, <strong>I</strong>nfluence, <strong>F</strong>inances and <strong>E</strong>xpertise.</p>
<p>We want people to become all God intended them to be, by fully investing their leadership skills, influence, financial resources and professional expertise towards fulfilling the Great Commission.</p>
<p>It does not matter what your career or profession is. There is always a place for you to serve, and we are here to give you the platform.</p>
<h2>Ways to partner</h2>
<ul>
<li><strong>Pray.</strong> Prayer is the heart of our ministry. <a href="/strategies/prayer/">Pray with us</a>.</li>
<li><strong>Give.</strong> Support our staff and projects. <a href="/giving/">See how to give</a>.</li>
<li><strong>Serve.</strong> Volunteer, intern or join our staff. <a href="/serve/">See how to serve</a>.</li>
</ul>
<blockquote>“The harvest is plentiful but the workers are few. Ask the Lord of the harvest, therefore, to send out workers into the fields.” Matthew 9:37-38</blockquote>
<p>The Lord is waiting for you to play your part in fulfilling the Great Commission. <a href="/contact/?topic=partnership">Talk to us about partnering</a>.</p>
"""
pages.append({"slug": "partnership", "title": "Partner with us", "order": 7, "content": partner, "dept": "Funding and Resource Mobilisation Team",
              "excerpt": "Come help change the world with us as a L.I.F.E. partner."})

# ------------------------------------------------------------------ serve
serve = """
<p>The harvest is plentiful but the workers are few. There is a place for you, whatever your career or profession. Here are the ways to get involved.</p>
<h2>Ways to serve</h2>
<h3>Full-time staff</h3>
<p>People fully involved in the ministry of Win, Build and Send, who also raise partners to support them with finances, prayer and encouragement.</p>
<h3>Associate staff</h3>
<p>Staff who give an agreed part of their time to Win, Build and Send alongside their careers. They raise partners to support their involvement in ministry, but not their livelihood.</p>
<h3>Volunteer staff</h3>
<p>People who sign up for a particular project, or make themselves available for ministry opportunities whenever their schedule allows.</p>
<h3>Short-term: interns and STINT</h3>
<p>People who want to be involved for 6 to 18 months (or less in some cases) and who raise their own finances.</p>
<h3>L.I.F.E. partners</h3>
<p>People who invest their Leadership, Influence, Finances and Expertise in the Great Commission. <a href="/partnership/">Find out more</a>.</p>
<h2>Internship programme</h2>
<p>GCMN offers you the chance to give God 6 months to 1 year of unforgettable adventures. You can discover purpose through:</p>
<ul>
<li>an orientation to GCM</li>
<li>evangelism and discipleship training, to deepen your knowledge of God in conviction, competence, character and ministry skills</li>
<li>a taste of mission outreaches in 8 strategies</li>
<li>leadership development</li>
<li>cross-cultural missions training</li>
<li>fun team building</li>
<li>fund development and executive functioning skills for ministry</li>
</ul>
<h2>How to get involved</h2>
<p>Get in touch with us by email or phone and we will help you find your place. <a href="/contact/?topic=serve">Ask about serving</a>.</p>
"""
pages.append({"slug": "serve", "title": "Serve with us", "order": 9, "content": serve, "dept": "LDHR",
              "excerpt": "Volunteer, intern or join our staff."})

# ------------------------------------------------------------------ contact
contact_offices = """
[gcmn_contact]
<h2>Our offices</h2>
<h3>National office</h3>
<p>10 Secretariat Road, Jos, Plateau State<br>
<a href="tel:+2348100039399">+234 810 003 9399</a> (front desk, 9 AM to 4 PM)<br>
<a href="tel:+2348102707860">+234 810 270 7860</a><br>
<a href="mailto:info@gcmnigeria.org">info@gcmnigeria.org</a></p>
<h3>Regional offices</h3>
<p><strong>North West Region (NWR):</strong> <a href="tel:+2347068147275">+234 706 814 7275</a><br>
<strong>Central Nigeria Region (CNR):</strong> <a href="tel:+2348065731859">+234 806 573 1859</a><br>
<strong>South West Region (SWR):</strong> <a href="tel:+2348135996164">+234 813 599 6164</a></p>
<h3>Schools</h3>
<p><strong>Africa Centre for Theological Studies (ACTS):</strong> 40 Town Planning Street, Ilupeju, Lagos. P.O. Box 14330. <a href="tel:+2348087599000">+234 808 759 9000</a><br>
<strong>Bethany Christian Academy:</strong> P.O. Box 189, Barkin Ladi, Plateau State. <a href="tel:+2347083129974">+234 708 312 9974</a></p>
<h3>State offices</h3>
<p><strong>Plateau State:</strong> P.O. Box 1272, Jos, Plateau State. <a href="tel:+2348065731859">+234 806 573 1859</a><br>
<strong>Rivers State:</strong> P.O. Box 480, Uniport Post Office, Port Harcourt, Rivers State. <a href="tel:+2348037266918">+234 803 726 6918</a><br>
<strong>Enugu State:</strong> P.O. Box 3298, Trans Ekulu, Enugu State. <a href="tel:+2348066019662">+234 806 601 9662</a><br>
<strong>Osun State:</strong> P.O. Box 1615, Ile Ife, Osun State. <a href="tel:+2348135996164">+234 813 599 6164</a><br>
<strong>Kaduna State:</strong> Turaki Street, Zango Shanu, Zaria, Kaduna State. <a href="tel:+2347068147275">+234 706 814 7275</a><br>
<strong>Niger State:</strong> P.O. Box 3235, Minna, Niger State. <a href="tel:+2348061602287">+234 806 160 2287</a><br>
<strong>Borno State:</strong> P.O. Box 1800, Maiduguri, Borno State. <a href="tel:+2348063244077">+234 806 324 4077</a></p>
"""
pages.append({"slug": "contact", "title": "Contact", "order": 10, "content": contact_offices, "dept": "Operations",
              "excerpt": "Reach the right team at Great Commission Movement of Nigeria."})

# ------------------------------------------------------------------ stories (testimonies)
ST = [
    ("/en/how-to-know-god/buddhism-to-christianity.html", "buddhism-to-christianity", "From Buddhism to Christianity"),
    ("/en/how-to-know-god/judaism-to-christianity.html", "judaism-to-christianity", "A Leap to Faith: Judaism to Christianity"),
    ("/en/how-to-know-god/mormonism-to-christianity.html", "mormonism-to-christianity", "From Mormonism to Christianity"),
    ("/en/how-to-know-god/islam-to-christianity.html", "islam-to-christianity", "From Islam to Christianity"),
    ("/en/how-to-know-god/my-story-a-life-changed/my-story-de-winget.html", "atheism-to-christianity", "Gravity and the Pull of Christ"),
]
for old, slug, title in ST:
    r = page(old)
    body = render(r["blocks"], title, drop=[r"^Read (more )?stories", r"^Latest Stories", r"^(Listen|Watch)\b"], skip_ul=True)
    body = polish(body, strip_heads=(title, "How to Know God", "My Story: How My Life Changed"), cut_at=("See similar stories", "<h3>Related Topics"))
    body = re.sub(r"^<h3>([^<]{8,120})</h3>\n", r"<p><em>\1</em></p>\n", body)
    if len(plain(body)) < 400:
        print("  story too short, skipped:", slug)
        continue
    items.append({"type": "gcmn_story", "slug": slug, "title": title, "excerpt": first_sentences(body, 170), "content": body, "dept": "Campus (Student-Led Movements)",
                  "meta": {}})

# ------------------------------------------------------------------ resources (full articles only)
RS = [
    ("/en/train-and-grow/spiritual-growth/5-things-you-need-to-live-the-life-god-intended.html", "five-things-to-live-the-life-god-intended", "5 Things You Need to Live the Life God Intended", "Article"),
    ("/en/train-and-grow/spiritual-growth/5-spiritual-disciplines-to-help-grow-your-walk-with-god.html", "five-spiritual-disciplines", "5 Spiritual Disciplines to Help Grow Your Walk With God", "Article"),
    ("/en/how-to-know-god/would-you-like-to-know-god-personally.html", "the-four-spiritual-laws", "Have You Heard of the Four Spiritual Laws?", "Booklet"),
    ("/en/digitalministry/apps-tools.html", "apps-and-tools", "Apps and Tools for Sharing Your Faith", "Guide"),
]
for old, slug, title, fmt in RS:
    r = page(old)
    body = render(r["blocks"], title, drop=[r"^Latest Stories", r"^Do you want to take a step", r"^(Download|Get) the app"], skip_ul=True)
    body = polish(body, strip_heads=(title, "Apps &amp; Tools", "Apps & Tools"), cut_at=("<h3>Related Topics",), drop_p=(r"Learn More", r"Download it Now"))
    body = re.sub(r"<h2>\s*</h2>", "", body)
    if len(plain(body)) < 500:
        print("  resource too short, skipped:", slug)
        continue
    items.append({"type": "gcmn_resource", "slug": slug, "title": title, "excerpt": first_sentences(body, 170), "content": body, "dept": "Digital Strategies" if "apps" in slug else "Campus (Student-Led Movements)",
                  "meta": {"format": fmt}})

# ------------------------------------------------------------------ news: the 50th anniversary
gcmn50 = fetch("/content/dam/global/nigeria/gcmn50.jpeg.transform/CruHalf432x243/img.jpg", "gcmn-50th-anniversary.jpg")
items.append({
    "type": "post", "slug": "gcmn-marks-50-years", "title": "GCMN marks 50 years in Nigeria", "date": "2019-08-31", "categories": ["News"],
    "excerpt": "Great Commission Movement of Nigeria marked its 50th anniversary in August 2019.",
    "content": "<p>Great Commission Movement of Nigeria marked its 50th anniversary in August 2019. It was a fruitful and remarkable celebration, with visits to churches in different states of Nigeria between January and August 2019.</p>\n<p>The ministry began in Nigeria in 1969, when Rev. Yemi and Sue Ladipo brought it to the University of Lagos. <a href=\"/who-we-are/our-history/\">Read our story year by year</a>, or <a href=\"/partnership/\">come help change the world with us as a L.I.F.E. partner</a>.</p>",
    "image": gcmn50, "dept": "Communications", "meta": {},
})

# ------------------------------------------------------------------ settings
SETTINGS = {
    "tagline": "Win. Build. Send.",
    "intro": "For over 50 years, we have been taking the message of Jesus from campuses to corporate offices, from cities to rural communities, across Nigeria.",
    "mission": "Position and empower teams of mission-minded people in the 36 States and Federal Capital Territory who Win, Build and Send Christ-centered Multiplying Disciples to reach each State with the Gospel and raise labourers and resources for the global harvest.",
    "vision": "Movements everywhere so that everyone knows someone who truly follows Jesus.",
    "email": "info@gcmnigeria.org",
    "phone": "+234 810 003 9399",
    "hours": "Front desk 9 AM to 4 PM",
    "address": "10 Secretariat Road\nJos, Plateau State",
    "facebook": "https://facebook.com/gcmnig",
    "x": "https://twitter.com/gcmnig",
    "giving_accounts": "| Diamond Bank | 0003805731 | NGN | \n| Guaranty Trust Bank | 0025707701 | NGN | ",
    "giving_note": "Transfer or deposit to either account, or give through your nearest GCMN office. Then tell us what your gift is for, so it goes where you intend.",
    "giving_email": "info@gcmnigeria.org",
    "stats": "89 | Campuses with an active ministry | October 2026 | GCMN website (gcmnigeria.org)\n"
             "29 | States in Nigeria where we serve | October 2026 | GCMN website (gcmnigeria.org)\n"
             "170 | Nigerian languages in the Jesus Film Project | October 2026 | GCMN website (gcmnigeria.org)\n"
             "1969 | The year the ministry began in Nigeria | Our history | GCMN website (gcmnigeria.org)",
    "departments": "Communications\nFunding and Resource Mobilisation Team\nFinance\nLeadership",
    "routing": "general | info@gcmnigeria.org\npartnership | info@gcmnigeria.org\ngiving | info@gcmnigeria.org\nserve | info@gcmnigeria.org\nprayer | info@gcmnigeria.org\nstory | info@gcmnigeria.org",
}

MENUS = {
    "primary": [
        {"title": "Who we are", "page": "who-we-are"},
        {"title": "Strategies", "archive": "gcmn_strategy"},
        {"title": "Prayer", "item": "gcmn_strategy:prayer"},
        {"title": "Stories", "archive": "gcmn_story"},
        {"title": "Resources", "archive": "gcmn_resource"},
        {"title": "News", "page": "news"},
        {"title": "Partner", "page": "partnership"},
        {"title": "Serve", "page": "serve"},
        {"title": "Contact", "page": "contact"},
    ],
    "footer": [
        {"title": "Who we are", "page": "who-we-are"},
        {"title": "What we do", "page": "what-we-do"},
        {"title": "Strategies", "archive": "gcmn_strategy"},
        {"title": "Give", "page": "giving"},
        {"title": "Partner with us", "page": "partnership"},
        {"title": "Serve with us", "page": "serve"},
        {"title": "Contact", "page": "contact"},
    ],
}

bundle = {"site_title": "Great Commission Movement of Nigeria", "site_description": "Win. Build. Send.", "settings": SETTINGS, "pages": pages, "items": items, "menus": MENUS}
json.dump(bundle, open(os.path.join(OUT, "gcmn-content.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("pages", len(pages), "items", len(items), "media", len(os.listdir(MEDIA)))
