#!/usr/bin/env python3
"""Prove the site's shared pages actually follow the current issue.

    python3 tools/test_render_html.py

There was no test here, and the pages rotted exactly where nobody was looking.
October published with a gold button reading "Read the September issue", a "By
the numbers" panel full of September's figures under an October heading, a
featured story that was still September's, and five pages whose footers pointed
at the previous issue. Worst of all, the card headed "Vol. 1, No. 9 · September
2026" had its "Read online" link rewritten to October, so September was
unreachable from the front page.

Every check below is one of those defects, written so it fails if it returns.
"""
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_html as R  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
failures = []


def check(desc, ok, detail=''):
    print('%-5s %s%s' % ('PASS' if ok else 'FAIL', desc, ('  — %s' % detail) if detail else ''))
    if not ok:
        failures.append(desc)


MONTHS = ('january february march april may june july august september october '
          'november december').split()

CARD = re.compile(r'<article class="card[^"]*">.*?</article>', re.S)
CARD_VOL = re.compile(r'Vol\. \d+, No\. \d+ &middot; ([A-Za-z]+) (\d{4})')


def edition(number, month, year=2026, headline=None):
    """A minimal edition, shaped like the real thing."""
    slug = '%s-%d' % (month.lower(), year)
    return {
        'volume': 1, 'number': number, 'month': '%s %d' % (month, year), 'slug': slug,
        'published': '%d-%02d-01' % (year, MONTHS.index(month.lower()) + 1),
        'headline': headline or 'Headline for %s' % month,
        'dek': 'The dek for %s, which is what the hero lede should say.' % month,
        'description': 'd', 'hero': {'image': '/assets/img/x.webp', 'alt': 'a'},
        'from_the_desk': ['p'],
        'featured': {
            'title': '%s Feature Title' % month,
            'sections': [{'heading': 'The %s section heading' % month,
                          'body': ['First %s paragraph.' % month,
                                   'Second %s paragraph.' % month,
                                   'Third %s paragraph.' % month]}],
            'takeaway': {'eyebrow': 'Key takeaway', 'body': 'b'},
        },
        'indicators': [
            {'region': 'us', 'label': 'Retail unit sales, rolling twelve months to April',
             'value': '214,292 units · −7.1%', 'source': {'title': 't', 'url': 'https://e.gov'}},
            {'region': 'us', 'label': 'Second indicator, some qualifier',
             'value': '89.4 · steady', 'source': {'title': 't', 'url': 'https://e.gov'}},
        ],
        'risks': [], 'actions': [], 'voices': [], 'voices_intro': [],
        'profile': {'company': 'C', 'ticker': '', 'dek': 'd', 'sections': []},
        'colophon': 'c', 'data_as_of': 'Data as of late %s 2026.' % month,
    }


# ------------------------------------------------------ the pieces, in isolation

sep, oct_ = edition(9, 'September'), edition(10, 'October')

# str.capitalize() lowercases everything after the first letter, which turned
# "rolling twelve months to April" into "...to april" on the live page.
check('sentence-casing does not lowercase the words after the first',
      R._sentence('rolling twelve months to April') == 'Rolling twelve months to April.',
      R._sentence('rolling twelve months to April'))
check('an already-terminated fragment does not gain a second full stop',
      R._sentence('Unchanged.') == 'Unchanged.', R._sentence('Unchanged.'))
check('an empty qualifier stays empty', R._sentence('   ') == '')

cells = R.number_cells(oct_)
check('a figure cell leads with the figure', '214,292 units' in cells)
check('a figure cell bolds the subject, not the whole label',
      '<strong>Retail unit sales</strong>' in cells,
      re.search(r'<strong>[^<]*</strong>', cells).group(0))
check('the label qualifier and the rest of the value become the small print',
      'Rolling twelve months to April. −7.1%.' in cells)
check('only as many cells as the design has slots', cells.count('numbers__cell') == 2)

body = R.feature_body(oct_)
check('the featured trailer uses the issue\'s own first section',
      'The October section heading' in body and 'First October paragraph.' in body)
check('the trailer is a trailer, not the whole article',
      'Third October paragraph.' not in body)
check('the trailer\'s button points at this issue',
      'href="/editions/october-2026"' in body)

rail = R.keylist(oct_)
check('the rail drops the label qualifier to fit',
      '<strong>Retail unit sales</strong>' in rail and 'rolling twelve' not in rail)


# --------------------------------------------- the pages, against real markup

work = tempfile.mkdtemp()
try:
    for name in ('index.html', 'archive.html', 'subscribe.html', 'confirmed.html',
                 'about.html', 'submit.html'):
        shutil.copy(os.path.join(ROOT, name), os.path.join(work, name))
    here = os.getcwd()
    os.chdir(work)

    # Render September first and insist the page is *wholly* September before
    # moving to October. Without this the checks below would pass against a
    # renderer that never touches the button or the lede, because the fixture
    # copied off disk already says October.
    R.update_index(sep)
    stepped = open('index.html', encoding='utf-8').read()
    check('rendering an issue rewrites the button to that issue',
          'Read the September issue' in stepped and 'Read the October issue' not in stepped)
    check('rendering an issue rewrites the lede to that issue',
          'The dek for September' in stepped and 'The dek for October' not in stepped)
    check('rendering an issue rewrites the featured story to that issue',
          'September Feature Title' in stepped and 'October Feature Title' not in stepped)

    R.update_index(oct_)
    page = open('index.html', encoding='utf-8').read()

    # The defect the reader saw first.
    check('the gold button names the issue it links to',
          '<a class="btn btn--gold" href="/editions/october-2026">Read the October issue</a>'
          in page)
    check('no page still offers the previous issue by name',
          'Read the September issue' not in page)

    check('the hero lede is this issue\'s dek',
          'The dek for October' in page and 'The dek for September' not in page)
    check('the hero headline is this issue\'s', 'Headline for October' in page)
    check('the numbers panel is this issue\'s figures',
          'By the numbers &mdash; October 2026' in page and '214,292 units' in page)
    check('the featured story is this issue\'s',
          'October Feature Title' in page and 'First October paragraph.' in page
          and 'September Feature Title' not in page)
    check('the colophon carries this issue\'s data date',
          'Data as of late October 2026.' in page)

    # The one that took September off the site: a card kept its own heading while
    # its links were rewritten to the newest issue.
    mismatched = []
    for card in CARD.findall(page):
        v = CARD_VOL.search(card)
        if not v:
            continue
        slug = '%s-%s' % (v.group(1).lower(), v.group(2))
        for href in re.findall(r'href="/editions/([a-z]+-\d{4})"', card):
            if href != slug:
                mismatched.append('%s card -> %s' % (slug, href))
    check('every archive card links to its own issue, not the newest',
          not mismatched, '; '.join(mismatched))

    check('the newest issue leads the archive strip',
          page.index('October 2026</p>') < page.index('September 2026</p>'))

    # The earliest issues predate content/editions/ and exist only as a card and
    # a PDF. Rebuilding the strip from the JSON on disk would drop them.
    check('an issue with no JSON on disk keeps its card',
          'August 2026' in page)

    # Every page carries these, and only index.html was ever updated.
    for name in ('confirmed.html', 'about.html', 'submit.html', 'subscribe.html'):
        text = open(name, encoding='utf-8').read()
        text = R.current_issue_links(text, oct_)
        open(name, 'w', encoding='utf-8').write(text)
        check('%s points at the current issue' % name,
              '/editions/october-2026">Current issue' in text
              and '/editions/september-2026">Current issue' not in text)

    check('the confirmation page stops promoting the old issue by name',
          'Read the October issue' in open('confirmed.html', encoding='utf-8').read())

    R.update_sampler(oct_)
    sampler = open('subscribe.html', encoding='utf-8').read()
    check('the subscribe sampler leads with the newest issue',
          sampler.index('October 2026</p>') < sampler.index('September 2026</p>'))
    check('the sampler keeps its own card styling',
          '<article class="card">' in sampler)

    # Running the renderer twice must not compound. A generated region that
    # re-matches its own output would double or drift on every publication.
    before = open('index.html', encoding='utf-8').read()
    R.update_index(oct_)
    check('re-rendering the same issue changes nothing',
          open('index.html', encoding='utf-8').read() == before)
finally:
    os.chdir(here)
    shutil.rmtree(work, ignore_errors=True)


print('\n%s' % ('all checks passed' if not failures
                else '%d FAILED: %s' % (len(failures), '; '.join(failures))))
sys.exit(1 if failures else 0)
