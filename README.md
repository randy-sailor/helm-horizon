# Helm & Horizon

A monthly market briefing for yacht industry leaders — brokers, dealers, and builders.
Published at [thehelmandhorizon.com](https://thehelmandhorizon.com).

Every figure in every edition is cited to a primary source: NMMA retail data, SEC filings and
earnings calls from MarineMax (NYSE: HZO), Brunswick (NYSE: BC), and OneWater Marine (NASDAQ: ONEW),
Boat International's order book, and charter and insurance market reporting.

## Stack

Static HTML, CSS, and vanilla JavaScript. No build step, no framework, no dependencies.
Hosted on Vercel; `vercel.json` handles clean URLs, cache headers, and CSP.

Because there is no build step, `base.css` and `site.js` have no content hash in their
filenames, so they are served `max-age=0, must-revalidate` (cheap 304s, and edits go live
immediately). Only `/assets/img/` is cached immutably for a year — rename an image rather than
replacing it in place.

The HTML references them as `base.css?v=2` and `site.js?v=2`. That query string is a cache key,
added because the site originally served these files `immutable, max-age=31536000`: browsers
that loaded the site before the header was corrected had them pinned for a year and would not
revalidate. **If you ever change either file in a way that must reach returning visitors
immediately, bump the number in all six HTML pages.** Vercel matches header rules on the path,
so the `must-revalidate` rule still applies with a query string attached.

## Layout

```
index.html                     Home — current edition lede and recent issues
editions/september-2026.html   Full edition, one file per issue
archive.html                   All editions with PDF downloads
about.html                     Masthead, methodology, sourcing standards
subscribe.html                 Email list signup
submit.html                    Reader submissions for "Voices from the Field"
assets/base.css                Design system and all page styles
assets/site.js                 Mobile nav, scroll reveal, form handling
assets/img/                    WebP imagery
pdf/                           PDF companion for each edition
confirmed.html                 Landing page after a successful confirmation
confirm-failed.html            Landing page for a bad or expired link
api/subscribe.js               Creates a pending contact, sends the confirm link
api/confirm.js                 Verifies the link and activates the contact
api/submit.js                  Emails a reader submission to the editor
api/_lib.js                    Shared validation, guards, signing, Resend client
api/_email.js                  Branded HTML + plain-text email templates
tools/build-edition-email.js   Turns an edition page into a branded email
emails/                        Generated email editions, for Resend Broadcasts
content/editions/*.json        The editions themselves — source of truth
tools/                         Draft, validate, render, and compare editions
.github/workflows/             Monthly drafting, and edition validation on every PR
docs/email-setup.md            Resend + ImprovMX DNS and configuration
```

## Design system

Defined as custom properties at the top of `assets/base.css`.

| Token | Value | Use |
| --- | --- | --- |
| `--navy` | `#0b2a4a` | Primary brand |
| `--navy-deep` | `#06192e` | Masthead, dark sections |
| `--gold` | `#c9a55a` | Accent, rules, CTAs |
| `--paper` | `#f7f5f0` | Page background |
| `--ink` | `#14202c` | Body text |

Type is Zodiak (display) and Satoshi (body), served from Fontshare.

## Adding an edition

An edition is **data first**. `content/editions/<slug>.json` is the source of truth;
the page in `editions/` is generated from it and should not be hand-edited, because
the next render will overwrite it.

```
content/editions/<slug>.json   The edition — the only file you edit by hand
tools/draft_edition.py         Researches a month and writes that JSON
tools/validate_edition.py      Refuses an edition that breaks the standard
tools/render_html.py           JSON -> the page, plus index/archive/sitemap/vercel
tools/render_pdf.py            JSON -> the PDF companion in pdf/
tools/compare_editions.py      Proves a render matches what is already published
tools/build-edition-email.js   Page -> branded email for a Resend Broadcast
```

### The monthly cycle

On the first Thursday of each month, `.github/workflows/draft-edition.yml`
researches the *following* month, validates the result, renders it, and opens a
pull request on `edition/<slug>`. It never publishes and it never emails anyone —
a person reads the draft, corrects it, and merges. Two guards keep it honest:
cron cannot express "first Thursday", so it fires weekly and skips the other
three; and it skips any month that already exists in `content/editions/`.

Run it by hand from the Actions tab. `provider: stub` exercises the whole path
without a model, a key, or any cost — useful when changing the workflow itself.

### By hand

```bash
python3 tools/draft_edition.py --month 2026-11        # research and write the JSON
python3 tools/validate_edition.py content/editions/november-2026.json
python3 tools/render_html.py content/editions/november-2026.json
python3 tools/render_pdf.py content/editions/november-2026.json
```

The HTML render writes `editions/<slug>.html` and updates `index.html`,
`archive.html`, `sitemap.xml`, and the `/latest` redirect in `vercel.json` in the
same run. The PDF render writes `pdf/Helm_Horizon_<Month><Year>.pdf` — the
filename comes from the same function the page's download link uses, so the two
cannot drift apart.

The PDF needs `reportlab` (`pip install 'reportlab~=5.0'`); nothing else in the
pipeline has a dependency. Zodiak and Satoshi are served to browsers from
Fontshare and are not in this repository, so the PDF substitutes the best sans
installed on the machine — `python3 tools/render_pdf.py --fonts` says which. When
only ReportLab's built-in Helvetica is available it cannot draw a minus sign or an
arrow, so `−7%` and `118 → 83` are transliterated to `-7%` and `118 -> 83` rather
than printed as black boxes.

Then build the email edition and paste it into a Resend Broadcast:

```bash
node tools/build-edition-email.js editions/<slug>.html
```

It writes `emails/<slug>.html` and fails loudly if any heading, paragraph, list
item, or source link from the article did not survive the conversion. See
[`docs/email-setup.md`](docs/email-setup.md).

### The editorial standard, enforced

`validate_edition.py` runs in CI and exits non-zero on any of these:

* a figure with no source, or a source that is not `https://`
* a link that returns 404 or 410, or whose host does not resolve
* anything other than exactly three action steps
* an edition number out of sequence with the rest of the archive
* a `voices[]` entry whose `permission_to_quote` is not `true`

That last one is why quotes are never drafted. `draft_edition.py` always writes
`voices: []`; a reader's words go in by hand, after a person has confirmed they
may be published. Both renderers refuse an uncleared quote outright, so skipping
the validator does not get one printed.

`tools/test_validate_edition.py`, `tools/test_draft_edition.py`, and
`tools/test_render_pdf.py` prove those refusals still fire — a validator that
cannot fail would wave everything through. The PDF test also asserts that every
cited URL survives as a clickable link annotation, because a citation that
silently stopped being a link still looks correct on the page.

### Secrets

`ANTHROPIC_API_KEY` is a repository secret (Settings → Secrets and variables →
Actions). Nothing else in the pipeline needs credentials, and nothing in this
repository may contain them.

## Forms

`assets/site.js` reads `data-hh-form` and `data-endpoint` on each form and POSTs JSON to that
endpoint. Both forms now point at same-origin Vercel functions in `api/`:

| Form | Endpoint | What it does |
| --- | --- | --- |
| Subscribe (`index.html`, `subscribe.html`) | `/api/subscribe` | Creates a pending contact and emails a confirmation link |
| Contribute (`submit.html`) | `/api/submit` | Emails the outlook to the editor via Resend |

Both require environment variables to be set in Vercel — see
[`docs/email-setup.md`](docs/email-setup.md). Until they are, the endpoints return a 500 with a
readable message rather than failing silently.

### Abuse and privacy

Both routes send email on an unauthenticated request, so both are guarded:

* **Same-origin only, including scripts.** A request with no `Origin` and no `Referer` is
  refused. Browsers attach `Origin` to every POST, so anything arriving without one is a
  script — and previously those were the only callers the guard let through. `Referer` is
  accepted as a fallback for the proxies that strip `Origin`, and `Sec-Fetch-Site` is
  honoured where the browser sends it.
* **Rate limited.** Five signups and three submissions per caller per ten minutes, answered
  with a 429 and a `Retry-After`. The counters live in memory, so the ceiling is per warm
  instance rather than per deployment — a speed bump, not a wall. It is what is available
  without adding a datastore, and it turns a trivial flood into an expensive one. If abuse
  ever justifies the dependency, swap in Vercel KV behind `rateLimit()` in `api/_lib.js`.
* **No subscriber enumeration.** An address already on the list gets byte-for-byte the same
  reply, and the same confirmation email, as one that is not — so the endpoint cannot be
  used to ask whether a given person subscribes. An already-confirmed contact is never
  rewritten, so re-entering an address still cannot unsubscribe anyone.

`node tools/test-api.js` proves all of it without a network or a key, and runs in CI on
every change to `api/`.

Because the endpoints are same-origin, the `connect-src 'self'` CSP in `vercel.json` needs no
change. If you ever swap in a third-party endpoint (Mailchimp, ConvertKit, Formspree), it will
be **blocked by the browser** until you add that provider's origin to `connect-src`.

If `data-endpoint` is set back to a value beginning with `REPLACE`, the form falls back to a
`mailto:` handoff. That path is a last resort: it depends on the visitor having a working mail
client, and it refuses submissions over ~1,800 characters because mail clients truncate long
`mailto:` URLs.

The functions have no npm dependencies — they use the Node runtime's global `fetch`, so the
project still has no build step and no `package.json`.

## Local development

```bash
npx serve . -l 3000
```

`serve` resolves extensionless paths the same way Vercel's `cleanUrls` does, so local URLs
match production.
