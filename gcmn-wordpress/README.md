# GCMN website: theme and plugin

Two parts, installed together:

| Part | What it is |
| --- | --- |
| `gcmn-theme` | A child of the free **Hello Elementor** theme. All templates (home, pages, strategies, stories, events, resources, prayer, opportunities, giving, contact) are theme files, so **Elementor Pro is not needed**. Elementor Free still works for editing any ordinary page. |
| `gcmn-core` | The plugin: content types, the submit → review → approve → publish → quality check → record workflow, the staff submission form, enquiries, giving details, daily freshness checks and the content importer. |

Brand: the GCMN Brand Guide (August 2026). Montserrat and Source Sans 3 are bundled in the theme (no external font requests).

## Install

1. Install and activate the free **Hello Elementor** theme (Appearance > Themes > Add New). It is the parent theme.
2. Upload `gcmn-core.zip` (Plugins > Add New > Upload) and activate it. **The website's content loads by itself at this point**: the pages, 16 strategies, stories, resources, news item, menus, contact details, giving accounts, numbers and photos from the previous website. Allow up to a minute. If your host stops it early, a notice offers a single **Load the website content** button.
3. Upload `gcmn-theme.zip` (Appearance > Themes > Add New > Upload) and activate it. The menus attach to the theme automatically.
4. Read [CONTENT_REVIEW.md](CONTENT_REVIEW.md), check the items listed under "Please confirm", then open **Settings > GCMN site** to adjust any detail.

Activation also creates the pages the plugin needs (Home as the front page, News and updates, Contact, Submit content) and removes WordPress's sample post and page.

## Where the content comes from

All of it is the previous website's content, gathered on 23 October 2026 from gcmnigeria.org, and shipped inside the plugin (`gcmn-core/content/gcmn-content.json` with its images). `CONTENT_REVIEW.md` lists what each page came from, what was reworded, what was left out and why. After launch, content is managed through the normal workflow below, not by re-importing.

To rebuild the bundle from a fresh copy of the old site, use `tools/build_content.py`. To load a bundle on another site with WP-CLI: `wp gcmn import path/to/gcmn-content.json --media=path/to/media`.

## How content gets published

This is the standard workflow from the GCMN Website Implementation System, built into the site. The one change in order: the quality check is done on the preview just before publishing, because the site enforces it as a gate, and the live page is checked once more after it goes out. Nothing reaches the public site without passing through it.

    CONTENT OWNER -> SUBMIT -> REVIEW -> APPROVE -> QUALITY CHECK -> PUBLISH -> RECORD -> REVIEW AGAIN

### Who does what

| Step | Who | Where in WordPress | What happens |
| --- | --- | --- | --- |
| 1. Identify | Content Owner (each strategy or department names one) | | Decides what should be on the website: a ministry update, story, event, resource, prayer need or partnership opportunity. |
| 2. Submit | Content Owner | **Submit content** page (staff sign in first) | Fills the Website Content Submission Form and presses **Submit for review**. The item is saved as *pending review* and the Content Editor is emailed. The owner cannot publish. |
| 3. Review | Content Editor (Communications) | **Content tracker**, then open the item | Checks accuracy, completeness, relevance, images, links and sensitive information. Edits the text, chooses where it belongs, sets the department, and records whether approval is needed. The editor cannot publish either. |
| 4. Approve | The responsible person named in the form (strategy leader, Leadership or Finance) | The **Review and approval** box | Approves by telling the editor. The editor ticks **Approved** and types the approver's name. |
| 5. Quality check | Website Administrator | **Preview** on the item, then the **Quality check done** box | Previews the page and checks spelling, formatting, images, links, contact details and the phone view, then ticks the box. The site will not publish an item until this is ticked. |
| 6. Publish | Website Administrator | The item's **Publish** button | Publishes once the gates below are met. After it is live, open the public page once more to confirm it looks right. |
| 7. Record | Automatic | **Content tracker** | Every item is listed with its type, department, stage, approver, publish date and next review date. Download it as CSV for the monthly review. |
| 8. Review again | Automatic, then the owner | Email reminder | When the next review date arrives the owner and the editor are emailed. The owner confirms, updates or retires the item. To confirm an item is still correct, open it and press **Update**: that moves the review date forward. |

### The submission form

The form asks for what the Implementation System lists: department or strategy, content title, content type, main content or story, date and location, statistics, photos, videos and links, contact person, desired publication date, approval required, call to action, and a box for sensitive or restricted information.

| Content type chosen | Where it lands |
| --- | --- |
| News, Ministry update, Staff update | A post in the matching category (News and updates) |
| Testimony | A story (Stories) |
| Event | An event (Events) |
| Resource | A resource (Resources) |
| Prayer request | A prayer need (Prayer) |
| Partnership opportunity | An opportunity (Partnership) |

Photos must be JPEG, PNG or WebP, up to 8 files and 5 MB each. The first photo becomes the lead image.

### The gates: what stops an item being published

When anyone presses Publish, the site checks these. If one fails, the item is saved as **pending review** instead and the person sees a message saying why.

1. **Quality check** is ticked.
2. **Approval** is recorded if one was asked for. An item marked *sensitive or restricted* always needs **Leadership** approval, whatever was chosen.
3. For a **story**, the box confirming the people in it agreed in writing is ticked.

Events, opportunities and prayer needs also carry a date after which they leave the site (below). Pages the plugin manages itself (Home, News and updates, Contact, Submit content) are not part of the workflow.

### Stages shown in the tracker

| Stage | Meaning |
| --- | --- |
| Draft | Being written, not submitted |
| In review | Submitted, waiting for the Content Editor |
| Awaiting approval | Needs an approval that has not been recorded |
| Approved | Approved, quality check not yet done |
| Ready to publish | Approved and quality-checked |
| Published | Live on the site |
| Needs update | Live, but past its next review date |

### Keeping content current

Every item has a **next review** date. If it is left empty, the site fills it in on publishing:

| Type | Default review | Leaves the site |
| --- | --- | --- |
| Prayer need | 7 days | On its *Show until* date, or three weeks after publishing |
| Event | 30 days | The day after it ends |
| Partnership opportunity | 30 days | On its *Closes* date |
| News, ministry and staff updates, stories, resources, strategies | 90 days | Stays until the owner retires it |
| Pages | 180 days | Stays until the owner retires it |

These are starting points; the editor can set a shorter date on any item. The Implementation System asks for priority pages to be reviewed monthly, so set a monthly date on those (Who we are, Partnership, Giving, Serve, Contact).

Each day the site automatically:

- emails each department's owner (set in **Settings > GCMN site > Departments**) and the Content Editor a list of items past their review date, once per item per day, and marks them *Needs update*;
- takes expired events, opportunities and prayer needs offline. Visitors never see them even before the daily run, and their own web addresses show "not found".

### The time rhythm

| When | What the team does |
| --- | --- |
| Within 24 to 48 hours | Publish significant updates, events, stories and time-sensitive items |
| Weekly | Review and publish current stories, news and ministry updates |
| Monthly | Review priority pages, partnership information, prayer and upcoming activities, using the tracker |
| Quarterly | Review strategy pages, impact numbers, stories and resources |
| Annually | Review who-we-are information, staff information and annual reports |
| As needed | Update contact details, giving details and opportunities |

### Special cases

- **Giving details.** Only site administrators can change the accounts in **Settings > GCMN site**. As a team rule, Finance approves any change and a second person checks it by a separate channel before it is saved. The site cannot enforce this, so keep it as a written procedure.
- **Editing an item that is already live.** The Website Administrator edits and presses **Update**. Saving a live item whose review date has passed moves the date forward by the default interval and clears *Needs update*.
- **Retiring content.** Set it back to Draft. It leaves the site immediately and stays in the tracker.
- **Pages from the old site.** The importer marks them approved and quality-checked, so the site can open with real content. Their review dates start from the day they are imported.
- **Enquiries.** Messages from the Contact page go to the address set under *Where enquiries go*, are saved under **Enquiries**, and are marked handled when a person has replied.

## Everything from the old website, editable in Elementor

The content of the old gcmnigeria.org (the offline copy in `C:\My Web Sites\Indigitous`) is loaded into the site: about 270 pages, 41 stories, the 16 ministries, the four resources and the news item, all at the same addresses they had before, in the same sections and sub-sections. Any old address (with or without `.html`) still works: it redirects to the new page (about 970 redirects).

**The eight sections** follow the old navigation: How to know God, Train and grow, Ministries, Opportunities, About us, Give, Need prayer and Talk to a mentor. The menu has drop-downs and sub-drop-downs (for example Train and grow > Life and relationships > Dating) on large screens and a full-screen list on phones. Give is the one highlighted button.

**Every part of every page is edited by drag and drop in Elementor Free.** Install the free Elementor plugin from WordPress.org, open any page and choose Edit with Elementor. Headings, text, tiles, buttons, link lists, forms, the header and the footer are all Elementor elements; nothing is fixed in code. The header and footer are under **Website system > Header and footer**. The plugin adds a **GCMN** group of elements to Elementor: **GCMN Menu** (the site menu with drop-downs), **GCMN Block** (the numbers, giving accounts, contact details and the request forms) and **GCMN Pages and items** (a grid of stories, ministries, resources, news or the pages under a page). The brand colours and fonts appear in Elementor's colour and font pickers. Stories, ministries and resources can also be opened in Elementor.

Content you have edited is never overwritten: loading the content again only adds what is missing.

**Loading the content.** After you install or update the plugin, open the WordPress dashboard: a progress bar loads the pages, stories, ministries, menus, header and footer in small steps (about two minutes). Keep the page open; if the host interrupts it, press Try again and it continues where it stopped. Until it finishes, the home page shows the designed hero with the menu items as tiles, never a blank page. WP-CLI can do it in one go: `wp gcmn import content/gcmn-content.json --media=content/media`.

**Where the old site was incomplete.** The offline copy held only the text of many articles' first part, and most photographs were blocked when it was made (403 errors), so those pages show the text that was saved and no picture. Pages that were error pages (404) on the old site are not recreated. See `CONTENT_REVIEW.md`.

**Pictures and motion.** Every page has a background picture taken from the old website's own pictures: the sections have their own (the night sky on Home, an open Bible on Train and grow, and so on), and a page whose topic has a picture of its own (Fasting, Discipleship, Hardships ...) shows it. Ministries and many topic tiles show their photo. Pictures are set in Elementor's Style tab (Background and Background Overlay), so you can change any of them. Each section has its own accent colour; tiles rise in one by one, light up under the cursor and grow a picture on hover; the numbers on Home count up; reading pages have a picture banner that drifts as you scroll, a thin reading-progress bar and an "In this section" menu beside the text. Visitors who prefer less motion see none of the movement.

**One screen.** On a large screen the home page, every section page and the two request forms fit one screen without scrolling. Long reading pages scroll, with their title beside the text. On phones every page scrolls.

**Need prayer** and **Talk to a mentor** take a name, an email and a message, and the visitor chooses a mentor. The message goes to that mentor's email. Name the mentors under **Settings > GCMN site > People and emails > Mentors** (`Name | email | what they help with`). Their emails are never shown on the site.

**Rebuilding the content file** (only if the offline copy changes): `python tools/build_all.py`.

## Emails, and who decides to send them

Fill in **Settings > GCMN site > People and emails** first: the Website Administrator, Content Editor, Website Oversight, Leadership, Finance and Technical support emails, and one line per department or strategy in the form `Name | Content Owner email | Strategy leader email`.

**The site never emails a Content Owner by itself.** When something needs an owner (an item past its review date, changes requested, an audit finding, an action from the monthly review), it prepares the message and puts it in **Website system > Owner emails**. The Website Administrator is told, by one email, that messages are waiting. Each message leaves only when that person presses **Send**; they can edit the address and the words, **Dismiss** it, or **Send all**. Only the Website Administrator role (and site administrators) can send. The same message is never queued twice.

Other emails: the Content Editor is told of each new submission; the approver is asked once the Editor ticks **Reviewed**; Website Oversight and the Website Administrator get the monthly review reminder.

## The Website system menu

One menu, built from the Website Implementation System: **Content tracker**, **Owner emails** (with a count of messages waiting), **Website audit** (the ten priority areas: current, needs updating, needs replacement or removal, missing), **Monthly review** (the eight questions answered from the site, ending in who, what, by when), **Measures** (the ten measures of success, read live), **Training** (eleven skills per person), **90-day plan** and **Who owns what**.

## Formatted text and search engines

The submission form, the page editor and the home page introduction, mission, vision and giving instructions all take formatted text (bold, italic, lists, quotes, links, headings). Only safe formatting is kept. Every page can set its own **Search appearance** (title and description); if left empty they come from the page. The site outputs titles, descriptions, canonical links, Open Graph and Twitter tags, JSON-LD (Organization, WebSite, page type, breadcrumbs, articles, events with a date), a sitemap without staff pages, and alt text on every image. Staff pages and the 404 page are not indexed.

## What the site never shows

Owners, reviewers, review dates, workflow status, empty sections or filler text. A section appears only when it has content, and a number appears only with its date and source.

## People and roles

| Role | Can do |
| --- | --- |
| Content Owner (strategy or department) | Write and submit. Cannot publish. |
| Content Editor (Communications) | Review and edit everyone's work. Cannot publish. |
| Website Administrator | Publish approved content. |
| Administrator | Everything, including Settings. |

An item cannot be published until the quality check is ticked, any approval it needs is recorded and (for stories) consent is confirmed. Otherwise it is saved as pending review and the person is told why. The **Content tracker** lists every item with its stage, approver and next review date, and downloads as CSV. A daily task emails owners and the editor about content past its review date, and takes events, prayer needs and opportunities offline when their date passes.

## Security notes

Staff submissions and enquiries use nonces, capability checks, a hidden spam field and a rate limit. Uploads accept only JPEG, PNG and WebP up to 5 MB. Output is escaped. Keep WordPress, the two parent/child themes and every plugin updated, use two-factor sign-in for editors, and keep tested off-site backups.

## Test

`tools/smoke_real.py` checks the real site against a throwaway WordPress (WordPress Playground, with and without Elementor): every page renders, the real facts are present, no filler or internal text appears, every internal link works and no screen offers more than one action beside the menu. `tools/smoke.py` and `tools/behaviour.php` test the templates and the publishing rules with a small test fixture that is never packaged. Build the installable zips with `python tools/package.py`.
