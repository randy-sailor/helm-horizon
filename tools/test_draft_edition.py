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

# The target is the month after the newest issue on disk, worked out here rather
# than written in. Hardcoding "October 2026" passed until October published, and
# then failed inside the drafting workflow's own pre-flight — a test that expires
# the moment the thing it tests starts working.
latest = D.latest_edition(editions)
year, month = D.next_month(date.fromisoformat(latest['published']))
brief = D.build_brief(year, month, editions, images)
check('number follows the highest edition on disk',
      brief['number'] == latest['number'] + 1, '%d -> %d' % (latest['number'], brief['number']))
check('slug is derived, not drafted',
      brief['slug'] == '%s-%d' % (D.MONTHS[month - 1].lower(), year), brief['slug'])
check('publication date is the first Thursday',
      brief['published'] == D.first_thursday(year, month).isoformat()
      and date.fromisoformat(brief['published']).weekday() == 3
      and date.fromisoformat(brief['published']).day <= 7,
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


class _Container:
    def __init__(self, cid):
        self.id = cid


class _Msg:
    def __init__(self, stop_reason, blocks, container=None):
        self.stop_reason = stop_reason
        self.content = blocks
        self.container = _Container(container) if container else None


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

# A truncated draft is often still parseable JSON — the model stops mid-document
# and the last complete block reads fine. Reading it would publish half an
# edition, so the budget is checked before the content is.
truncated = _Msg('max_tokens', [_Block(json.dumps({'headline': 'Half an edition'}))])
try:
    run_provider([truncated])
    check('a truncated draft is refused rather than half-published', False)
except SystemExit as e:
    check('a truncated draft is refused rather than half-published',
          'budget' in str(e) and str(D.MAX_TOKENS) in str(e), str(e))

check('the output budget leaves room for thinking as well as prose',
      D.MAX_TOKENS >= 64000 and D.AnthropicProvider().max_tokens == D.MAX_TOKENS,
      '%d' % D.MAX_TOKENS)

# The budget is per request, so a resume starts a fresh one. If it were ever
# carried forward, a long month would fail on the second call rather than the
# first — quietly, and only in production.
_, msgs = run_provider([paused, finished])
check('every request asks for the full budget, including a resume',
      all(c['max_tokens'] == D.MAX_TOKENS for c in msgs.calls),
      str([c['max_tokens'] for c in msgs.calls]))


# The server tools run in a container, and the tool uses a paused turn trails
# are still pending inside it. A resume that does not name it is refused with
# "400 container_id is required when there are pending tool uses" — which is
# how October's fifth attempt ended, one second after a seven-minute search.
held = _Msg('pause_turn', [_Block(kind='server_tool_use')], container='cnt_01abc')

_, msgs = run_provider([held, finished])
check('a resume names the container the paused turn left behind',
      msgs.calls[1].get('container') == 'cnt_01abc', repr(msgs.calls[1].get('container')))
check('the first request does not invent a container',
      'container' not in msgs.calls[0], repr(msgs.calls[0].get('container')))

# Two pauses in a row: the second resume must still carry a container, and the
# newest one wins — a stale id is as useless as none.
moved = _Msg('pause_turn', [_Block(kind='server_tool_use')], container='cnt_02def')
_, msgs = run_provider([held, moved, finished])
check('a second resume carries the newest container, not the first',
      [c.get('container') for c in msgs.calls] == [None, 'cnt_01abc', 'cnt_02def'],
      str([c.get('container') for c in msgs.calls]))

# Not every paused turn allocates one. Sending container=None would be a
# request for a container literally named None, so it must be omitted.
_, msgs = run_provider([paused, finished])
check('a pause with no container omits the parameter rather than sending null',
      'container' not in msgs.calls[1], repr(msgs.calls[1].get('container')))


# ------------------------------------------ the drafter reads its own output back

# Structured outputs cannot express "at least 400 characters" — minLength and
# minItems are not supported — so the schema is physically unable to refuse a
# risks body reading "Placeholder". The model has now shipped exactly that
# twice, with every other field of the edition fully written, and the house
# rule in the system prompt did not stop it either. The only place left to
# catch it is here, before the draft is written.

full = D.StubProvider().research(brief, D.wire_schema(images))
check('a complete draft has nothing to repair', D.stub_fields(full) == {},
      str(sorted(D.stub_fields(full))))

stubbed = json.loads(json.dumps(full))
stubbed['risks'][0]['body'] = 'Placeholder'
stubbed['risks'][0]['sources'] = []
found = D.stub_fields(stubbed)
check('a placeholder risks body is caught', 'risks' in found, str(sorted(found)))
check('and so is the missing citation underneath it',
      any('cites no source' in m for m in found.get('risks', [])),
      str(found.get('risks')))
check('a stub in one field does not implicate the others',
      sorted(found) == ['risks'], str(sorted(found)))

# "TBD" is a placeholder; a real short sentence is not — the length rule is what
# separates them, and it must not fire on prose that is merely concise.
check('an ordinary paragraph is not mistaken for a stub',
      'from_the_desk' not in D.stub_fields(full))

# The repair asks only for the fields that failed, so a good indicators array is
# not regenerated (and cannot be made worse) by a bad risks array.
narrowed = D.subset_schema(D.wire_schema(images), ['risks'])
check('the repair request asks only for the fields that failed',
      list(narrowed['properties']) == ['risks'] and narrowed['required'] == ['risks'],
      str(list(narrowed['properties'])))

stub_msg = _Msg('end_turn', [_Block(json.dumps(stubbed))])
good_msg = _Msg('end_turn', [_Block(json.dumps({'risks': full['risks']}))])

out, msgs = run_provider([stub_msg, good_msg])
check('a stubbed field is asked for again rather than accepted',
      len(msgs.calls) == 2 and D.stub_fields(out) == {},
      '%d request(s), %s' % (len(msgs.calls), sorted(D.stub_fields(out))))
check('the repair keeps the fields that were already good',
      out['headline'] == full['headline'] and out['indicators'] == full['indicators'])
check('the repair turn carries the original brief and the paused draft',
      [m['role'] for m in msgs.calls[1]['messages']] == ['user', 'assistant', 'user'],
      str([m['role'] for m in msgs.calls[1]['messages']]))
check('the repair names the unfinished field to the model',
      'risks[0]' in msgs.calls[1]['messages'][2]['content'],
      msgs.calls[1]['messages'][2]['content'][:60])

# Two failed repairs must not throw away the eight minutes of research that
# produced the rest of the edition.
try:
    run_provider([stub_msg, stub_msg, stub_msg])
    check('a draft the model will not finish is still handed back', False)
except D.StubbedDraft as e:
    check('a draft the model will not finish is still handed back',
          e.draft['headline'] == full['headline']
          and any('risks[0]' in m for m in e.problems), str(e.problems))
except SystemExit as e:
    check('a draft the model will not finish is still handed back', False, str(e))


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
