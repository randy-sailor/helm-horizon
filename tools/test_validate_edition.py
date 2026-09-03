#!/usr/bin/env python3
"""Prove the validator rejects what it is supposed to reject.

    python3 tools/test_validate_edition.py

A validator that never fails is worse than none, so each fixture isolates one
defect and asserts both that it is caught and that the message names it.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate_edition as V  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')

# The fixtures are numbered 10, so they need an archive whose highest edition is
# 9 to sequence against. Building that here rather than borrowing the real
# content/editions keeps these tests hermetic: they used to start failing the
# moment a new edition landed on disk, which is how the drafting workflow
# caught this — it writes a draft and then runs these.
ARCHIVE = tempfile.mkdtemp()
json.dump({'volume': 1, 'number': 9, 'slug': 'prior-2026'},
          open(os.path.join(ARCHIVE, 'prior-2026.json'), 'w', encoding='utf-8'))

CASES = [
    ('valid.json', None, 'baseline must pass'),
    ('missing_source.json', 'must cite a primary source', 'indicator with no source'),
    ('voice_without_permission.json', 'permission_to_quote', 'quote without permission'),
    ('four_actions.json', 'exactly 3 steps', 'four action steps'),
    ('wrong_number.json', 'expected', 'edition number out of sequence'),
    ('http_source.json', 'not https', 'insecure source URL'),
    # Added after October's first real draft shipped two risk panels reading
    # "Placeholder", cited to example.com, past every structural rule.
    ('placeholder_body.json', 'placeholder text', 'stub prose left in a risk body'),
    ('example_source.json', 'reserved example domain', 'a citation to example.com'),
    ('short_body.json', 'too short to be real', 'an action step of a few words'),
]

failures = 0
for name, expect, desc in CASES:
    p = V.validate(os.path.join(FIX, name), offline=True, editions_dir=ARCHIVE)
    msgs = ' | '.join('%s: %s' % (w, m) for w, m in p.items)
    if expect is None:
        ok = not p
        detail = msgs if p else ''
    else:
        ok = bool(p) and expect in msgs
        detail = msgs if not ok else next(m for w, m in p.items if expect in m)
    print('%-5s %-34s %s' % ('PASS' if ok else 'FAIL', desc, detail[:88]))
    if not ok:
        failures += 1

# An archive with more than one issue in it. The sequence rule used to be
# "exactly one greater than the highest other edition", which is right for a
# draft joining the archive and wrong for every issue already in it: the day
# October landed, `validate_edition.py` with no arguments turned red because
# September was number 9 and not 11. These fix the rule in place.
print()
SEQ = tempfile.mkdtemp()


def seq_write(number, slug):
    ed = json.load(open(os.path.join(FIX, 'valid.json'), encoding='utf-8'))
    ed['number'], ed['slug'] = number, slug
    path = os.path.join(SEQ, '%s.json' % slug)
    json.dump(ed, open(path, 'w', encoding='utf-8'))
    return path


september = seq_write(9, 'september-2026')
october = seq_write(10, 'october-2026')


def sequence_case(path, expect, desc):
    global failures
    p = V.validate(path, offline=True, editions_dir=SEQ)
    msgs = ' | '.join('%s: %s' % (w, m) for w, m in p.items)
    ok = (not p) if expect is None else (bool(p) and expect in msgs)
    print('%-5s %-34s %s' % ('PASS' if ok else 'FAIL', desc, msgs[:88]))
    if not ok:
        failures += 1


# The two that were failing on the live archive: each existing issue, checked
# against the other. This is what `validate_edition.py` with no arguments does.
sequence_case(september, None, 'an older issue in a full archive')
sequence_case(october, None, 'the newest issue in a full archive')

# And the protections the old rule existed for, still firing.
for number, expect, desc in ((11, None, 'the next issue after the newest'),
                             (10, 'already taken', 'a number another edition uses'),
                             (13, 'leaves a gap', 'a number that skips ahead')):
    subject = seq_write(number, 'subject-2026')
    try:
        sequence_case(subject, expect, desc)
    finally:
        os.remove(subject)

# The URL classifier decides what counts as a dead link; check the policy
# directly rather than over the network, which CI may or may not allow.
print()
import urllib.error  # noqa: E402


def fake(code):
    def _open(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, code, 'x', {}, None)
    return _open


orig = V.urllib.request.urlopen
for code, should_fail in [(404, True), (410, True), (403, False), (405, False), (429, False)]:
    V.urllib.request.urlopen = fake(code)
    reason = V.check_url('https://example.com/x')
    ok = bool(reason) == should_fail
    print('%-5s HTTP %-4s -> %-14s (%s)' % ('PASS' if ok else 'FAIL', code,
                                            reason or 'reachable',
                                            'dead link' if should_fail else 'allowed'))
    if not ok:
        failures += 1
V.urllib.request.urlopen = orig

# Inline prose citations must be collected, not just structured sources.
ed = {'body': ['See [Reuters](https://reuters.example/a) and [NMMA](https://nmma.example/b).'],
      'indicators': [{'source': {'url': 'https://struct.example/c'}}]}
urls = V.collect_urls(ed)
ok = urls == ['https://nmma.example/b', 'https://reuters.example/a', 'https://struct.example/c']
print('\n%-5s collects inline prose links and structured sources (%d found)'
      % ('PASS' if ok else 'FAIL', len(urls)))
if not ok:
    failures += 1

print('\n%s' % ('all checks passed' if not failures else '%d FAILED' % failures))
sys.exit(1 if failures else 0)
