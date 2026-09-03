#!/usr/bin/env python3
"""Validate an edition JSON file against the schema and the editorial standard.

    python3 tools/validate_edition.py                          # every edition
    python3 tools/validate_edition.py content/editions/x.json   # one
    python3 tools/validate_edition.py --offline                 # skip URL liveness

Exits non-zero with a readable message on any violation. The point is that
"every figure is cited to a primary source" stops being a matter of discipline
and becomes something a machine refuses to let past.

No third-party dependencies: checks are hand-rolled rather than jsonschema so
the failure messages name the field and say what is wrong with it.
"""

import argparse
import concurrent.futures
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

EDITIONS_DIR = os.path.join('content', 'editions')
REGIONS = ('us', 'global')

# [label](url) inside body prose — citations are inline, so they must be
# checked too, not only the ones in structured fields.
MD_LINK = re.compile(r'\[([^\]]*)\]\((https?://[^)\s]+)\)')

USER_AGENT = 'helm-horizon-link-check/1.0 (+https://thehelmandhorizon.com)'

# Reserved names from RFC 2606 and RFC 6761, plus the usual local hosts. A
# citation pointing at one of these is a placeholder nobody replaced — and
# example.com answers 200, so the liveness check will never catch it.
RESERVED_HOST = re.compile(
    r'^(?:.+\.)?example\.(?:com|org|net|edu)$|^(?:.+\.)?(?:test|invalid|localhost)$'
    r'|^127\.0\.0\.1$|^::1$', re.I)

# Text that is *only* one of these is a stub, not prose. Matched against the
# whole field so a paragraph that merely uses the word is left alone.
PLACEHOLDER = re.compile(
    r'^\s*(?:placeholder|placeholder text|tbd|to be (?:determined|written|added)|todo|'
    r'n/?a|none|null|xxx+|\.\.\.|lorem ipsum.*|coming soon|text here|sample text|'
    r'insert .*here)\s*[.!]?\s*$', re.I)

# Below this a "risk assessment" or "action step" is a stub. September's run
# 400-900; the October draft that prompted this rule was eleven characters.
MIN_BODY = 80


class Problems:
    def __init__(self, path):
        self.path = path
        self.items = []

    def add(self, where, msg):
        self.items.append((where, msg))

    def __bool__(self):
        return bool(self.items)


# --------------------------------------------------------------- type helpers

def _is_str(v):
    return isinstance(v, str) and v.strip() != ''


def _req(p, obj, key, kind, where):
    """Require a field, return it, or record the problem and return None."""
    if key not in obj or obj[key] is None:
        p.add(where, 'missing required field "%s"' % key)
        return None
    v = obj[key]
    if kind == 'str' and not _is_str(v):
        p.add(where, '"%s" must be a non-empty string' % key)
        return None
    if kind == 'int' and not isinstance(v, int):
        p.add(where, '"%s" must be an integer' % key)
        return None
    if kind == 'list' and not isinstance(v, list):
        p.add(where, '"%s" must be a list' % key)
        return None
    if kind == 'dict' and not isinstance(v, dict):
        p.add(where, '"%s" must be an object' % key)
        return None
    return v


def _check_source(p, src, where):
    """A source must exist, name itself, and carry an https URL."""
    if not isinstance(src, dict):
        p.add(where, 'missing source — every figure must cite a primary source')
        return None
    url = src.get('url')
    if not _is_str(url):
        p.add(where, 'source has no url — every figure must cite a primary source')
        return None
    if not url.startswith('https://'):
        p.add(where, 'source url is not https: %s' % url)
        return None
    host = urllib.parse.urlsplit(url).hostname or ''
    if RESERVED_HOST.match(host):
        p.add(where, 'source url is a reserved example domain, not a citation: %s' % url)
        return None
    if not _is_str(src.get('title')):
        p.add(where, 'source has no title')
    return url


# ------------------------------------------------------------------ structure

def validate_structure(p, ed):
    for key in ('volume', 'number'):
        _req(p, ed, key, 'int', 'edition')
    for key in ('month', 'slug', 'published', 'headline', 'dek'):
        _req(p, ed, key, 'str', 'edition')

    slug = ed.get('slug')
    if _is_str(slug) and not re.fullmatch(r'[a-z]+-\d{4}', slug):
        p.add('edition', 'slug should look like "october-2026", got "%s"' % slug)

    published = ed.get('published')
    if _is_str(published) and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', published):
        p.add('edition', 'published should be an ISO date (YYYY-MM-DD), got "%s"' % published)

    desk = _req(p, ed, 'from_the_desk', 'list', 'edition')
    if isinstance(desk, list) and not all(_is_str(x) for x in desk):
        p.add('from_the_desk', 'every paragraph must be a non-empty string')
    if isinstance(desk, list) and not desk:
        p.add('from_the_desk', 'must have at least one paragraph')

    feat = _req(p, ed, 'featured', 'dict', 'edition')
    if isinstance(feat, dict):
        _req(p, feat, 'title', 'str', 'featured')
        secs = _req(p, feat, 'sections', 'list', 'featured')
        for i, s in enumerate(secs or []):
            where = 'featured.sections[%d]' % i
            if not isinstance(s, dict):
                p.add(where, 'must be an object')
                continue
            if 'figure' in s:
                fig = s['figure']
                if not isinstance(fig, dict) or not _is_str(fig.get('image')):
                    p.add(where, 'figure needs an image path')
                elif not _is_str(fig.get('alt')):
                    p.add(where, 'figure needs alt text')
            else:
                if not _is_str(s.get('heading')):
                    p.add(where, 'needs a heading (or a figure)')
                if not isinstance(s.get('body'), list) or not s.get('body'):
                    p.add(where, 'needs a non-empty body list')

    inds = _req(p, ed, 'indicators', 'list', 'edition')
    for i, ind in enumerate(inds or []):
        where = 'indicators[%d] (%s)' % (i, (ind or {}).get('label', '?') if isinstance(ind, dict) else '?')
        if not isinstance(ind, dict):
            p.add(where, 'must be an object')
            continue
        if ind.get('region') not in REGIONS:
            p.add(where, 'region must be one of %s' % (REGIONS,))
        for k in ('label', 'value'):
            if not _is_str(ind.get(k)):
                p.add(where, 'missing "%s"' % k)
        _check_source(p, ind.get('source'), where)

    risks = _req(p, ed, 'risks', 'list', 'edition')
    for i, r in enumerate(risks or []):
        where = 'risks[%d] (%s)' % (i, (r or {}).get('title', '?') if isinstance(r, dict) else '?')
        if not isinstance(r, dict):
            p.add(where, 'must be an object')
            continue
        if r.get('region') not in REGIONS:
            p.add(where, 'region must be one of %s' % (REGIONS,))
        for k in ('title', 'body'):
            if not _is_str(r.get(k)):
                p.add(where, 'missing "%s"' % k)
        srcs = r.get('sources')
        if not isinstance(srcs, list) or not srcs:
            p.add(where, 'must cite at least one source')
        else:
            for j, s in enumerate(srcs):
                _check_source(p, s, where + '.sources[%d]' % j)

    actions = _req(p, ed, 'actions', 'list', 'edition')
    if isinstance(actions, list) and len(actions) != 3:
        p.add('actions', 'must contain exactly 3 steps, found %d' % len(actions))
    for i, a in enumerate(actions or []):
        where = 'actions[%d]' % i
        if not isinstance(a, dict):
            p.add(where, 'must be an object')
            continue
        for k in ('title', 'body'):
            if not _is_str(a.get(k)):
                p.add(where, 'missing "%s"' % k)

    prof = _req(p, ed, 'profile', 'dict', 'edition')
    if isinstance(prof, dict):
        _req(p, prof, 'company', 'str', 'profile')
        secs = _req(p, prof, 'sections', 'list', 'profile')
        if isinstance(secs, list) and not secs:
            p.add('profile', 'needs at least one section')

    voices = ed.get('voices')
    if voices is None or not isinstance(voices, list):
        p.add('voices', 'must be a list (empty is fine)')
    else:
        for i, v in enumerate(voices):
            where = 'voices[%d]' % i
            if not isinstance(v, dict):
                p.add(where, 'must be an object')
                continue
            # Off-record commentary must never reach publication through an
            # omission, so a missing flag is a failure, not a default.
            if v.get('permission_to_quote') is not True:
                p.add(where, 'permission_to_quote is not true — this quote must not be published')
            for k in ('quote', 'attribution'):
                if not _is_str(v.get(k)):
                    p.add(where, 'missing "%s"' % k)


def validate_prose(p, ed):
    """Refuse stub text that satisfies every structural rule.

    October's first real draft passed everything and still carried two risk
    panels reading "Placeholder", cited to example.com. Each rule was met: a
    non-empty string, an https URL, and a domain that answers 200. Structure
    was never what was wrong with it.
    """
    def walk(node, path):
        if isinstance(node, str):
            if PLACEHOLDER.match(node):
                p.add(path, 'placeholder text left in place: %r' % node.strip()[:40])
        elif isinstance(node, dict):
            for k, v in node.items():
                if k != 'url':          # urls have their own rule
                    walk(v, '%s.%s' % (path, k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, '%s[%d]' % (path, i))

    walk(ed, 'edition')

    # A floor, not a word count: enough to catch a stub, far under real prose.
    for field in ('risks', 'actions'):
        for i, item in enumerate(ed.get(field) or []):
            body = (item or {}).get('body') if isinstance(item, dict) else None
            if _is_str(body) and len(body.strip()) < MIN_BODY:
                p.add('%s[%d]' % (field, i),
                      'body is %d characters — too short to be real'
                      % len(body.strip()))


def validate_sequence(p, ed, path, editions_dir=EDITIONS_DIR):
    """Edition numbers must be unique across the archive and leave no gaps.

    The rule was "exactly one greater than the highest other edition", which is
    right for a draft joining the archive and wrong for every issue already in
    it. The day October landed, re-validating September asked why number 9 was
    not 11 — and `validate_edition.py` with no arguments checks every edition,
    so the whole archive went red as soon as a second issue existed.

    Uniqueness plus contiguity keeps what the old rule was for: a draft
    numbered 9 collides, a draft numbered 12 leaves a gap, and only 11 passes.

    The archive to sequence against is a parameter, not a constant: an edition
    is only in or out of sequence relative to some set of editions, and the
    fixtures need to state their own. Pinning this to the live directory made
    the fixture tests fail the moment a new edition landed on disk.
    """
    others = {}
    for name in sorted(os.listdir(editions_dir)) if os.path.isdir(editions_dir) else []:
        if not name.endswith('.json'):
            continue
        full = os.path.join(editions_dir, name)
        if os.path.abspath(full) == os.path.abspath(path):
            continue
        try:
            other = json.load(open(full, encoding='utf-8'))
        except Exception:
            continue
        n = other.get('number')
        if isinstance(n, int):
            others.setdefault(n, name)

    n = ed.get('number')
    if not isinstance(n, int) or not others:
        return  # first edition in the repo; nothing to sequence against
    if n in others:
        p.add('edition', 'number %d is already taken by %s' % (n, others[n]))
        return
    numbers = sorted(list(others) + [n])
    if numbers != list(range(numbers[0], numbers[0] + len(numbers))):
        highest = max(others)
        p.add('edition', 'number %d leaves a gap in the archive — the highest other '
                         'edition is %d, so the next one is expected to be %d'
              % (n, highest, highest + 1))


# ----------------------------------------------------------------- URL checks

def collect_urls(ed):
    """Every URL in the edition: structured sources and inline prose links."""
    urls = set()

    def walk(node):
        if isinstance(node, str):
            for _, u in MD_LINK.findall(node):
                urls.add(u)
        elif isinstance(node, dict):
            if 'url' in node and isinstance(node['url'], str):
                urls.add(node['url'])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(ed)
    return sorted(urls)


def check_url(url, timeout=15):
    """Return None if reachable, else a reason.

    Publishers frequently block HEAD, so 403/405 count as reachable — the
    point is to catch dead links, not to audit access control. Only 404/410
    and DNS failure are treated as broken.
    """
    req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': USER_AGENT})
    try:
        urllib.request.urlopen(req, timeout=timeout)
        return None
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return 'HTTP %d' % e.code
        if e.code in (403, 405, 401, 429):
            return None
        # Anything else: retry once with GET before judging.
        try:
            urllib.request.urlopen(
                urllib.request.Request(url, headers={'User-Agent': USER_AGENT}), timeout=timeout)
            return None
        except urllib.error.HTTPError as e2:
            return 'HTTP %d' % e2.code if e2.code in (404, 410) else None
        except Exception:
            return None
    except urllib.error.URLError as e:
        reason = str(getattr(e, 'reason', e))
        if 'Name or service not known' in reason or 'nodename nor servname' in reason:
            return 'DNS failure'
        # Timeouts, TLS trouble, proxy refusals: not evidence the link is dead.
        return None
    except Exception:
        return None


def validate_links(p, ed, workers=8):
    urls = collect_urls(ed)
    if not urls:
        return
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for url, reason in zip(urls, pool.map(check_url, urls)):
            if reason:
                p.add('links', '%s — %s' % (reason, url))


# ------------------------------------------------------------------- reporting

def validate(path, offline=False, editions_dir=EDITIONS_DIR):
    p = Problems(path)
    try:
        ed = json.load(open(path, encoding='utf-8'))
    except json.JSONDecodeError as e:
        p.add('file', 'invalid JSON: %s' % e)
        return p
    except FileNotFoundError:
        p.add('file', 'not found')
        return p

    validate_structure(p, ed)
    validate_prose(p, ed)
    validate_sequence(p, ed, path, editions_dir)
    if not offline:
        validate_links(p, ed)
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paths', nargs='*', help='edition JSON files (default: all)')
    ap.add_argument('--offline', action='store_true',
                    help='skip the URL liveness check')
    args = ap.parse_args()

    paths = args.paths
    if not paths:
        if not os.path.isdir(EDITIONS_DIR):
            print('no %s directory' % EDITIONS_DIR, file=sys.stderr)
            return 1
        paths = [os.path.join(EDITIONS_DIR, n)
                 for n in sorted(os.listdir(EDITIONS_DIR)) if n.endswith('.json')]
    if not paths:
        print('no editions to validate', file=sys.stderr)
        return 1

    failed = 0
    for path in paths:
        p = validate(path, offline=args.offline)
        if p:
            failed += 1
            print('FAIL %s' % path)
            for where, msg in p.items:
                print('   %-42s %s' % (where, msg))
        else:
            print('ok   %s' % path)

    if failed:
        print('\n%d edition(s) failed validation' % failed, file=sys.stderr)
        return 1
    print('\nall editions valid')
    return 0


if __name__ == '__main__':
    sys.exit(main())
