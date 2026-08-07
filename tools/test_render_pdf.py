#!/usr/bin/env python3
"""Prove the PDF carries what the page carries.

    python3 tools/test_render_pdf.py

A PDF is hard to eyeball in CI, so this checks the things that would actually
hurt: a citation that stopped being clickable, a quote printed without
permission, and a character the chosen font cannot draw printing as a box.
"""
import copy
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_pdf as R  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDITION = os.path.join(ROOT, 'content', 'editions', 'september-2026.json')

failures = []


def check(desc, ok, detail=''):
    print('%-5s %s%s' % ('PASS' if ok else 'FAIL', desc, ('  — %s' % detail) if detail else ''))
    if not ok:
        failures.append(desc)


# ------------------------------------------------------ markdown -> ReportLab

check('a link becomes an anchor',
      R.rl('see [Reuters](https://r.example/a)')
      == 'see <a href="https://r.example/a" color="#0b5fa5">Reuters</a>')
check('bold becomes <b>, not <strong>',
      R.rl('**up 8%**') == '<b>up 8%</b>', R.rl('**up 8%**'))
check('angle brackets are escaped before the parser sees them',
      R.rl('a < b & c') == 'a &lt; b &amp; c', R.rl('a < b & c'))
check('a URL with an ampersand survives escaping',
      '&amp;' in R.rl('[x](https://e.example/?a=1&b=2)'), R.rl('[x](https://e.example/?a=1&b=2)'))
check('flatten strips markdown for canvas text',
      R.flatten('**Margins** up, see [source](https://e.example)')
      == 'Margins up, see source', R.flatten('**Margins** up, see [source](https://e.example)'))

# Helvetica is WinAnsi-only. A minus sign left alone prints as a black box, which
# a reader reads as a broken figure rather than a missing glyph.
check('minus and arrow are transliterated on the WinAnsi path',
      R.rl('−7% and 118 → 83', unicode_ok=False) == '-7% and 118 -> 83',
      R.rl('−7% and 118 → 83', unicode_ok=False))
check('they are left alone when the font can draw them',
      R.rl('−7%', unicode_ok=True) == '−7%')
check('every transliteration target is plain ASCII',
      all(ord(c) < 128 for v in R.NON_WINANSI.values() for c in v))

# The banner is drawn onto the canvas, so it cannot reflow — the wrapper has to
# guarantee it never asks for a third line.
for h in ['Margins Up, Volumes Down: The Second-Half Split Screen',
          'Short One',
          'A ' * 40]:
    lines = R.wrap_headline(h)
    check('headline wraps to at most two banner lines (%d chars)' % len(h),
          len(lines) <= 2 and ' '.join(lines).split() == h.split(), str(len(lines)))


# --------------------------------------------------------- fonts and the build

body, bold, italic, name = R.resolve_fonts()
check('a font resolves', bool(body and bold and italic), name)

ed = json.load(open(EDITION, encoding='utf-8'))
out = os.path.join(tempfile.mkdtemp(), 'test.pdf')
font_used, unicode_ok = R.render(ed, out)
raw = open(out, 'rb').read()

check('output is a PDF', raw[:5] == b'%PDF-', str(raw[:8]))
check('output is not a stub', len(raw) > 20000, '%d KB' % (len(raw) // 1024))

# Every figure is cited on the page; every citation must still be clickable in
# the PDF, or the sourcing standard quietly stops applying to the download.
annotated = {u.decode('latin-1') for u in re.findall(rb'/URI\s*\(([^)]+)\)', raw)}
wanted = set()


def walk(n):
    if isinstance(n, str):
        wanted.update(u for _, u in R.MD_LINK.findall(n))
    elif isinstance(n, dict):
        if isinstance(n.get('url'), str):
            wanted.add(n['url'])
        for v in n.values():
            walk(v)
    elif isinstance(n, list):
        for v in n:
            walk(v)


walk(ed)
missing = sorted(wanted - annotated)
check('every cited URL is a live link annotation (%d)' % len(wanted),
      not missing, '; '.join(m[:70] for m in missing[:3]))

check('the subscribe call to action links out',
      any('/subscribe' in u for u in annotated))


# -------------------------------------------------------- the permission guard

# The validator refuses this edition outright. The renderer refuses it too,
# because a renderer that would print an uncleared quote if the validator were
# skipped is a liability rather than a convenience.
doctored = copy.deepcopy(ed)
doctored['voices'] = [{'quote': 'Off the record, it is worse than it looks.',
                       'attribution': 'A broker who did not agree to this'}]
try:
    R.render(doctored, os.path.join(tempfile.mkdtemp(), 'bad.pdf'))
    check('refuses to render a quote without permission', False)
except SystemExit as e:
    check('refuses to render a quote without permission',
          'without permission' in str(e), str(e))

doctored['voices'][0]['permission_to_quote'] = True
try:
    R.render(doctored, os.path.join(tempfile.mkdtemp(), 'ok.pdf'))
    check('renders a quote once permission is recorded', True)
except SystemExit as e:
    check('renders a quote once permission is recorded', False, str(e))


print('\n%s' % ('all checks passed' if not failures
                else '%d FAILED: %s' % (len(failures), '; '.join(failures))))
sys.exit(1 if failures else 0)
