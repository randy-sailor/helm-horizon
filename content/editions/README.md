# Edition schema

One JSON file per edition, `content/editions/<slug>.json`. This is the source of
truth: the page, the PDF, and the email edition are all rendered from it. Nothing
downstream should be edited by hand.

## Why the shape differs from prose

Body text is stored as **minimal markdown**, not HTML:

```
"On 24 July, [Reuters reported](https://www.reuters.com/…) that **Blackstone,
Donerail, and Centerbridge Partners** have advanced to the third round…"
```

Only three constructs are supported — `[text](url)`, `**bold**`, `*italic*`.
Storing raw HTML here would defeat the point of having a data representation, and
it would mean the PDF renderer had to parse markup it does not otherwise care
about. Keeping citations inline in the prose also means the validator can extract
every URL in the edition, not only the ones in structured fields.

## Fields

| Field | Type | Notes |
| --- | --- | --- |
| `volume`, `number` | int | `number` must be exactly one greater than the previous edition |
| `month` | string | Display form, e.g. `"September 2026"` |
| `slug` | string | `<month>-<year>`; drives filenames and the URL |
| `published` | string | ISO date |
| `headline` | string | |
| `dek` | string | One sentence. Used for `og:description` and the archive card |
| `description` | string | Longer meta description |
| `hero` | `{image, alt}` | Path is site-relative |
| `from_the_desk` | string[] | Editor's note, 2–3 paragraphs |
| `featured` | object | See below |
| `indicators` | object[] | See below |
| `risks` | object[] | See below |
| `actions` | object[] | **Exactly three** |
| `profile` | object | One company, usually with a ticker |
| `voices` | object[] | Reader submissions; may be empty |
| `voices_intro` | string[] | Shown when `voices` is empty — the call for submissions |
| `colophon` | string | Trailing "Sources cited inline…" line |

### `featured`

```jsonc
{
  "title": "Three bidders, one endgame",
  "sections": [
    { "heading": "The MarineMax auction enters its final round", "body": ["…", "…"] },
    { "figure": { "image": "/assets/img/…", "alt": "…", "caption": "…" } },
    { "heading": "The read for dealers and brokers", "body": ["…"] }
  ],
  "takeaway": { "eyebrow": "Key takeaway", "body": "…" }
}
```

A `sections[]` entry is either a `{heading, body}` pair or a `{figure}`. Order is
preserved as written.

### `indicators` and `risks`

```jsonc
{ "region": "us",                      // "us" | "global"
  "label": "MarineMax Q3 revenue",
  "value": "$611.3M · −7%",
  "source": { "title": "Yahoo Finance on MarineMax", "url": "https://…" } }
```

**Every indicator and every risk must carry a `source.url`.** This is the
publication's core editorial standard, and the validator enforces it rather than
leaving it to discipline. The rendered "Sources:" line under each panel is
rebuilt from these, deduplicated in order of first use — it is not stored
separately, so a source cannot appear in the footnote without being attached to a
figure.

`risks[]` additionally carries `title` and `body`, and its `sources` is a list,
since a risk paragraph usually cites several.

### `voices`

```jsonc
{ "quote": "…", "attribution": "…", "role": "…", "permission_to_quote": true }
```

An entry with `permission_to_quote` false or absent **must never render**. The
validator rejects the edition rather than silently dropping the entry, so a
contributor's off-record remark cannot reach publication through an omission.

## Known exception

`september-2026.json` has one indicator with `"source": null` — *US federal funds
target, end July*. The published page cites no source for it. It is recorded
honestly rather than given an invented citation; resolve it by supplying the real
source or removing the figure.
