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
