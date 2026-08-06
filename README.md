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

1. Copy the most recent file in `editions/` to `editions/<month>-<year>.html`.
2. Update the content, the canonical URL, and the Open Graph tags.
3. Add the PDF to `pdf/`.
4. Add a card to `archive.html` and update the lede on `index.html`.
5. Point the `/latest` redirect in `vercel.json` at the new edition.
6. Add the new URL to `sitemap.xml`.

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
