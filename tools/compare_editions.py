#!/usr/bin/env python3
"""Prove a rendered edition matches the published one.

    python3 tools/compare_editions.py editions/september-2026.html --rendered /tmp/x.html
    python3 tools/compare_editions.py --live september-2026 --rendered /tmp/x.html

Raw bytes are not compared: whitespace and attribute order differ harmlessly.
What must match is what a reader and a search engine see —

  * normalized visible text
  * the set of href values
  * the set of anchor ids
  * heading text, in order

Differences are reported, never normalized away silently.
"""

import argparse
import difflib
import re
import sys
import urllib.request
from html.parser import HTMLParser

SITE = 'https://www.thehelmandhorizon.com'
SKIP_TEXT = {'script', 'style'}


class Doc(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.hrefs = set()
        self.ids = set()
        self.headings = []
        self._skip = 0
        self._heading = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in SKIP_TEXT:
            self._skip += 1
        if a.get('href'):
            self.hrefs.add(a['href'])
        if a.get('id'):
            self.ids.add(a['id'])
        if tag in ('h1', 'h2', 'h3', 'h4'):
            self._heading = [tag, []]

    def handle_endtag(self, tag):
        if tag in SKIP_TEXT and self._skip:
            self._skip -= 1
        if tag in ('h1', 'h2', 'h3', 'h4') and self._heading:
            self.headings.append((self._heading[0], squash(''.join(self._heading[1]))))
            self._heading = None

    def handle_data(self, data):
        if self._skip:
            return
        self.text.append(data)
        if self._heading is not None:
            self._heading[1].append(data)


def squash(s):
    return re.sub(r'\s+', ' ', s).strip()


def parse(html):
    d = Doc()
    d.feed(html)
    d.body = squash(''.join(d.text))
    return d


def fetch(slug):
    url = '%s/editions/%s' % (SITE, slug)
    req = urllib.request.Request(url, headers={'User-Agent': 'helm-horizon-parity/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')


def report(label, a, b, limit=12):
    """Report set differences in both directions."""
    only_a = sorted(a - b)
    only_b = sorted(b - a)
    if not only_a and not only_b:
        print('  ok    %s (%d)' % (label, len(a)))
        return 0
    print('  DIFF  %s' % label)
    for x in only_a[:limit]:
        print('          only in published: %s' % str(x)[:110])
    for x in only_b[:limit]:
        print('          only in rendered:  %s' % str(x)[:110])
    extra = max(len(only_a) - limit, 0) + max(len(only_b) - limit, 0)
    if extra:
        print('          ... and %d more' % extra)
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('published', nargs='?', help='path to the published HTML')
    ap.add_argument('--live', metavar='SLUG', help='fetch the published page from the live site')
    ap.add_argument('--rendered', required=True, help='path to the freshly rendered HTML')
    ap.add_argument('--ignore-href', action='append', default=[],
                    help='substring of href values to exclude (repeatable)')
    args = ap.parse_args()

    if args.live:
        try:
            pub_html = fetch(args.live)
            source = '%s/editions/%s' % (SITE, args.live)
        except Exception as e:
            print('could not fetch the live page: %s' % e, file=sys.stderr)
            print('run without --live to compare against the committed HTML', file=sys.stderr)
            return 2
    elif args.published:
        pub_html = open(args.published, encoding='utf-8').read()
        source = args.published
    else:
        ap.error('give a published path or --live SLUG')

    pub = parse(pub_html)
    ren = parse(open(args.rendered, encoding='utf-8').read())

    print('published: %s' % source)
    print('rendered:  %s\n' % args.rendered)

    fails = 0

    def keep(h):
        return not any(sub in h for sub in args.ignore_href)

    fails += report('href set', {h for h in pub.hrefs if keep(h)},
                    {h for h in ren.hrefs if keep(h)})
    fails += report('anchor ids', pub.ids, ren.ids)

    if pub.headings == ren.headings:
        print('  ok    headings (%d, in order)' % len(pub.headings))
    else:
        fails += 1
        print('  DIFF  headings')
        for line in list(difflib.unified_diff(
                ['%s %s' % h for h in pub.headings],
                ['%s %s' % h for h in ren.headings],
                'published', 'rendered', lineterm='', n=1))[:30]:
            print('          %s' % line)

    if pub.body == ren.body:
        print('  ok    visible text (%d chars)' % len(pub.body))
    else:
        fails += 1
        print('  DIFF  visible text')
        sm = difflib.SequenceMatcher(None, pub.body, ren.body, autojunk=False)
        print('          similarity %.4f' % sm.ratio())
        shown = 0
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == 'equal' or shown >= 8:
                continue
            shown += 1
            print('          %-7s published %r' % (op, pub.body[i1:i2][:90]))
            print('          %-7s rendered  %r' % ('', ren.body[j1:j2][:90]))

    print()
    if fails:
        print('%d difference(s) — review each before trusting the renderer' % fails)
        return 1
    print('parity confirmed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
