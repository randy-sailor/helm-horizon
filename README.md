# Helm & Horizon

A monthly market briefing for yacht industry leaders — brokers, dealers, and builders.
Published at [thehelmandhorizon.com](https://thehelmandhorizon.com).

Every figure in every edition is cited to a primary source: NMMA retail data, SEC filings and
earnings calls from MarineMax (NYSE: HZO), Brunswick (NYSE: BC), and OneWater Marine (NASDAQ: ONEW),
Boat International's order book, and charter and insurance market reporting.

## Stack

Static HTML, CSS, and vanilla JavaScript. No build step, no framework, no dependencies.
Hosted on Vercel; `vercel.json` handles clean URLs, cache headers, and CSP.

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

`assets/site.js` reads `data-hh-form` and `data-endpoint` on each form. While `data-endpoint`
still begins with `REPLACE`, submissions fall back to a `mailto:` link. Replace the placeholder
values with live API routes to capture submissions server-side.

## Local development

```bash
npx serve . -l 3000
```

`serve` resolves extensionless paths the same way Vercel's `cleanUrls` does, so local URLs
match production.
