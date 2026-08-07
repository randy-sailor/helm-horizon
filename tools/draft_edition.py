#!/usr/bin/env python3
"""Draft the next edition's JSON by researching the month.

    python3 tools/draft_edition.py                       # next month, live research
    python3 tools/draft_edition.py --month 2026-10       # a specific month
    python3 tools/draft_edition.py --provider stub       # no network, no key, no cost
    python3 tools/draft_edition.py --stdout              # print, write nothing

The model call sits behind `Provider.research()`. Everything downstream of that
method — the renderers, the validator, the workflow — talks to the edition JSON
and never to a vendor SDK, so swapping providers is a matter of adding a class
here and nothing else.

What the model is *not* allowed to decide:

  * the edition number, slug, and publication date  — arithmetic, done here
  * the previous-issue link                          — read off disk
  * image paths                                      — constrained to files that
                                                       actually exist in the repo
  * reader quotes                                    — `voices` is always empty in
                                                       a draft; quotes need a real
                                                       human's permission

A draft is a starting point for an editor, not a publication. It lands in a pull
request and a person reads it before it ships.
"""

import argparse
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDITIONS_DIR = os.path.join(ROOT, 'content', 'editions')
IMG_DIR = os.path.join(ROOT, 'assets', 'img')

MODEL = 'claude-opus-5'
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July',
          'August', 'September', 'October', 'November', 'December')


# ----------------------------------------------------------------- the calendar

def first_thursday(year, month):
    """Helm & Horizon publishes on the first Thursday of the month."""
    d = date(year, month, 1)
    return d.replace(day=1 + (3 - d.weekday()) % 7)


def next_month(today):
    return (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)


def parse_month(s):
    """Accept 2026-10, October 2026, or october-2026."""
    m = re.fullmatch(r'(\d{4})-(\d{1,2})', s.strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.fullmatch(r'([A-Za-z]+)[ -](\d{4})', s.strip())
    if m and m.group(1).capitalize() in MONTHS:
        return int(m.group(2)), MONTHS.index(m.group(1).capitalize()) + 1
    raise ValueError('could not read a month out of %r — try "2026-10"' % s)


# -------------------------------------------------------------- what's on disk

def load_editions():
    if not os.path.isdir(EDITIONS_DIR):
        return []
    out = []
    for name in sorted(os.listdir(EDITIONS_DIR)):
        if name.endswith('.json'):
            try:
                out.append(json.load(open(os.path.join(EDITIONS_DIR, name), encoding='utf-8')))
            except Exception:
                pass
    return out


def latest_edition(editions):
    numbered = [e for e in editions if isinstance(e.get('number'), int)]
    return max(numbered, key=lambda e: e['number']) if numbered else None


def available_images():
    """Only images that exist may be referenced; a 404 hero is worse than none."""
    if not os.path.isdir(IMG_DIR):
        return []
    return sorted('/assets/img/%s' % n for n in os.listdir(IMG_DIR)
                  if n.lower().endswith(('.webp', '.jpg', '.jpeg', '.png', '.avif')))


def build_brief(year, month, editions, images):
    """Everything the provider needs, and nothing it gets to invent."""
    slug = '%s-%d' % (MONTHS[month - 1].lower(), year)

    # Redrafting a month that already exists must not renumber it — the target
    # keeps its own place in the sequence and sequences against the others.
    existing = next((e for e in editions if e.get('slug') == slug), None)
    prev = latest_edition([e for e in editions if e.get('slug') != slug])

    if existing:
        volume, number = existing.get('volume', 1), existing['number']
        previous = existing.get('previous')
    else:
        volume, number = (prev or {}).get('volume', 1), (prev or {}).get('number', 0) + 1
        previous = None
    if previous is None and prev:
        previous = {'slug': prev['slug'], 'volume': prev['volume'],
                    'number': prev['number'], 'headline': prev['headline']}

    return {
        'month': '%s %d' % (MONTHS[month - 1], year),
        'slug': slug,
        'published': first_thursday(year, month).isoformat(),
        'volume': volume,
        'number': number,
        'images': images,
        'previous': previous,
        'previous_headline': (prev or previous or {}).get('headline'),
        'previous_takeaway': ((prev or {}).get('featured') or {}).get('takeaway', {}).get('body'),
    }


# ------------------------------------------------------------- the wire schema
#
# This is the shape the *model* returns, not the shape stored on disk. It is
# deliberately flat: every field is required, nothing is nullable, and the
# prose/figure distinction is carried by a `kind` discriminator rather than a
# union. Strict JSON-schema validation is reliable over that subset and gets
# fussy outside it, and `to_edition()` below costs ten lines.

def _src():
    return {
        'type': 'object',
        'additionalProperties': False,
        'required': ['title', 'url'],
        'properties': {
            'title': {'type': 'string',
                      'description': 'the publication, e.g. "Reuters" or "Brunswick investor relations"'},
            'url': {'type': 'string', 'description': 'https URL that resolves today'},
        },
    }


def wire_schema(images):
    img_enum = list(images) + ['']
    prose = {
        'type': 'array',
        'items': {'type': 'string'},
        'description': 'paragraphs; inline citations as [publication](https://...) markdown, '
                       'emphasis as **bold**',
    }
    return {
        'type': 'object',
        'additionalProperties': False,
        'required': ['headline', 'dek', 'description', 'hero_image', 'hero_alt',
                     'from_the_desk', 'featured', 'indicators', 'risks', 'actions',
                     'profile', 'voices_intro', 'data_as_of'],
        'properties': {
            'headline': {'type': 'string', 'description': 'under 70 characters, no colon-subtitle cliche'},
            'dek': {'type': 'string', 'description': 'one sentence under the headline'},
            'description': {'type': 'string', 'description': 'meta description, under 200 characters'},
            'hero_image': {'type': 'string', 'enum': images},
            'hero_alt': {'type': 'string'},
            'from_the_desk': prose,
            'featured': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['title', 'sections', 'takeaway_body'],
                'properties': {
                    'title': {'type': 'string'},
                    'sections': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'additionalProperties': False,
                            'required': ['kind', 'heading', 'body',
                                         'figure_image', 'figure_alt', 'figure_caption'],
                            'properties': {
                                'kind': {'type': 'string', 'enum': ['prose', 'figure']},
                                'heading': {'type': 'string',
                                            'description': 'empty string for a figure'},
                                'body': prose,
                                'figure_image': {'type': 'string', 'enum': img_enum},
                                'figure_alt': {'type': 'string'},
                                'figure_caption': {'type': 'string'},
                            },
                        },
                    },
                    'takeaway_body': {'type': 'string',
                                      'description': 'the one paragraph a reader keeps'},
                },
            },
            'indicators': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['region', 'label', 'value', 'source'],
                    'properties': {
                        'region': {'type': 'string', 'enum': ['us', 'global']},
                        'label': {'type': 'string'},
                        'value': {'type': 'string',
                                  'description': 'e.g. "$611.3M · −7%" — figure first, change second'},
                        'source': _src(),
                    },
                },
            },
            'risks': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['region', 'title', 'body', 'sources'],
                    'properties': {
                        'region': {'type': 'string', 'enum': ['us', 'global']},
                        'title': {'type': 'string', 'enum': ['United States', 'Global']},
                        'body': {'type': 'string',
                                 'description': 'one paragraph, inline [text](url) citations'},
                        'sources': {'type': 'array', 'items': _src()},
                    },
                },
            },
            'actions': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['title', 'body'],
                    'properties': {
                        'title': {'type': 'string', 'description': 'an imperative sentence'},
                        'body': {'type': 'string'},
                    },
                },
            },
            'profile': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['company', 'ticker', 'dek', 'sections'],
                'properties': {
                    'company': {'type': 'string'},
                    'ticker': {'type': 'string', 'description': 'e.g. "NYSE: BC", or "" if private'},
                    'dek': {'type': 'string'},
                    'sections': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'additionalProperties': False,
                            'required': ['heading', 'body'],
                            'properties': {
                                'heading': {'type': 'string',
                                            'description': 'empty string for the opening section'},
                                'body': prose,
                            },
                        },
                    },
                },
            },
            'voices_intro': prose,
            'data_as_of': {'type': 'string',
                           'description': 'e.g. "Data as of late August / early September 2026."'},
        },
    }


# -------------------------------------------------------------------- the brief

SYSTEM = """\
You are the research desk for Helm & Horizon, a monthly briefing read by yacht \
industry professionals — brokers, dealers, builders, captains, marina operators, \
and the banks and insurers behind them. They are practitioners. They know the \
vocabulary and they do not need it explained.

House standards, in order of importance:

1. EVERY FIGURE CARRIES A SOURCE. A number without a URL that resolves today does \
not go in. Prefer the primary document — a company's own results release or SEC \
filing, a central bank statement, a trade association's data release, a court \
filing — over anyone reporting on it. If you cannot source a figure, drop the \
figure; do not soften it into a vague claim.
2. No invented quotes, no invented people, no invented company statements.
3. Analytical and plain. No hype, no "game-changer", no exclamation marks. Write \
the way an analyst writes to a client who pays for candour.
4. Say what it means for the reader's own business, specifically. "Margins \
compressed" is a fact; "check your non-new-boat gross-profit share against 40%" \
is the reason they subscribe.
5. Use the em dash and the en dash as an editor would. Spell out jargon on first \
use: "finance and insurance", not "F&I"; "basis points", not "bps" alone.

Structure you are filling:

* from_the_desk — two paragraphs. The month in the industry, and what the rest of \
the issue argues.
* featured — the month's main story, 2 or 3 prose sections with headings, \
optionally one figure section between them, and a takeaway paragraph.
* indicators — 14 to 18 dashboard figures, split as evenly as you can between \
region "us" and region "global". Each is a label, a value, and a source.
* risks — exactly two entries: one with region "us" and title "United States", one \
with region "global" and title "Global".
* actions — exactly three. Each is an imperative title and a paragraph a reader \
could act on this week.
* profile — one company, with an opening section (empty heading), then \
"Why it matters now", then "Watch for".
* voices_intro — two paragraphs inviting reader submissions for the next issue.

Search the web before writing. Verify every figure against its source rather than \
against your memory of it, and cite what you actually opened."""


def user_prompt(brief):
    lines = [
        'Research and draft the %s edition of Helm & Horizon (Vol. %d No. %d), '
        'which publishes on %s.' % (brief['month'], brief['volume'], brief['number'],
                                    brief['published']),
        '',
        'Cover developments from roughly the last six weeks: public-company results '
        'across marine retail, propulsion and boatbuilding; mergers, acquisitions and '
        'distress at the dealer and builder tiers; charter market pricing and booking '
        'behaviour; brokerage inventory and days-on-market; fuel, insurance and '
        'shipping-route risk; rates and credit conditions as they reach marine '
        'lending; and the boat show calendar.',
    ]
    if brief.get('previous_headline'):
        lines += [
            '',
            'The previous issue led with "%s".' % brief['previous_headline'],
        ]
        if brief.get('previous_takeaway'):
            lines.append('Its takeaway was: %s' % brief['previous_takeaway'])
        lines.append('Advance that story where the evidence has moved. Do not restate it.')
    lines += [
        '',
        'Images: use only these paths, which exist in the repository. Pick the one '
        'that fits; do not invent a filename.',
    ]
    lines += ['  %s' % p for p in brief['images']]
    return '\n'.join(lines)


# ----------------------------------------------------------------- the providers

class Provider:
    """The whole vendor surface. Add a class, register it, change nothing else."""

    name = 'provider'

    def research(self, brief, schema):
        raise NotImplementedError


class AnthropicProvider(Provider):
    """Claude with server-side web search.

    Search-grounded is not optional here: the schema requires a citation for
    every figure, and a model working from memory produces plausible URLs that
    do not resolve. The validator catches those, but late and noisily.
    """

    name = 'anthropic'

    def __init__(self, model=MODEL, effort='high', max_tokens=32000):
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens

    def research(self, brief, schema):
        try:
            import anthropic
        except ImportError:
            raise SystemExit('the anthropic package is not installed: pip install anthropic')
        if not os.environ.get('ANTHROPIC_API_KEY'):
            raise SystemExit('ANTHROPIC_API_KEY is not set '
                             '(repository secret, exposed to the workflow as an env var)')

        client = anthropic.Anthropic()
        # Streaming, because a full edition runs well past the non-streaming
        # request timeout once web search rounds are included.
        with client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM,
            messages=[{'role': 'user', 'content': user_prompt(brief)}],
            thinking={'type': 'adaptive'},
            tools=[
                # Bounded because this runs unattended on a schedule; an
                # unbounded research loop is an unbounded bill.
                {'type': 'web_search_20260209', 'name': 'web_search', 'max_uses': 30},
                {'type': 'web_fetch_20260209', 'name': 'web_fetch', 'max_uses': 30},
            ],
            output_config={
                'effort': self.effort,
                'format': {'type': 'json_schema', 'schema': schema},
            },
        ) as stream:
            message = stream.get_final_message()

        if message.stop_reason == 'refusal':
            raise SystemExit('the model declined to draft this edition; '
                             'no output to read')
        if message.stop_reason == 'max_tokens':
            raise SystemExit('the draft hit max_tokens and is truncated; '
                             'raise --max-tokens and re-run')

        # Web search rounds can leave narration in earlier text blocks, so the
        # draft is the last block that parses rather than simply the first.
        blocks = [b.text for b in message.content if b.type == 'text']
        for text in reversed(blocks):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue
        raise SystemExit('no JSON in the response (%d text block(s))' % len(blocks))


class StubProvider(Provider):
    """A fixed, well-formed draft. No key, no network, no tokens.

    This exists so the rest of the pipeline — validate, render, branch, pull
    request — can be exercised end to end in CI on every change, including
    changes made by someone without an API key. It is the difference between
    "the workflow is written" and "the workflow is known to work".
    """

    name = 'stub'

    def research(self, brief, schema):
        img = brief['images'][0] if brief['images'] else ''
        src = {'title': 'Example primary source', 'url': 'https://example.com/'}
        month = brief['month']
        para = ('Placeholder prose for %s, generated without a model so the '
                'pipeline can be tested. See [the source](https://example.com/).' % month)
        return {
            'headline': 'Stub draft for %s' % month,
            'dek': 'A structurally valid placeholder produced without calling a model.',
            'description': 'Stub edition for %s, used to exercise the pipeline.' % month,
            'hero_image': img,
            'hero_alt': 'Placeholder hero image',
            'from_the_desk': [para, para],
            'featured': {
                'title': 'Stub feature',
                'sections': [
                    {'kind': 'prose', 'heading': 'First section', 'body': [para],
                     'figure_image': '', 'figure_alt': '', 'figure_caption': ''},
                    {'kind': 'figure', 'heading': '', 'body': [],
                     'figure_image': img, 'figure_alt': 'Placeholder figure',
                     'figure_caption': 'Placeholder caption.'},
                    {'kind': 'prose', 'heading': 'Second section', 'body': [para],
                     'figure_image': '', 'figure_alt': '', 'figure_caption': ''},
                ],
                'takeaway_body': para,
            },
            'indicators': [
                {'region': r, 'label': 'Stub indicator %d' % i, 'value': '0.0%',
                 'source': dict(src)}
                for i, r in enumerate(['us'] * 4 + ['global'] * 4, start=1)
            ],
            'risks': [
                {'region': 'us', 'title': 'United States', 'body': para, 'sources': [dict(src)]},
                {'region': 'global', 'title': 'Global', 'body': para, 'sources': [dict(src)]},
            ],
            'actions': [{'title': 'Stub action %d.' % i, 'body': para} for i in (1, 2, 3)],
            'profile': {
                'company': 'Stub Company', 'ticker': 'NYSE: STUB',
                'dek': 'A placeholder profile.',
                'sections': [
                    {'heading': '', 'body': [para]},
                    {'heading': 'Why it matters now', 'body': [para]},
                    {'heading': 'Watch for', 'body': [para]},
                ],
            },
            'voices_intro': [para, para],
            'data_as_of': 'Data as of the stub run.',
        }


PROVIDERS = {p.name: p for p in (AnthropicProvider, StubProvider)}


# ------------------------------------------------------ wire shape -> disk shape

def to_edition(draft, brief):
    """Merge the model's draft with the facts it was not allowed to decide."""
    allowed = set(brief['images'])

    def image(path, where):
        # The schema constrains this to an enum, but a provider that ignored the
        # enum would ship a page with a broken image and nothing would object.
        if path not in allowed:
            raise SystemExit('%s references an image that does not exist: %r' % (where, path))
        return path

    featured_sections = []
    for s in draft.get('featured', {}).get('sections', []):
        if s.get('kind') == 'figure' and s.get('figure_image'):
            featured_sections.append({'figure': {
                'image': image(s['figure_image'], 'featured figure'),
                'alt': s.get('figure_alt', ''),
                'caption': s.get('figure_caption', ''),
            }})
        elif s.get('body'):
            featured_sections.append({'heading': s.get('heading') or None,
                                      'body': list(s['body'])})

    ed = {
        'volume': brief['volume'],
        'number': brief['number'],
        'month': brief['month'],
        'slug': brief['slug'],
        'published': brief['published'],
        'headline': draft.get('headline'),
        'dek': draft.get('dek'),
        'description': draft.get('description'),
        'hero': {'image': image(draft.get('hero_image'), 'hero'), 'alt': draft.get('hero_alt')},
        'from_the_desk': draft.get('from_the_desk', []),
        'featured': {
            'title': draft.get('featured', {}).get('title'),
            'sections': featured_sections,
            'takeaway': {'eyebrow': 'Key takeaway',
                         'body': draft.get('featured', {}).get('takeaway_body')},
        },
        'indicators': draft.get('indicators', []),
        'risks': draft.get('risks', []),
        'actions': draft.get('actions', []),
        'profile': {
            'company': draft.get('profile', {}).get('company'),
            'ticker': draft.get('profile', {}).get('ticker'),
            'dek': draft.get('profile', {}).get('dek'),
            'sections': [{'heading': s.get('heading') or None, 'body': list(s.get('body', []))}
                         for s in draft.get('profile', {}).get('sections', [])],
        },
        # Never drafted. Reader submissions arrive through /api/submit and a
        # person confirms permission before a quote is added by hand.
        'voices': [],
        'voices_intro': draft.get('voices_intro', []),
        'colophon': 'Sources cited inline with links. %s Helm & Horizon is published by '
                    'The Walton Group, Inc. and is not investment advice.'
                    % draft.get('data_as_of', ''),
        'data_as_of': draft.get('data_as_of'),
    }
    if brief.get('previous'):
        ed['previous'] = brief['previous']
    return ed


# ------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--month', help='target month: 2026-10, "October 2026" (default: next month)')
    ap.add_argument('--today', help='override today\'s date (YYYY-MM-DD), for testing')
    ap.add_argument('--provider', default='anthropic', choices=sorted(PROVIDERS),
                    help='stub drafts without a model, key, or network')
    ap.add_argument('--model', default=MODEL)
    ap.add_argument('--effort', default='high', choices=['low', 'medium', 'high', 'xhigh', 'max'])
    ap.add_argument('--max-tokens', type=int, default=32000)
    ap.add_argument('--out', help='where to write (default: content/editions/<slug>.json)')
    ap.add_argument('--stdout', action='store_true', help='print the draft, write nothing')
    ap.add_argument('--plan', action='store_true',
                    help='print what would be drafted as JSON and stop — no model call')
    ap.add_argument('--force', action='store_true', help='overwrite an existing edition file')
    args = ap.parse_args()

    today = date.fromisoformat(args.today) if args.today else date.today()
    year, month = parse_month(args.month) if args.month else next_month(today)

    images = available_images()
    if not images:
        raise SystemExit('no images found in assets/img — nothing to reference')

    editions = load_editions()
    brief = build_brief(year, month, editions, images)

    out = args.out or os.path.join(EDITIONS_DIR, '%s.json' % brief['slug'])

    if args.plan:
        # The workflow asks the tool what it would do rather than reimplementing
        # the calendar in shell, where it would drift.
        json.dump({'month': brief['month'], 'slug': brief['slug'],
                   'published': brief['published'], 'volume': brief['volume'],
                   'number': brief['number'],
                   'path': os.path.relpath(out, ROOT),
                   'exists': os.path.exists(out)}, sys.stdout)
        sys.stdout.write('\n')
        return 0

    if not args.stdout and os.path.exists(out) and not args.force:
        raise SystemExit('%s already exists — pass --force to overwrite' % out)

    kwargs = {}
    if args.provider == 'anthropic':
        kwargs = {'model': args.model, 'effort': args.effort, 'max_tokens': args.max_tokens}
    provider = PROVIDERS[args.provider](**kwargs)

    print('drafting %s (Vol. %d No. %d, publishing %s) via %s'
          % (brief['month'], brief['volume'], brief['number'], brief['published'],
             provider.name), file=sys.stderr)

    draft = provider.research(brief, wire_schema(images))
    ed = to_edition(draft, brief)
    text = json.dumps(ed, indent=2, ensure_ascii=False) + '\n'

    if args.stdout:
        sys.stdout.write(text)
        return 0

    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8').write(text)
    print('wrote %s' % out, file=sys.stderr)
    print(out)  # stdout is the path, so the workflow can consume it
    return 0


if __name__ == '__main__':
    sys.exit(main())
