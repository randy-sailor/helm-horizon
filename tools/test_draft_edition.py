#!/usr/bin/env python3
"""Prove the drafting layer decides what the model must not.

    python3 tools/test_draft_edition.py

The model is asked to research and write. It is not asked for the edition
number, the publication date, the previous-issue link, an image path, or a
reader quote — and these check that it cannot supply them by accident either.
"""
import json
import os
import sys
import types
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


# ------------------------------------------- the provider resumes a paused turn

# A long web-search turn stops at the server's ten-iteration limit with
# stop_reason "pause_turn": no text block, no error, an unfinished answer.
# October's re-run spent eight minutes on exactly that and came back empty.
# The API resumes when the exchange is re-sent, so this stands in a fake client
# and proves the loop does it — there is no way to reach the real API from a
# test, and finding out in the monthly run costs a research call.

class _Block:
    def __init__(self, text=None, kind='text'):
        self.type = kind
        self.text = text


class _Msg:
    def __init__(self, stop_reason, blocks):
        self.stop_reason = stop_reason
        self.content = blocks


class _Stream:
    def __init__(self, msg):
        self._msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self._msg


class _Messages:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def stream(self, **kw):
        self.calls.append(kw)
        return _Stream(self.script.pop(0))


class _Client:
    def __init__(self, script):
        self.messages = _Messages(script)


def run_provider(script, max_resumes=None):
    """Drive AnthropicProvider.research against a scripted fake client."""
    fake = types.ModuleType('anthropic')
    client = _Client(script)
    fake.Anthropic = lambda *a, **k: client
    old_mod, old_key = sys.modules.get('anthropic'), os.environ.get('ANTHROPIC_API_KEY')
    sys.modules['anthropic'] = fake
    os.environ['ANTHROPIC_API_KEY'] = 'test'
    prov = D.AnthropicProvider()
    if max_resumes is not None:
        prov.MAX_RESUMES = max_resumes
    try:
        return prov.research(brief, D.wire_schema(images)), client.messages
    finally:
        if old_mod is None:
            sys.modules.pop('anthropic', None)
        else:
            sys.modules['anthropic'] = old_mod
        if old_key is None:
            os.environ.pop('ANTHROPIC_API_KEY', None)
        else:
            os.environ['ANTHROPIC_API_KEY'] = old_key


paused = _Msg('pause_turn', [_Block(kind='server_tool_use')])
finished = _Msg('end_turn', [_Block(json.dumps({'headline': 'Done'}))])

out, msgs = run_provider([paused, finished])
check('a paused turn is resumed rather than failed',
      out == {'headline': 'Done'} and len(msgs.calls) == 2,
      '%d request(s), got %r' % (len(msgs.calls), out))

# The resume must re-send the exchange, not invent a "continue" message.
second = msgs.calls[1]['messages']
check('the resume re-sends the user turn and the paused assistant turn',
      len(second) == 2 and second[0]['role'] == 'user'
      and second[1]['role'] == 'assistant',
      str([m['role'] for m in second]))

out, msgs = run_provider([paused, paused, finished])
check('it resumes more than once when the search runs long',
      out == {'headline': 'Done'} and len(msgs.calls) == 3,
      '%d request(s)' % len(msgs.calls))

try:
    run_provider([paused, paused, paused], max_resumes=1)
    check('it gives up rather than looping forever', False)
except SystemExit as e:
    check('it gives up rather than looping forever', 'still paused' in str(e), str(e))

try:
    run_provider([_Msg('refusal', [])])
    check('a refusal is reported, not parsed', False)
except SystemExit as e:
    check('a refusal is reported, not parsed', 'declined' in str(e), str(e))


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
