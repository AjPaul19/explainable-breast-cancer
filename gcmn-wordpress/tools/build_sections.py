"""Add the eight top-level sections of the old gcmnigeria.org navigation to the content bundle, with Elementor-ready layouts.

Reads and rewrites gcmn-core/content/gcmn-content.json (run build_content.py first, then this). It is safe to run again:
every page it owns is removed and re-added. All wording comes from the old site's pages (see CONTENT_REVIEW.md for the few
lines of plain interface text, such as the form introductions, that are new).
Run:  python tools/build_sections.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "gcmn-core", "content", "gcmn-content.json")
B = json.load(open(PATH, encoding="utf8"))

OWNED = {
    "home", "how-to-know-god", "life-questions", "common-questions", "train-and-grow", "spiritual-growth", "bible-studies",
    "life-and-relationships", "share-the-gospel", "help-others-grow", "leadership-training", "ministries", "opportunities",
    "internship-programme", "internship-application", "reference-questionnaire", "about-us", "need-prayer", "talk-to-a-mentor",
}
B["pages"] = [p for p in B["pages"] if p["slug"] not in OWNED]
by = {p["slug"]: p for p in B["pages"]}


def page(slug, title, content="", layout=None, parent="", order=50, dept="Communications", excerpt=""):
    p = {"slug": slug, "title": title, "content": content, "dept": dept, "order": order, "excerpt": excerpt}
    if parent:
        p["parent"] = parent
    if layout:
        p["layout"] = layout
    B["pages"].append(p)


def sections(*blocks):
    """(heading, paragraph) pairs -> h3 + p. A heading with None paragraph becomes an h2."""
    out = []
    for h, t in blocks:
        if t is None:
            out.append(f"<h2>{h}</h2>")
        else:
            out.append(f"<h3>{h}</h3>\n<p>{t}</p>")
    return "\n".join(out)


# ---------------------------------------------------------------- 1. How to know God
page("how-to-know-god", "How to know God", layout={
    "type": "hub", "eyebrow": "How to know God",
    "lead": "Do you ever wonder about what Christians believe? Who Jesus is, what he did, and why it matters? Get answers to these questions and more.",
    "tiles": [
        {"title": "Have you heard of the Four Spiritual Laws?", "text": "A simple way to understand God’s love, truth and hope.", "item": "gcmn_resource:the-four-spiritual-laws"},
        {"title": "Dealing with life’s questions", "text": "The meaning of life, whether God is real, and why God allows suffering.", "page": "life-questions"},
        {"title": "Common questions", "text": "Who is Jesus? What is a Christian? And how you can receive Christ.", "page": "common-questions"},
        {"title": "Stories of changed lives", "text": "The one God writes for each of us may go down many paths.", "archive": "gcmn_story"},
        {"title": "Talk to a mentor", "text": "Have more questions? Share them with someone who will listen.", "page": "talk-to-a-mentor"},
    ],
}, order=1, dept="Campus (Student-Led Movements)", excerpt="Answers about Jesus, faith and how to begin a relationship with God.")

page("life-questions", "Dealing with life’s questions", parent="how-to-know-god", order=2, dept="Campus (Student-Led Movements)",
     excerpt="Why do bad things happen? Is God good? What if these questions could be answered?",
     layout={"type": "doc", "eyebrow": "How to know God"}, content="""
<p>Why do you look the way you look? Why do bad things happen? What happens when you pray? Is God good? What if these questions could be answered?</p>
<h2>What is the meaning of life?</h2>
<h3>Is everything relative?</h3>
<p>One of the most common viewpoints held by college students today is the belief that “everything is relative”, meaning that there aren’t any absolute truths in the world. This article attempts to refute relativism and show how the existence of morality necessarily means that God exists.</p>
<h3>Finding purpose and meaning</h3>
<p>You are not alone if you have ever wondered about the meaning of life or your purpose. Browse stories of some who received an answer to this question.</p>
<h3>Can I find peace in a messed-up world?</h3>
<p>It’s human nature to pursue happiness by trying to rigorously work our way there. Here are stories of some who found true peace by doing just the opposite.</p>
<h3>Will I ever be happy?</h3>
<p>One atheist discovers true happiness by experiencing a love that brought him from a lifetime of doubt in God to an eternity of faith in Christ.</p>
<h2>Is God real?</h2>
<h3>Is there a God?</h3>
<p>Just once wouldn’t you love for someone to simply show you the evidence for God’s existence? No arm-twisting? No statements of “You just have to believe”? Well, here are six straightforward reasons to believe God exists.</p>
<h3>Is Jesus God?</h3>
<p>Who is Jesus? This article lays out our only three options of who Jesus is: a liar, a lunatic, or Lord.</p>
<h3>What about other religions?</h3>
<p>Are all religions worshipping the same God? Let’s consider that.</p>
<h3>Does God answer prayer?</h3>
<p>What is prayer? How is it done? What happens when you do it?</p>
<h2>Why does God allow suffering?</h2>
<h3>Where is God in a world of evil and suffering?</h3>
<p>Where is God during tragedies? How can I continue to believe in God?</p>
<h3>Why does God allow bad things to happen?</h3>
<p>Is there significance to the hard things that we face? How can any good come from them?</p>
<h3>How do I find hope while suffering?</h3>
<p>What are we to do with the wreckage that tragedy leaves in its wake? There is hope to be found.</p>
<h2>How can I know God?</h2>
<h3>Would you like to know God personally?</h3>
<p>What does it take to begin a relationship with God? Devote yourself to unselfish religious deeds? Become a better person so that God will accept you? You may be surprised that none of those things will work. But God has made it very clear in the Bible how we can know Him. <a href="/resources/the-four-spiritual-laws/">Read the Four Spiritual Laws</a>.</p>
""")

page("common-questions", "Common questions", parent="how-to-know-god", order=3, dept="Campus (Student-Led Movements)",
     excerpt="Who is Jesus? What is a Christian? How can I receive Christ?",
     layout={"type": "doc", "eyebrow": "How to know God"}, content="""
<h3>Who is Jesus?</h3>
<p>Analysing our three options to explain His identity: a liar, a lunatic, or Lord?</p>
<h3>What is a Christian?</h3>
<p>Confused about what it really means to be a Christian? Here’s a quick explanation.</p>
<h3>What makes Christianity different?</h3>
<p>Are we arrogant in thinking that Jesus is uniquely different and superior to any other person or belief system?</p>
<h3>Why do I need a Saviour?</h3>
<p>Supposedly I need Jesus. But why?</p>
<h3>Does Jesus give me hope?</h3>
<p>Against a pessimistic and fearful backdrop, Jesus Christ offers real hope to the world.</p>
<h3>What happens when I die?</h3>
<p>Since death is completely unavoidable for each of us, it’s necessary to confront the question “What happens when we die?”</p>
<h2>You can receive Christ right now by faith, through prayer</h2>
<p>Prayer is talking to God. God knows your heart and is not so concerned with your words as He is with the attitude of your heart. The following is a suggested prayer:</p>
<blockquote>Lord Jesus, I need You. Thank You for dying on the cross for my sins. I open the door of my life and receive You as my Saviour and Lord. Thank You for forgiving my sins and giving me eternal life. Take control of the throne of my life. Make me the kind of person You want me to be.</blockquote>
<p>If this prayer expresses the desire of your heart, then you can pray this prayer right now and Christ will come into your life, as He promised. <a href="/talk-to-a-mentor/">Talk to a mentor</a> about your next step.</p>
""")

# ---------------------------------------------------------------- 2. Train and grow
page("train-and-grow", "Train and grow", layout={
    "type": "hub", "eyebrow": "Train and grow",
    "lead": "Looking to move forward in your spiritual journey? We have the content to help you, from the core beliefs of the Christian faith to resources on prayer and fasting.",
    "tiles": [
        {"title": "Spiritual growth", "text": "Everyone has their own journey with the Lord. Move forward in yours.", "page": "spiritual-growth"},
        {"title": "Bible studies", "text": "Study the Bible on your own or with a group.", "page": "bible-studies"},
        {"title": "Life and relationships", "text": "Friendship, marriage, parenting, hardships, emotions, work and rest.", "page": "life-and-relationships"},
        {"title": "Share the gospel", "text": "Learn the heart of evangelism and ways to reach others for Christ.", "page": "share-the-gospel"},
        {"title": "Help others grow", "text": "Discipleship and leading small groups.", "page": "help-others-grow"},
        {"title": "Leadership training", "text": "Grow as a leader, start a ministry, lead and send a team.", "page": "leadership-training"},
    ],
}, order=2, dept="Leadership Development and Human Resource (LDHR)", excerpt="Resources to grow in your faith and help others grow.")

page("spiritual-growth", "Spiritual growth", parent="train-and-grow", order=1, dept="Leadership Development and Human Resource (LDHR)",
     excerpt="Everyone has their own spiritual journey with the Lord.", layout={"type": "doc", "eyebrow": "Train and grow"}, content="""
<p>Everyone has their own spiritual journey with the Lord. How can we help you move forward in yours today?</p>
<h3>Living the Spirit-filled life</h3>
<p>Every day can be an exciting adventure for the Christian who knows the reality of being filled with the Holy Spirit and who lives constantly, moment by moment, under His gracious direction.</p>
<h3>How your personality connects you with God</h3>
<p>Is it possible that we don’t experience God like everyone else because God didn’t intend us to? Worship has the potential to be a part of everyday life, and God has hardwired each of us to experience Him in our own unique ways.</p>
<h2>Go deeper on your spiritual journey</h2>
<h3>10 basic steps to Christian maturity</h3>
<p>Takes a new Christian from “who is Jesus?” to topics such as the Holy Spirit, prayer, witnessing, and a survey of both the Old and New Testaments.</p>
<h3>Transferable concepts</h3>
<p>The essential “how tos” which every Christian, newborn or with many years of maturity, needs to know and remember.</p>
<h3>Fasting</h3>
<p>Fasting (intentionally abstaining from food) is a powerful way to connect with the Lord. Explore step-by-step guides on fasting and learn how to apply this practice in your spiritual journey.</p>
<h3>Prayer</h3>
<p>Prayer is a powerful act of talking to God, but how do you pray? How do you connect with God? Explore articles about prayer and ways to apply them both individually and with other people.</p>
<h3>Devotionals and quiet times</h3>
<p>Don’t know how to spend time with God? These devotionals and articles will help you draw closer to the Lord while providing a variety of options to fit your personality.</p>
<h2>Read now</h2>
<ul>
<li><a href="/resources/five-spiritual-disciplines/">5 spiritual disciplines to help grow your walk with God</a></li>
<li><a href="/resources/five-things-to-live-the-life-god-intended/">5 things you need to live the life God intended</a></li>
</ul>
""")

page("bible-studies", "Bible studies", parent="train-and-grow", order=2, dept="Leadership Development and Human Resource (LDHR)",
     excerpt="Whether you want to study the Bible on your own or with a group.", layout={"type": "doc", "eyebrow": "Train and grow"}, content="""
<p>Whether you want to study the Bible on your own or with a group, find resources here to help you do that.</p>
<h3>Personal Bible study</h3>
<p>Study on your own, at your own pace.</p>
<h3>Group Bible study</h3>
<p>Study with others and ask the hard questions together.</p>
<p>Want to study with someone? <a href="/talk-to-a-mentor/">Talk to a mentor</a>.</p>
""")

page("life-and-relationships", "Life and relationships", parent="train-and-grow", order=3, dept="FamilyLife",
     excerpt="Explore the questions you have about navigating through life.", layout={"type": "doc", "eyebrow": "Train and grow"}, content="""
<blockquote>Be completely humble and gentle; be patient, bearing with one another in love. Make every effort to keep the unity of the Spirit through the bond of peace.</blockquote>
<h3>Friendship</h3>
<p>Who you choose to surround yourself with is one of the most important and influential decisions you can make. Explore topics ranging from how you can be a better friend to what kind of friends you need the most.</p>
<h3>Dating</h3>
<p>Many people face challenges when it comes to dating. These articles will help guide you through dating, what it looks like and how to keep God at the centre of the relationship.</p>
<h3>Marriage</h3>
<p>Struggling in your marriage? Looking for tips to help you grow in your relationship with your spouse? Browse through these articles to help you draw closer to your spouse and to the Lord.</p>
<h3>Parenting</h3>
<p>Parenting can be one of the hardest things people do, but also rewarding. God calls parents to teach their children.</p>
<h3>For men</h3>
<p>As men, God created you with unique personalities and different roles in your lives. Men struggle with different issues and face questions. Check out these topics that will help address struggles and other factors that men face.</p>
<h3>For women</h3>
<p>Every woman has struggles she faces in her life. Am I good enough? Why do I look the way I do? How far is too far? Explore answers to these questions and more.</p>
<h3>Hardships</h3>
<p>Life is not easy. Everyone struggles with hardships in their lives. How do we deal when hardship strikes? What steps can we take?</p>
<h3>Emotions</h3>
<p>All humans are created with emotions, but how do you deal with emotions when they feel out of control? Explore topics such as anger, depression, anxiety and more.</p>
<h3>Work and rest</h3>
<p>As humans, we seem to bounce between too much work and too much rest, but can we find a healthy middle ground? Topics include ambition, calling, and knowing when and how to rest.</p>
""")

page("share-the-gospel", "Share the gospel", parent="train-and-grow", order=4, dept="Digital Strategies",
     excerpt="Sharing our faith is one of our most important callings as followers of Jesus.", layout={"type": "doc", "eyebrow": "Train and grow"}, content="""
<p>Sharing our faith is one of our most important callings as followers of Jesus. Learn about the heart of evangelism and engaging strategies you can use to help reach others for Christ.</p>
<h2>Using digital tools for evangelism</h2>
<p>At GCMN, we’ve seen firsthand how digital tools can be used for advancing the Great Commission. Digital allows access to places and people that have never been reachable before, and we want you to be a part of reaching people with the gospel. <a href="/resources/apps-and-tools/">Apps and tools for sharing your faith</a>.</p>
<h2>More on sharing your faith</h2>
<h3>Evangelism principles</h3>
<p>Sharing your faith is an opportunity for people to hear the gospel and respond to Jesus. These topics will help you grow in understanding evangelism and how to go about sharing your faith.</p>
<h3>Outreach strategies</h3>
<p>There are many ways to share your faith with people in your life, on campus and in the workplace. Browse tools and strategies to help you share the gospel and have spiritual conversations.</p>
<h3>Obstacles to faith</h3>
<p>Have people asked you questions about faith and you don’t know what to say? Browse these topics to help guide you through tough questions about faith.</p>
""")

page("help-others-grow", "Help others grow", parent="train-and-grow", order=5, dept="Leadership Development and Human Resource (LDHR)",
     excerpt="Therefore go and make disciples of all nations.", layout={"type": "doc", "eyebrow": "Train and grow"}, content="""
<blockquote>Therefore go and make disciples of all nations, baptizing them in the name of the Father and of the Son and of the Holy Spirit, and teaching them to obey everything I have commanded you. And surely I am with you always, to the very end of the age. (Matthew 28:19-20)</blockquote>
<h3>Discipleship</h3>
<p>Discipleship is spending time with someone regularly talking about God, the Bible, and daily life. Whether you’re just getting started or looking to go deeper with your disciple, these articles will give you tips and resources to live out this practice in a way that effectively multiplies the Kingdom.</p>
<h3>Leading small groups</h3>
<p>Small groups and Bible studies are great ways to embrace community and fellowship, grow in knowledge of the Bible and ask the hard questions. These articles will help you as a leader to engage your small group.</p>
<h3>Top tools for transferable training</h3>
<p>Ministry becomes effective when we accurately apply specific tools, using biblical strategies, under the power of the Holy Spirit. To get the job done, here are some of the tools to consider adding to the top drawers of your tool chest.</p>
""")

page("leadership-training", "Leadership training", parent="train-and-grow", order=6, dept="Leadership Development and Human Resource (LDHR)",
     excerpt="Grow as a leader, start a ministry, lead a team and send it out.", layout={"type": "doc", "eyebrow": "Train and grow"}, content="""
<blockquote>So he shepherded them according to the integrity of his heart, and guided them with his skilful hands. (Psalm 78:72)</blockquote>
<h3>Leader development</h3>
<p>Looking to grow in your leadership skills? These topics will help you thrive as a leader to bring your team closer to the Lord and in line with the mission and vision.</p>
<h3>Starting a ministry</h3>
<p>Want to start a ministry but don’t know where to turn? Browse these topics to learn where to begin and ways to engage and strengthen your ministry.</p>
<h3>Leading a team</h3>
<p>Once you have a ministry team, now what? These topics will help guide you in leading your team in ministry and continuing to work towards your vision and mission.</p>
<h3>Sending your team</h3>
<p>Wondering what is next for your team? Browse these topics on sending your team out to live the missional life the Lord has called them to.</p>
""")

# ---------------------------------------------------------------- 3. Ministries
page("ministries", "Ministries", layout={
    "type": "hub", "eyebrow": "Ministries",
    "lead": "Great Commission Movement of Nigeria has a number of strategies that offer many ministry opportunities.",
    "tiles": [
        {"title": "Prayer", "text": "An intercessor in every tribe and city.", "item": "gcmn_strategy:prayer"},
        {"title": "Campus", "text": "Students who lead other students to Christ, build them and send them.", "item": "gcmn_strategy:campus-student-led-movements"},
        {"title": "FamilyLife", "text": "Practical, scripture-based help for couples and families.", "item": "gcmn_strategy:familylife"},
        {"title": "Digital ministry", "text": "Helping people know Jesus, grow and go, using digital tools.", "item": "gcmn_strategy:digital-strategies"},
        {"title": "Jesus Film Project", "text": "Media tools and training for evangelism in every needed language.", "item": "gcmn_strategy:jesus-film-project"},
        {"title": "All ministries", "text": "Every strategy, from athletes to schools to aid.", "archive": "gcmn_strategy"},
    ],
}, order=3, dept="Leadership", excerpt="The strategies that offer many ministry opportunities.")

# ---------------------------------------------------------------- 4. Opportunities
page("opportunities", "Opportunities", layout={
    "type": "hub", "eyebrow": "Opportunities",
    "lead": "The harvest is plentiful but the workers are few. It does not matter what your career or profession is, there is always a place for you to serve.",
    "tiles": [
        {"title": "Join the Great Commission", "text": "Full-time, associate or volunteer staff, short-term, or a L.I.F.E. partner.", "page": "serve"},
        {"title": "Internship programme", "text": "Give God 6 months to 1 year of unforgettable adventure.", "page": "internship-programme"},
        {"title": "Internship application", "text": "Apply to become an intern.", "page": "internship-application"},
        {"title": "Reference questionnaire", "text": "For the reference who is filling it in for an intern.", "page": "reference-questionnaire"},
    ],
}, order=4, dept="Leadership Development and Human Resource (LDHR)", excerpt="Ways to serve, from volunteering to internships and staff.")

page("internship-programme", "Internship programme", parent="opportunities", order=1, dept="Leadership Development and Human Resource (LDHR)",
     excerpt="Give God 6 months to 1 year of unforgettable adventures.", layout={"type": "doc", "eyebrow": "Opportunities", "after": ""}, content="""
<p>Great Commission Movement (GCMN) offers you an opportunity to give God 6 months to 1 year of unforgettable adventures.</p>
<h2>You can discover purpose</h2>
<ul>
<li>Receive an orientation to GCM.</li>
<li>Evangelism and discipleship training will enable you to grow deeper in your knowledge of God in conviction, competence, character and ministry skills.</li>
<li>A taste of mission outreaches in 8 strategies.</li>
<li>Leadership development.</li>
<li>Cross-cultural missions training.</li>
<li>Fun team building.</li>
<li>Gain fund development and executive functioning skills for ministry.</li>
</ul>
<p><a href="/opportunities/internship-application/">Apply for the internship</a>. A reference fills in the <a href="/opportunities/reference-questionnaire/">reference questionnaire</a> for you.</p>
""")

page("internship-application", "Internship application", parent="opportunities", order=2, dept="Leadership Development and Human Resource (LDHR)",
     excerpt="Apply to give God 6 months to 1 year.", layout={
         "type": "split", "eyebrow": "Opportunities",
         "lead": "Tell us about yourself and why you want to serve as an intern. We will reply by email.",
         "shortcode": '[gcmn_contact topic="internship" button="Send my application" label="About you and your calling"]'})

page("reference-questionnaire", "Reference questionnaire", parent="opportunities", order=3, dept="Leadership Development and Human Resource (LDHR)",
     excerpt="A reference fills this in for an intern.", layout={
         "type": "split", "eyebrow": "Opportunities",
         "lead": "A reference fills this in for the intern. Please give your name, say whose reference you are, and tell us what you know of them.",
         "shortcode": '[gcmn_contact topic="reference" button="Send reference" label="Your reference for the intern"]'})

# ---------------------------------------------------------------- 5. About us
page("about-us", "About us", layout={
    "type": "hub", "eyebrow": "About us",
    "lead": "For over 50 years, we have been taking the message of Jesus from campuses to corporate offices, from cities to rural communities, across Nigeria.",
    "tiles": [
        {"title": "Our mission", "text": "Win, build and send Christ-centred multiplying disciples.", "page": "who-we-are"},
        {"title": "Our values", "text": "What we hold to as we serve.", "page": "our-values"},
        {"title": "What we do", "text": "How we journey with everyone towards a relationship with Jesus.", "page": "what-we-do"},
        {"title": "Our history", "text": "Our story year by year, since 1969.", "page": "our-history"},
        {"title": "Statement of faith", "text": "What we believe.", "page": "statement-of-faith"},
        {"title": "Contact", "text": "Our offices and how to reach them.", "page": "contact"},
    ],
}, order=5, dept="Leadership", excerpt="Who we are, what we believe and how to reach us.")

# ---------------------------------------------------------------- 7 and 8. Prayer and mentor
page("need-prayer", "Need prayer", layout={
    "type": "split", "eyebrow": "Need prayer",
    "lead": "Tell us what you would like prayer for. Choose a mentor, and your request goes to them alone. They will pray with you and reply by email.",
    "shortcode": '[gcmn_contact topic="prayer" mentors="1" button="Send my prayer request" label="Your prayer request"]'},
     order=7, dept="Prayer", excerpt="Share your prayer request with a mentor.")

page("talk-to-a-mentor", "Talk to a mentor", layout={
    "type": "split", "eyebrow": "Talk to a mentor",
    "lead": "Share what you are going through with someone who will listen. Choose a mentor, give your name and email, and write your message. It goes to your mentor alone.",
    "shortcode": '[gcmn_contact topic="mentor" mentors="1" button="Send to my mentor" label="Your message"]'},
     order=8, dept="Prayer", excerpt="Share what you are going through with a mentor.")

# ---------------------------------------------------------------- the existing pages, laid out
if "giving" in by:
    g = by["giving"]
    g["layout"] = {"type": "doc", "eyebrow": "Give", "before": "[gcmn_giving]"}
    g["order"] = 6
if "contact" in by:
    c = by["contact"]
    c["layout"] = {"type": "doc", "eyebrow": "About us"}
for slug, eb in (("who-we-are", "About us"), ("our-values", "About us"), ("our-history", "About us"), ("statement-of-faith", "About us"),
                 ("what-we-do", "About us"), ("partnership", "Give"), ("serve", "Opportunities")):
    if slug in by:
        by[slug]["layout"] = {"type": "doc", "eyebrow": eb}
if "serve" in by:
    by["serve"]["title"] = "Join the Great Commission"

# ---------------------------------------------------------------- home
S = B["settings"]
page("home", "Home", layout={
    "type": "home", "eyebrow": "Great Commission Movement of Nigeria", "title": S.get("tagline", "Win. Build. Send."),
    "lead": "For over 50 years, we have been taking the message of Jesus from campuses to corporate offices, from cities to rural communities, across Nigeria.",
    "stats": True, "cta": {"title": "How to know God", "page": "how-to-know-god"},
    "tiles": [
        {"title": "How to know God", "text": "Who Jesus is, what he did and why it matters.", "page": "how-to-know-god"},
        {"title": "Train and grow", "text": "Move forward in your spiritual journey.", "page": "train-and-grow"},
        {"title": "Ministries", "text": "Strategies that offer many ministry opportunities.", "page": "ministries"},
        {"title": "Opportunities", "text": "Give God 6 months to 1 year of adventure.", "page": "opportunities"},
        {"title": "About us", "text": "Over 50 years across Nigeria.", "page": "about-us"},
        {"title": "Give", "text": "Support the Great Commission.", "page": "giving"},
        {"title": "Need prayer", "text": "Share your request with a mentor.", "page": "need-prayer"},
        {"title": "Talk to a mentor", "text": "Share what you are going through.", "page": "talk-to-a-mentor"},
    ],
}, order=0, dept="Communications")

# ---------------------------------------------------------------- mentors setting: left empty on purpose (people to be named by GCMN)
S.setdefault("mentors", "")
S["routing"] = S.get("routing", "") + "\nmentor | info@gcmnigeria.org\ninternship | info@gcmnigeria.org\nreference | info@gcmnigeria.org"

# ---------------------------------------------------------------- menus
def sub(title, **k):
    d = {"title": title}
    d.update(k)
    return d


B["menus"] = {
    "primary": [
        sub("How to know God", page="how-to-know-god", children=[
            sub("Four Spiritual Laws", item="gcmn_resource:the-four-spiritual-laws"),
            sub("Life’s questions", page="life-questions"),
            sub("Common questions", page="common-questions"),
            sub("Stories", archive="gcmn_story"),
        ]),
        sub("Train and grow", page="train-and-grow", children=[
            sub("Spiritual growth", page="spiritual-growth"),
            sub("Bible studies", page="bible-studies"),
            sub("Life and relationships", page="life-and-relationships"),
            sub("Share the gospel", page="share-the-gospel"),
            sub("Help others grow", page="help-others-grow"),
            sub("Leadership training", page="leadership-training"),
        ]),
        sub("Ministries", page="ministries", children=[
            sub("Prayer", item="gcmn_strategy:prayer"),
            sub("Campus", item="gcmn_strategy:campus-student-led-movements"),
            sub("FamilyLife", item="gcmn_strategy:familylife"),
            sub("Digital ministry", item="gcmn_strategy:digital-strategies"),
            sub("Jesus Film Project", item="gcmn_strategy:jesus-film-project"),
            sub("All ministries", archive="gcmn_strategy"),
        ]),
        sub("Opportunities", page="opportunities", children=[
            sub("Join the Great Commission", page="serve"),
            sub("Internship programme", page="internship-programme"),
            sub("Internship application", page="internship-application"),
            sub("Reference questionnaire", page="reference-questionnaire"),
        ]),
        sub("About us", page="about-us", children=[
            sub("Our mission", page="who-we-are"),
            sub("Our values", page="our-values"),
            sub("What we do", page="what-we-do"),
            sub("Our history", page="our-history"),
            sub("Statement of faith", page="statement-of-faith"),
            sub("Contact", page="contact"),
        ]),
        sub("Need prayer", page="need-prayer"),
        sub("Talk to a mentor", page="talk-to-a-mentor"),
        sub("Give", page="giving", **{"class": "g-nav-give"}),
    ],
    "footer": [
        sub("How to know God", page="how-to-know-god"),
        sub("Train and grow", page="train-and-grow"),
        sub("Ministries", page="ministries"),
        sub("Opportunities", page="opportunities"),
        sub("About us", page="about-us"),
        sub("Give", page="giving"),
        sub("Partner with us", page="partnership"),
        sub("Contact", page="contact"),
    ],
}

json.dump(B, open(PATH, "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("pages", len(B["pages"]), "items", len(B["items"]))
