#!/usr/bin/env python3
"""Prove the drafting layer decides what the model must not.

    python3 tools/test_draft_edition.py

The model is asked to research and write. It is not asked for the edition
number, the publication date, the previous-issue link, an image path, or a
reader quote — and these check that it cannot supply them by accident either.
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import draft_edition as D  # noqa: E402
import validate_edition as V  # noqa: E402

failures = []


def check(desc, ok, detail=''):
    print('%-5s %s%s' % ('PASS' if ok else 'FAIL', desc, ('  — %s' % detail) if detail else ''))
    if not ok:
        failures.append(desc)


# ------------------------------------------------------------------- calendar

# Helm & Horizon publishes on the first Thursday. September 2026 shipped on the
# 3rd, so these are checked against a real, already-published issue.
check('first Thursday of September 2026 is the 3rd',
      D.first_thursday(2026, 9) == date(2026, 9, 3), str(D.first_thursday(2026, 9)))
check('first Thursday of October 2026 is the 1st',
      D.first_thursday(2026, 10) == date(2026, 10, 1), str(D.first_thursday(2026, 10)))
check('first Thursday when the 1st is itself a Thursday is the 1st',
      D.first_thursday(2027, 4) == date(2027, 4, 1), str(D.first_thursday(2027, 4)))
check('first Thursday when the 1st is a Friday is the 7th',
      D.first_thursday(2027, 1) == date(2027, 1, 7), str(D.first_thursday(2027, 1)))

check('December rolls into the next January',
      D.next_month(date(2026, 12, 3)) == (2027, 1), str(D.next_month(date(2026, 12, 3))))
check('August targets September',
      D.next_month(date(2026, 8, 6)) == (2026, 9), str(D.next_month(date(2026, 8, 6))))

for text, want in [('2026-10', (2026, 10)), ('October 2026', (2026, 10)),
                   ('october-2026', (2026, 10)), ('2027-1', (2027, 1))]:
    check('parses %r' % text, D.parse_month(text) == want)
try:
    D.parse_month('Smarch 2026')
    check('rejects a month that does not exist', False)
except ValueError:
    check('rejects a month that does not exist', True)


# ---------------------------------------------------- the brief, off real data

editions = D.load_editions()
images = D.available_images()
check('there are editions on disk to sequence against', bool(editions), '%d found' % len(editions))
check('there are images on disk to reference', bool(images), ', '.join(images))

brief = D.build_brief(2026, 10, editions, images)
latest = D.latest_edition(editions)
check('number follows the highest edition on disk',
      brief['number'] == latest['number'] + 1, '%d -> %d' % (latest['number'], brief['number']))
check('slug is derived, not drafted', brief['slug'] == 'october-2026', brief['slug'])
check('publication date is the first Thursday', brief['published'] == '2026-10-01',
      brief['published'])
check('previous points at the highest edition on disk',
      brief['previous']['slug'] == latest['slug'], brief['previous']['slug'])

# Redrafting an issue that already exists — the editor re-running closer to
# publication for fresher figures — must not push it down the sequence.
redraft = D.build_brief(*D.parse_month(latest['slug']), editions=editions, images=images)
check('a redraft keeps the existing edition number',
      redraft['number'] == latest['number'], '%d' % redraft['number'])
check('a redraft keeps the existing previous-issue link',
      redraft['previous'] == latest.get('previous'), repr(redraft['previous']))


# ------------------------------------------------- what the model cannot smuggle

draft = D.StubProvider().research(brief, D.wire_schema(images))

# A quote from a reader who has not confirmed permission must never reach a page.
# The wire schema has no voices field at all; this proves that even a provider
# that returned one would be ignored rather than trusted.
draft_with_quote = dict(draft)
draft_with_quote['voices'] = [{'quote': 'Off the record, things are dire.',
                               'attribution': 'A broker'}]
ed = D.to_edition(draft_with_quote, brief)
check('an unsolicited voices entry is dropped, not passed through', ed['voices'] == [],
      repr(ed['voices']))

check('edition number comes from the brief, not the draft', ed['number'] == brief['number'])
check('slug comes from the brief', ed['slug'] == brief['slug'])
check('published comes from the brief', ed['published'] == brief['published'])

figures = [s for s in ed['featured']['sections'] if 'figure' in s]
prose = [s for s in ed['featured']['sections'] if 'heading' in s]
check('a figure section becomes {figure: ...}', len(figures) == 1, str(len(figures)))
check('prose sections keep heading and body', len(prose) == 2, str(len(prose)))
check('an empty heading becomes null, not ""',
      ed['profile']['sections'][0]['heading'] is None,
      repr(ed['profile']['sections'][0]['heading']))

# An image path that is not in the repository would render as a broken image and
# nothing downstream would notice, so it is refused here.
bad = dict(draft, hero_image='/assets/img/does-not-exist.webp')
try:
    D.to_edition(bad, brief)
    check('refuses an image that is not in the repository', False)
except SystemExit as e:
    check('refuses an image that is not in the repository', 'does not exist' in str(e), str(e))


# --------------------------------------------- the stub survives the validator

# If the stub could not pass validation, the workflow's dry run would prove
# nothing about the real path.
tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.stub-draft.json')
import json  # noqa: E402
json.dump(D.to_edition(draft, brief), open(tmp, 'w', encoding='utf-8'), indent=2)
try:
    p = V.validate(tmp, offline=True)
    check('a stub draft passes the validator', not p,
          ' | '.join('%s: %s' % i for i in p.items))
finally:
    os.remove(tmp)


print('\n%s' % ('all checks passed' if not failures
                else '%d FAILED: %s' % (len(failures), '; '.join(failures))))
sys.exit(1 if failures else 0)
