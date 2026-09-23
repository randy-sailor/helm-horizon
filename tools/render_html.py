#!/usr/bin/env python3
"""Render an edition JSON into the site's edition page, and update the pages
that reference it.

    python3 tools/render_html.py content/editions/october-2026.json
    python3 tools/render_html.py content/editions/october-2026.json --dry-run

Writes editions/<slug>.html and, unless --page-only, updates index.html,
archive.html, sitemap.xml, and the /latest redirect in vercel.json.

Markup is reproduced from the existing edition page: same masthead and nav,
same sticky sidebar and anchors, same class names from assets/base.css. The
renderer owns structure; base.css owns appearance.
"""

import argparse
import json
import os
import re
import sys

SITE = 'https://thehelmandhorizon.com'
PUBLISHER = 'The Walton Group, Inc.'

MD_LINK = re.compile(r'\[([^\]]*)\]\((https?://[^)\s]+)\)')
MD_BOLD = re.compile(r'\*\*([^*]+)\*\*')
MD_ITAL = re.compile(r'(?<!\*)\*([^*]+)\*(?!\*)')

FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' fill='%2306192e'/%3E%3Cpath d='M16 5l4.5 11L16 27l-4.5-11z' "
    "fill='%23c9a55a'/%3E%3Cpath d='M4 16h24' stroke='%23c9a55a' stroke-width='1.6'/%3E%3C/svg%3E"
)

FONTSHARE = ('https://api.fontshare.com/v2/css?f[]=zodiak@400,500,700'
             '&f[]=satoshi@400,500,700&display=swap')

BRAND_SVG = '''<svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
            <circle cx="16" cy="16" r="14" stroke="currentColor" stroke-width="1.5" />
            <path d="M2 16h28" stroke="currentColor" stroke-width="1.5" />
            <path d="M16 3.5 21 16l-5 12.5L11 16z" fill="currentColor" />
          </svg>'''


# --------------------------------------------------------------------- inline

def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def inline(s):
    """[text](url) -> anchor, **bold** -> strong. Everything else is escaped.

    External links match the site convention: new tab, noopener noreferrer.
    """
    parts = []
    pos = 0
    for m in MD_LINK.finditer(s):
        parts.append(('text', s[pos:m.start()]))
        parts.append(('link', m.group(1), m.group(2)))
        pos = m.end()
    parts.append(('text', s[pos:]))

    out = []
    for part in parts:
        if part[0] == 'link':
            label = _emphasis(esc(part[1]))
            out.append('<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>'
                       % (esc(part[2]), label))
        else:
            out.append(_emphasis(esc(part[1])))
    return ''.join(out)


def _emphasis(escaped):
    escaped = MD_BOLD.sub(r'<strong>\1</strong>', escaped)
    escaped = MD_ITAL.sub(r'<em>\1</em>', escaped)
    return escaped


def plain(s):
    """Strip markdown for use in attributes and meta tags."""
    s = MD_LINK.sub(r'\1', s)
    s = MD_BOLD.sub(r'\1', s)
    s = MD_ITAL.sub(r'\1', s)
    return re.sub(r'\s+', ' ', s).strip()


# ------------------------------------------------------------------- fragments

def pdf_name(slug):
    month, year = slug.split('-')
    return 'Helm_Horizon_%s%s.pdf' % (month.capitalize(), year)


def masthead(active=None):
    def a(href, label, cta=False):
        cur = ' aria-current="page"' if active == href else ''
        cls = ' class="nav__cta"' if cta else ''
        return '<a%s href="%s"%s>%s</a>' % (cls, href, cur, label)
    return '''    <a class="skip" href="#main">Skip to content</a>

    <header class="masthead">
      <div class="shell masthead__inner">
        <a class="brand" href="/" aria-label="Helm and Horizon home">
          %s
          <span class="brand__name">Helm &amp; Horizon</span>
        </a>
        <button
          class="nav__toggle"
          type="button"
          aria-expanded="false"
          aria-controls="site-nav"
          aria-label="Toggle navigation"
        >
          <svg width="18" height="14" viewBox="0 0 18 14" fill="none" aria-hidden="true">
            <path d="M0 1h18M0 7h18M0 13h18" stroke="currentColor" stroke-width="1.6" />
          </svg>
        </button>
        <nav class="nav" id="site-nav" aria-label="Primary">
          %s
          %s
          %s
          %s
          %s
        </nav>
      </div>
    </header>
''' % (BRAND_SVG, a('/', 'Latest'), a('/archive', 'Archive'), a('/about', 'About'),
       a('/submit', 'Contribute'), a('/subscribe', 'Subscribe', cta=True))


def footer(slug, pdf, legal):
    return '''    <footer class="footer">
      <div class="shell">
        <div class="footer__grid">
          <div class="footer__brand">
            <a class="brand" href="/" style="margin-bottom: var(--space-4)">
              %s
              <span class="brand__name">Helm &amp; Horizon</span>
            </a>
            <p>
              A monthly market briefing for yacht industry leaders. Published by The Walton Group,
              Inc. Sources cited inline. Not investment advice.
            </p>
          </div>
          <div>
            <h4>Read</h4>
            <ul>
              <li><a href="/editions/%s">Current issue</a></li>
              <li><a href="/archive">Archive</a></li>
              <li><a href="/pdf/%s">Download PDF</a></li>
            </ul>
          </div>
          <div>
            <h4>Participate</h4>
            <ul>
              <li><a href="/subscribe">Subscribe</a></li>
              <li><a href="/submit">Submit an outlook</a></li>
              <li><a href="/about">About &amp; masthead</a></li>
              <li><a href="mailto:editor@thehelmandhorizon.com">Contact the editor</a></li>
            </ul>
          </div>
        </div>
        <div class="footer__legal">
          <span>&copy; <span data-year>2026</span> The Walton Group, Inc. All rights reserved.</span>
          <span>%s</span>
        </div>
      </div>
    </footer>
''' % (BRAND_SVG, slug, pdf, legal)


# -------------------------------------------------------------------- sections

def render_article(ed):
    out = []

    out.append('            <h2 id="desk">From the desk</h2>')
    for p in ed['from_the_desk']:
        out.append('            <p>%s</p>' % inline(p))

    out.append('')
    out.append('            <h2 id="featured">Featured story: %s</h2>' % esc(ed['featured']['title']))
    for sec in ed['featured']['sections']:
        if 'figure' in sec:
            f = sec['figure']
            out.append('            <figure>')
            out.append('              <img')
            out.append('                src="%s"' % esc(f['image']))
            out.append('                alt="%s"' % esc(f['alt']))
            out.append('                width="1536"')
            out.append('                height="1024"')
            out.append('                loading="lazy"')
            out.append('              />')
            if f.get('caption'):
                out.append('              <figcaption>%s</figcaption>' % inline(f['caption']))
            out.append('            </figure>')
        else:
            out.append('            <h3>%s</h3>' % esc(sec['heading']))
            for p in sec['body']:
                out.append('            <p>%s</p>' % inline(p))
    tk = ed['featured'].get('takeaway')
    if tk:
        out.append('            <div class="callout">')
        out.append('              <p class="eyebrow">%s</p>' % esc(tk.get('eyebrow', 'Key takeaway')))
        out.append('              <p>%s</p>' % inline(tk['body']))
        out.append('            </div>')

    out.append('')
    out.append('            <h2 id="numbers">Economic indicators and risk</h2>')
    for region, heading in (('us', 'United States'), ('global', 'Global')):
        items = [i for i in ed['indicators'] if i['region'] == region]
        if not items:
            continue
        out.append('            <h3>%s</h3>' % heading)
        out.append('            <ul class="datalist">')
        for i in items:
            out.append('              <li><span>%s</span><b>%s</b></li>'
                       % (esc(i['label']), esc(i['value'])))
        out.append('            </ul>')
        # One "Sources:" line per panel, deduplicated in first-use order, so
        # the rendered page keeps the published convention while the data
        # underneath ties each source to the figure it supports.
        seen, srcs = set(), []
        for i in items:
            s = i.get('source') or {}
            if s.get('url') and s['url'] not in seen:
                seen.add(s['url'])
                srcs.append(s)
        if srcs:
            links = ['<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>'
                     % (esc(s['url']), esc(s['title'])) for s in srcs]
            if len(links) > 1:
                joined = ', '.join(links[:-1]) + ', and ' + links[-1]
            else:
                joined = links[0]
            out.append('            <p>Sources: %s.</p>' % joined)

    risks = ed.get('risks') or []
    if risks:
        out.append('            <h3>Risk watch</h3>')
        for n, r in enumerate(risks):
            style = ' style="margin-bottom: var(--space-4)"' if n < len(risks) - 1 else ''
            out.append('            <div class="warn"%s>' % style)
            out.append('              <h4>%s</h4>' % esc(r['title']))
            out.append('              <p>%s</p>' % inline(r['body']))
            out.append('            </div>')

    out.append('')
    out.append('            <h2 id="actions">Three action steps</h2>')
    out.append('            <div class="steps" style="margin-top: var(--space-6)">')
    for n, a in enumerate(ed['actions'], 1):
        out.append('              <article class="step">')
        out.append('                <div class="step__n">%d</div>' % n)
        out.append('                <div>')
        out.append('                  <h3 style="margin-top: 0">%s</h3>' % inline(a['title']))
        out.append('                  <p>%s</p>' % inline(a['body']))
        out.append('                </div>')
        out.append('              </article>')
    out.append('            </div>')

    prof = ed['profile']
    out.append('')
    out.append('            <h2 id="profile">Industry player profile: %s</h2>' % esc(prof['company']))
    if prof.get('dek'):
        out.append('            <p style="color: var(--ink-faint); font-style: italic">%s</p>'
                   % inline(prof['dek']))
    for sec in prof['sections']:
        if sec.get('heading'):
            out.append('            <h3>%s</h3>' % esc(sec['heading']))
        for p in sec['body']:
            out.append('            <p>%s</p>' % inline(p))

    out.append('')
    out.append('            <h2 id="voices">Voices from the field</h2>')
    for v in ed.get('voices') or []:
        # The validator guarantees permission, but a renderer that would emit
        # an uncleared quote if the validator were skipped is a liability.
        if v.get('permission_to_quote') is not True:
            raise SystemExit('refusing to render a quote without permission: %r'
                             % v.get('attribution'))
        out.append('            <blockquote class="callout">')
        out.append('              <p>%s</p>' % inline(v['quote']))
        out.append('              <p class="eyebrow">%s%s</p>'
                   % (esc(v['attribution']),
                      ' &middot; ' + esc(v['role']) if v.get('role') else ''))
        out.append('            </blockquote>')
    for p in ed.get('voices_intro') or []:
        out.append('            <p>%s</p>' % inline(p))
    out.append('            <div class="btn-row" style="margin-bottom: var(--space-8)">')
    out.append('              <a class="btn btn--navy" href="/submit">Submit your outlook</a>')
    out.append('              <a class="btn btn--outline" href="/subscribe">Subscribe free</a>')
    out.append('            </div>')

    if ed.get('colophon'):
        out.append('')
        out.append('            <p style="font-size: var(--text-xs); color: var(--ink-faint)">%s</p>'
                   % inline(ed['colophon']))

    return '\n'.join(out)


def count_sources(ed):
    urls = set()

    def walk(n):
        if isinstance(n, str):
            for _, u in MD_LINK.findall(n):
                urls.add(u)
        elif isinstance(n, dict):
            if isinstance(n.get('url'), str):
                urls.add(n['url'])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(ed)
    return len(urls)


def reading_time(ed):
    words = 0

    def walk(n):
        nonlocal words
        if isinstance(n, str):
            words += len(plain(n).split())
        elif isinstance(n, dict):
            for k, v in n.items():
                if k != 'url':
                    walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk({k: v for k, v in ed.items() if k not in ('hero',)})
    return max(1, round(words / 200))


def render_sidebar(ed, prev):
    slug = ed['slug']
    items = [
        ('#desk', 'From the desk'),
        ('#featured', 'Featured: %s' % ed['featured']['title'][0].lower() + ed['featured']['title'][1:]),
        ('#numbers', 'Economic indicators and risk'),
        ('#actions', 'Three action steps'),
        ('#profile', 'Profile: %s' % ed['profile']['company']),
        ('#voices', 'Voices from the field'),
    ]
    nav = '\n'.join('              <li><a href="%s">%s</a></li>' % (h, esc(t)) for h, t in items)

    prev_block = ''
    if prev:
        prev_block = '''
            <h4>Previous issue</h4>
            <ul>
              <li>
                <a href="/pdf/%s"
                  >Vol. %d, No. %d &mdash; %s</a
                >
              </li>
            </ul>''' % (pdf_name(prev['slug']), prev['volume'], prev['number'], esc(prev['headline']))

    return '''          <aside class="sidebar">
            <h4>In this issue</h4>
            <ul>
%s
            </ul>

            <h4>Issue at a glance</h4>
            <ul class="datalist" style="margin-bottom: var(--space-8)">
              <li><span>Edition</span><b>Vol. %d, No. %d</b></li>
              <li><span>Published</span><b>%s</b></li>
              <li><span>Reading time</span><b>%d min</b></li>
              <li><span>Sources cited</span><b>%d</b></li>
            </ul>

            <h4>Download</h4>
            <ul style="margin-bottom: var(--space-8)">
              <li>
                <a href="/pdf/%s">%s PDF edition</a>
              </li>
              <li><a href="/archive">Browse all back issues</a></li>
            </ul>%s
          </aside>''' % (nav, ed['volume'], ed['number'],
                         esc(ed['month'].split()[0][:4] + ' ' + ed['month'].split()[1]),
                         reading_time(ed), count_sources(ed),
                         pdf_name(slug), esc(ed['month']), prev_block)


def render_page(ed, prev=None):
    slug = ed['slug']
    url = '%s/editions/%s' % (SITE, slug)
    hero = ed.get('hero') or {}
    desc = ed.get('description') or ed['dek']

    return '''<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>
      %s — Helm &amp; Horizon, %s
    </title>
    <meta
      name="description"
      content="%s"
    />
    <link rel="canonical" href="%s" />
    <meta property="og:type" content="article" />
    <meta property="og:site_name" content="Helm &amp; Horizon" />
    <meta property="og:url" content="%s" />
    <meta property="og:title" content="%s" />
    <meta
      property="og:description"
      content="%s"
    />
    <meta property="og:image" content="%s%s" />
    <meta name="twitter:card" content="summary_large_image" />
    <link
      rel="icon"
      href="%s"
    />
    <link
      href="%s"
      rel="stylesheet"
    />
    <link rel="stylesheet" href="/assets/base.css?v=2" />
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": "%s",
        "datePublished": "%s",
        "publisher": { "@type": "Organization", "name": "%s" },
        "isPartOf": { "@type": "Periodical", "name": "Helm & Horizon" }
      }
    </script>
  </head>
  <body>
%s
    <main id="main">
      <!-- ===== Issue header ===== -->
      <section class="hero">
        <div class="hero__media">
          <img
            src="%s"
            alt="%s"
            width="1536"
            height="1024"
            fetchpriority="high"
          />
        </div>
        <div class="shell hero__inner" style="padding-block: clamp(3rem, 8vw, 6rem)">
          <div class="hero__meta">
            <span>%s</span><span>Vol. %d, No. %d</span>
          </div>
          <div class="hero__rule"></div>
          <h1 style="font-size: var(--text-2xl)">
            %s
          </h1>
          <p class="hero__lede" style="margin-bottom: var(--space-6)">
            A monthly market briefing for yacht industry leaders.
          </p>
          <div class="btn-row">
            <a class="btn btn--gold" href="/pdf/%s"
              >Download the PDF edition</a
            >
          </div>
        </div>
      </section>

      <div class="article">
        <div class="shell article__shell">
          <!-- ================= BODY ================= -->
          <article class="prose">
%s
          </article>

          <!-- ================= SIDEBAR ================= -->
%s
        </div>
      </div>
    </main>

%s
    <script src="/assets/site.js?v=2" defer></script>
  </body>
</html>
''' % (esc(ed['headline']), esc(ed['month']), esc(plain(desc)), url, url,
       esc(ed['headline']), esc(plain(ed['dek'])), SITE, hero.get('image', ''),
       FAVICON, FONTSHARE, ed['headline'].replace('"', '\\"'), ed['published'], PUBLISHER,
       masthead(), esc(hero.get('image', '')), esc(hero.get('alt', '')),
       esc(ed['month']), ed['volume'], ed['number'], esc(ed['headline']),
       pdf_name(slug), render_article(ed), render_sidebar(ed, prev),
       footer(slug, pdf_name(slug),
              esc(ed.get('data_as_of', 'Data as of %s.' % ed['month']))))


# ------------------------------------------------------- site-wide references

def update_sitemap(ed, path='sitemap.xml'):
    s = open(path, encoding='utf-8').read()
    loc = '%s/editions/%s' % (SITE, ed['slug'])
    if loc in s:
        return False
    entry = ('  <url><loc>%s</loc><changefreq>yearly</changefreq>'
             '<priority>0.9</priority></url>\n' % loc)
    s = s.replace('</urlset>', entry + '</urlset>')
    open(path, 'w', encoding='utf-8').write(s)
    return True


def update_vercel(ed, path='vercel.json'):
    cfg = json.load(open(path, encoding='utf-8'))
    dest = '/editions/%s' % ed['slug']
    changed = False
    for r in cfg.get('redirects', []):
        if r.get('source') == '/latest' and r.get('destination') != dest:
            r['destination'] = dest
            changed = True
    if changed:
        open(path, 'w', encoding='utf-8').write(json.dumps(cfg, indent=2) + '\n')
    return changed


def archive_card(ed, reveal=True, pdf_label='PDF edition'):
    """One issue's card. subscribe.html's sampler omits the scroll-reveal class
    and shortens the PDF label, so both are parameters rather than a second
    near-identical template."""
    return '''            <article class="card%s">
              <p class="card__vol">Vol. %d, No. %d &middot; %s</p>
              <div class="card__body">
                <h3>%s</h3>
                <p>%s</p>
                <div class="card__links">
                  <a href="/editions/%s">Read online</a>
                  <a href="/pdf/%s">%s</a>
                </div>
              </div>
            </article>
''' % (' reveal' if reveal else '', ed['volume'], ed['number'], esc(ed['month']),
       esc(ed['headline']), esc(plain(ed['dek'])), ed['slug'], pdf_name(ed['slug']),
       esc(pdf_label))


CARD_RE = re.compile(r'<article class="card[^"]*">.*?</article>\n?', re.S)
CARD_VOL_RE = re.compile(
    r'<p class="card__vol">Vol\. \d+, No\. \d+ &middot; ([A-Za-z]+) (\d{4})</p>')


def refresh_cards(block, ed, limit=3, reveal=True, pdf_label='PDF edition'):
    """Point every card at its own issue, and put this one at the front.

    The cards are not regenerated from the JSON, because the earliest issues
    predate content/editions/ and exist only as a card and a PDF — rebuilding
    the strip from disk would silently drop them off the site.

    What went wrong before was subtler: update_index replaced the outgoing slug
    everywhere in the file, so September's card kept its September heading and
    dek while its "Read online" link was rewritten to October. Each card's links
    are now derived from the card's own volume line.
    """
    def retarget(m):
        card = m.group(0)
        v = CARD_VOL_RE.search(card)
        if not v:
            return card
        slug = '%s-%s' % (v.group(1).lower(), v.group(2))
        card = re.sub(r'href="/editions/[a-z]+-\d{4}"',
                      'href="/editions/%s"' % slug, card)
        return re.sub(r'href="/pdf/Helm_Horizon_[A-Za-z]+\d{4}\.pdf"',
                      'href="/pdf/%s"' % pdf_name(slug), card)

    block = CARD_RE.sub(retarget, block)
    if 'Vol. %d, No. %d' % (ed['volume'], ed['number']) not in block:
        block = archive_card(ed, reveal=reveal, pdf_label=pdf_label) + block
    return ''.join(CARD_RE.findall(block)[:limit]).rstrip('\n')


def update_sampler(ed, path='subscribe.html'):
    """Keep subscribe.html's "Read an issue first" strip on the newest issues.

    It is the panel a prospective subscriber reads before deciding, and it was
    still offering September as the most recent issue after October published.
    """
    s = open(path, encoding='utf-8').read()
    out = re.sub(r'(<div class="grid-cards">\n)(.*?)(\n          </div>)',
                 lambda m: m.group(1) + refresh_cards(m.group(2), ed, reveal=False,
                                                      pdf_label='PDF') + m.group(3),
                 s, count=1, flags=re.S)
    if out == s:
        return False
    open(path, 'w', encoding='utf-8').write(out)
    return True


def _sentence(text):
    """Sentence-case a fragment without flattening the words after it.

    str.capitalize() lowercases the remainder, which turns "rolling twelve
    months to April" into "...to april".
    """
    text = text.strip()
    if not text:
        return ''
    text = text[0].upper() + text[1:]
    return text if text.endswith('.') else text + '.'


def _split_value(value):
    """"214,292 units · -7.1%" -> the figure, and the rest of the line."""
    parts = [p.strip() for p in str(value).split('·')]
    return parts[0], ' · '.join(parts[1:])


def number_cells(ed, count=4):
    """The four figures under "By the numbers", from the edition's indicators.

    The cell is a big figure, the subject in bold, then the qualifier — so the
    label is split at its first comma rather than set whole, which would put a
    line of small print where the design wants a few words.
    """
    cells = []
    for ind in (ed.get('indicators') or [])[:count]:
        figure, rest = _split_value(ind.get('value', ''))
        subject, _, qualifier = plain(ind.get('label', '')).partition(',')
        tail = ' '.join(t for t in (_sentence(qualifier), _sentence(rest)) if t)
        cells.append('''            <div class="numbers__cell">
              <div class="numbers__val">%s</div>
              <p class="numbers__label">
                <strong>%s</strong>%s
              </p>
            </div>''' % (esc(figure), esc(subject.strip()), esc(tail)))
    return '\n'.join(cells)


def feature_body(ed):
    """The home page's trailer for the featured story: its first prose section."""
    sections = [s for s in ed['featured'].get('sections', []) if s.get('body')]
    first = sections[0] if sections else {}
    out = []
    if first.get('heading'):
        out.append('              <h3>%s</h3>' % esc(first['heading']))
    # A trailer, not the article: two paragraphs and the button under them.
    for para in first.get('body', [])[:2]:
        out.append('              <p>%s</p>' % inline(para))
    out.append('''              <div class="btn-row">
                <a class="btn btn--outline" href="/editions/%s"
                  >Continue reading</a
                >
              </div>''' % ed['slug'])
    return '\n'.join(out)


def keylist(ed, count=6):
    """The "What moved this month" rail, from the same indicators as the page."""
    items = []
    for ind in (ed.get('indicators') or [])[:count]:
        label = plain(ind.get('label', ''))
        # The rail is narrow: lead with the subject, leave the qualifier off.
        items.append('                <li><strong>%s</strong><span>%s</span></li>'
                     % (esc(label.split(',')[0]), esc(plain(ind.get('value', '')))))
    return '\n'.join(items)


def current_issue_links(s, ed):
    """Point a page's "current issue" footer links at this edition.

    Every page carries them, and they are the one part of the furniture that is
    not the same on every issue. Five pages spent a month pointing at September
    because nothing outside index.html ever rewrote them.
    """
    s = re.sub(r'(<li><a href=")/editions/[a-z]+-\d{4}(">Current issue</a></li>)',
               r'\g<1>/editions/%s\g<2>' % ed['slug'], s)
    s = re.sub(r'(<li><a href=")/pdf/Helm_Horizon_[A-Za-z]+\d{4}\.pdf(">Download PDF</a></li>)',
               r'\g<1>/pdf/%s\g<2>' % pdf_name(ed['slug']), s)
    # "Read the September issue" in gold, on the home page and on the page a
    # reader lands on the moment they confirm their subscription. Both named the
    # wrong month for a month.
    return re.sub(r'<a class="btn btn--gold" href="/editions/[a-z]+-\d{4}">Read the [A-Za-z]+ issue</a>',
                  '<a class="btn btn--gold" href="/editions/%s">Read the %s issue</a>'
                  % (ed['slug'], esc(ed['month'].split()[0])), s)


def update_archive(ed, path='archive.html'):
    s = open(path, encoding='utf-8').read()
    before = s
    if 'Vol. %d, No. %d' % (ed['volume'], ed['number']) not in s:
        anchor = '<div class="grid-cards">\n'
        i = s.index(anchor) + len(anchor)
        s = s[:i] + archive_card(ed) + s[i:]
    s = current_issue_links(s, ed)
    if s == before:
        return False
    open(path, 'w', encoding='utf-8').write(s)
    return True


def update_index(ed, path='index.html'):
    """Rewrite every part of the home page that belongs to a particular issue.

    This used to repoint the links and patch three labels, leaving the lede, the
    figures, the featured story and the archive cards exactly as a person had
    typed them. The result on publication day was a home page carrying October's
    headline, October's links and September's journalism — a gold button reading
    "Read the September issue", and a card headed "Vol. 1, No. 9 · September
    2026" whose "Read online" link had been rewritten to point at October, so
    September was unreachable from the front page. Anything that names an issue
    is generated here now.
    """
    s = open(path, encoding='utf-8').read()
    before = s
    # ------ hero
    s = re.sub(r'(<div class="hero__meta">\s*<span>)[^<]*(</span><span>)Vol\. \d+, No\. \d+(</span>)',
               r'\g<1>%s\g<2>Vol. %d, No. %d\g<3>' % (esc(ed['month']), ed['volume'], ed['number']),
               s, count=1)
    s = re.sub(r'(<div class="shell hero__inner">.*?<h1>)(.*?)(</h1>)',
               lambda m: m.group(1) + esc(ed['headline']) + m.group(3), s, count=1, flags=re.S)
    s = re.sub(r'(<p class="hero__lede">)(.*?)(</p>)',
               lambda m: m.group(1) + '\n            ' + esc(plain(ed['dek']))
               + '\n          ' + m.group(3), s, count=1, flags=re.S)
    s = re.sub(r'<a class="btn btn--gold" href="[^"]*">[^<]*</a>',
               '<a class="btn btn--gold" href="/editions/%s">Read the %s issue</a>'
               % (ed['slug'], esc(ed['month'].split()[0])), s, count=1)

    # ------ by the numbers
    s = re.sub(r'(<p class="eyebrow">By the numbers &mdash; )[^<]*(</p>)',
               r'\g<1>%s\g<2>' % esc(ed['month']), s, count=1)
    s = re.sub(r'(<div class="numbers">\n).*?(\n          </div>)',
               lambda m: m.group(1) + number_cells(ed) + m.group(2), s, count=1, flags=re.S)

    # ------ featured story
    s = re.sub(r'(<p class="eyebrow eyebrow--ink">Featured story</p>\s*<h2>)(.*?)(</h2>)',
               lambda m: m.group(1) + esc(ed['featured']['title']) + m.group(3),
               s, count=1, flags=re.S)
    s = re.sub(r'(<div class="feature__body">\n).*?(\n            </div>)',
               lambda m: m.group(1) + feature_body(ed) + m.group(2), s, count=1, flags=re.S)
    s = re.sub(r'(<h4>What moved this month</h4>\s*<ul class="keylist">\n).*?(\n              </ul>)',
               lambda m: m.group(1) + keylist(ed) + m.group(2), s, count=1, flags=re.S)

    # ------ the archive strip, and everything that links to an issue
    s = re.sub(r'(<div class="grid-cards">\n)(.*?)(\n          </div>)',
               lambda m: m.group(1) + refresh_cards(m.group(2), ed) + m.group(3),
               s, count=1, flags=re.S)
    s = re.sub(r'(<a href=")/editions/[a-z]+-\d{4}(">Full issue</a>)',
               r'\g<1>/editions/%s\g<2>' % ed['slug'], s, count=1)
    s = current_issue_links(s, ed)
    if ed.get('data_as_of'):
        s = re.sub(r'(<span>)Data as of [^<]*(</span>)',
                   r'\g<1>%s\g<2>' % esc(plain(ed['data_as_of'])), s, count=1)

    if s != before:
        open(path, 'w', encoding='utf-8').write(s)
        return True
    return False


# ------------------------------------------------------------------------ main

def load_prev(ed, directory=os.path.join('content', 'editions')):
    """Find the preceding edition among the other JSON files.

    Falls back to an explicit "previous" block in the edition itself, which
    exists so an edition can render faithfully before its predecessor has been
    back-ported. The JSON files win when both are present.
    """
    for name in sorted(os.listdir(directory)):
        if not name.endswith('.json'):
            continue
        other = json.load(open(os.path.join(directory, name), encoding='utf-8'))
        if other.get('number') == ed['number'] - 1:
            return other
    return ed.get('previous')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('edition', help='content/editions/<slug>.json')
    ap.add_argument('--dry-run', action='store_true', help='print the page, write nothing')
    ap.add_argument('--page-only', action='store_true',
                    help='write the edition page but leave index/archive/sitemap/vercel alone')
    args = ap.parse_args()

    ed = json.load(open(args.edition, encoding='utf-8'))
    html = render_page(ed, prev=load_prev(ed))

    if args.dry_run:
        sys.stdout.write(html)
        return 0

    out = os.path.join('editions', '%s.html' % ed['slug'])
    os.makedirs('editions', exist_ok=True)
    open(out, 'w', encoding='utf-8').write(html)
    print('wrote %s (%d KB)' % (out, round(len(html) / 1024)))

    if args.page_only:
        return 0
    for label, fn in (('sitemap.xml', update_sitemap), ('vercel.json', update_vercel),
                      ('archive.html', update_archive), ('index.html', update_index),
                      ('subscribe.html', update_sampler)):
        print('  %-14s %s' % (label, 'updated' if fn(ed) else 'already current'))

    # Every page carries "Current issue" and "Download PDF" in its footer, and
    # nothing outside index.html had ever rewritten them — so about, submit,
    # subscribe and both confirmation pages spent a month pointing at September.
    for name in sorted(f for f in os.listdir('.') if f.endswith('.html')):
        if name in ('index.html', 'archive.html'):
            continue
        page = open(name, encoding='utf-8').read()
        fixed = current_issue_links(page, ed)
        if fixed != page:
            open(name, 'w', encoding='utf-8').write(fixed)
            print('  %-14s updated' % name)
    return 0


if __name__ == '__main__':
    sys.exit(main())
