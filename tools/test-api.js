/* Prove the API routes reject what they are supposed to reject.
 *
 *     node tools/test-api.js
 *
 * No dependencies and no network: fetch and the Resend calls are stubbed, so
 * this runs anywhere the site does. The three things it is really watching:
 * a scripted caller with no Origin, an unbounded stream of outbound email, and
 * a reply that answers "is this address on the list?" for anyone who asks.
 */

'use strict';

var assert = require('assert');
var path = require('path');

process.env.RESEND_API_KEY = 'test-key';
process.env.MAIL_FROM = 'Helm & Horizon <hello@thehelmandhorizon.com>';
process.env.SUBMIT_FROM = 'Helm & Horizon <hello@thehelmandhorizon.com>';
process.env.EDITOR_EMAIL = 'editor@thehelmandhorizon.com';

var lib = require(path.join('..', 'api', '_lib.js'));
var subscribe = require(path.join('..', 'api', 'subscribe.js'));
var submit = require(path.join('..', 'api', 'submit.js'));

var HOST = 'thehelmandhorizon.com';
var passed = 0;
var failures = [];

function check(desc, fn) {
  return Promise.resolve()
    .then(fn)
    .then(function () {
      passed++;
      console.log('PASS  ' + desc);
    })
    .catch(function (e) {
      failures.push(desc);
      console.log('FAIL  ' + desc + '\n        ' + (e && e.message));
    });
}

/* ------------------------------------------------------------------ harness */

function req(over) {
  var r = {
    method: 'POST',
    headers: {
      host: HOST,
      origin: 'https://' + HOST,
      'x-forwarded-for': '203.0.113.9'
    },
    body: { email: 'reader@example.com', name: 'A Reader' }
  };
  Object.keys(over || {}).forEach(function (k) {
    if (k === 'headers') {
      Object.keys(over.headers).forEach(function (h) {
        if (over.headers[h] === undefined) delete r.headers[h];
        else r.headers[h] = over.headers[h];
      });
    } else {
      r[k] = over[k];
    }
  });
  return r;
}

function res() {
  var out = { headers: {}, code: 0, payload: null };
  out.setHeader = function (k, v) { out.headers[k.toLowerCase()] = v; };
  out.status = function (c) { out.code = c; return out; };
  out.send = function (s) { out.payload = JSON.parse(s); return out; };
  return out;
}

/* Records every outbound call and answers with whatever the test wants. */
var sent;
function stubFetch(reply) {
  sent = [];
  global.fetch = function (url, opts) {
    var parsed = {};
    if (opts && typeof opts.body === 'string') {
      try { parsed = JSON.parse(opts.body); } catch (e) { parsed = {}; }
    }
    var call = { url: url, method: (opts && opts.method) || 'GET', body: parsed };
    sent.push(call);
    var r = reply(call) || {};
    return Promise.resolve({
      ok: r.ok !== false,
      status: r.status || 200,
      text: function () { return Promise.resolve(JSON.stringify(r.body || {})); }
    });
  };
}

/* A contact the account has never seen. */
function unknownContact(call) {
  if (call.method === 'GET') return { ok: false, status: 404, body: {} };
  return { ok: true, status: 200, body: { id: 'c_1' } };
}

/* A contact that has already confirmed. */
function confirmedContact(call) {
  if (call.method === 'GET') {
    return { ok: true, status: 200, body: { id: 'c_1', unsubscribed: false } };
  }
  return { ok: true, status: 200, body: { id: 'c_1' } };
}

function run(handler, request) {
  var r = res();
  return Promise.resolve(handler(request, r)).then(function () { return r; });
}

/* ------------------------------------------------------- the same-origin gate */

var tests = [];

tests.push(function () {
  return check('a scripted caller with no Origin and no Referer is refused', function () {
    lib.resetRateLimit();
    stubFetch(unknownContact);
    return run(subscribe, req({ headers: { origin: undefined } })).then(function (r) {
      assert.strictEqual(r.code, 403, 'expected 403, got ' + r.code);
      assert.strictEqual(sent.length, 0, 'it must not reach Resend');
    });
  });
});

tests.push(function () {
  return check('a cross-origin Origin is refused', function () {
    lib.resetRateLimit();
    stubFetch(unknownContact);
    return run(subscribe, req({ headers: { origin: 'https://evil.example' } })).then(function (r) {
      assert.strictEqual(r.code, 403);
      assert.strictEqual(sent.length, 0);
    });
  });
});

tests.push(function () {
  return check('Referer stands in when a proxy has stripped Origin', function () {
    lib.resetRateLimit();
    stubFetch(unknownContact);
    return run(subscribe, req({
      headers: { origin: undefined, referer: 'https://' + HOST + '/subscribe' }
    })).then(function (r) {
      assert.strictEqual(r.code, 200, 'expected 200, got ' + r.code);
    });
  });
});

tests.push(function () {
  return check('a cross-site Sec-Fetch-Site is refused even with a matching Origin', function () {
    lib.resetRateLimit();
    stubFetch(unknownContact);
    return run(subscribe, req({ headers: { 'sec-fetch-site': 'cross-site' } })).then(function (r) {
      assert.strictEqual(r.code, 403);
    });
  });
});

tests.push(function () {
  return check('the site\'s own form still works', function () {
    lib.resetRateLimit();
    stubFetch(unknownContact);
    return run(subscribe, req({ headers: { 'sec-fetch-site': 'same-origin' } })).then(function (r) {
      assert.strictEqual(r.code, 200, JSON.stringify(r.payload));
      assert.ok(/check your inbox/i.test(r.payload.message), r.payload.message);
    });
  });
});

tests.push(function () {
  return check('x-forwarded-host is honoured, so preview deployments work', function () {
    lib.resetRateLimit();
    stubFetch(unknownContact);
    return run(subscribe, req({
      headers: {
        'x-forwarded-host': 'helm-horizon-abc123.vercel.app',
        origin: 'https://helm-horizon-abc123.vercel.app'
      }
    })).then(function (r) {
      assert.strictEqual(r.code, 200, JSON.stringify(r.payload));
    });
  });
});

tests.push(function () {
  return check('GET is still refused before anything else runs', function () {
    lib.resetRateLimit();
    stubFetch(unknownContact);
    return run(subscribe, req({ method: 'GET' })).then(function (r) {
      assert.strictEqual(r.code, 405);
      assert.strictEqual(r.headers.allow, 'POST');
    });
  });
});

/* ----------------------------------------------------------- the rate ceiling */

tests.push(function () {
  return check('the sixth signup in the window is refused with Retry-After', function () {
    lib.resetRateLimit();
    stubFetch(unknownContact);
    var chain = Promise.resolve();
    var codes = [];
    for (var i = 0; i < 6; i++) {
      chain = chain.then(function () {
        return run(subscribe, req()).then(function (r) {
          codes.push(r.code);
          return r;
        });
      });
    }
    return chain.then(function (last) {
      assert.deepStrictEqual(codes, [200, 200, 200, 200, 200, 429], codes.join(','));
      assert.ok(Number(last.headers['retry-after']) > 0, 'Retry-After must be set');
    });
  });
});

tests.push(function () {
  return check('the ceiling is per address, not global', function () {
    lib.resetRateLimit();
    stubFetch(unknownContact);
    var chain = Promise.resolve();
    for (var i = 0; i < 5; i++) {
      chain = chain.then(function () { return run(subscribe, req()); });
    }
    return chain
      .then(function () {
        return run(subscribe, req({ headers: { 'x-forwarded-for': '198.51.100.4' } }));
      })
      .then(function (r) {
        assert.strictEqual(r.code, 200, 'a different caller must not be punished');
      });
  });
});

tests.push(function () {
  return check('submissions to the editor have a tighter ceiling of three', function () {
    lib.resetRateLimit();
    stubFetch(function () { return { ok: true, status: 200, body: { id: 'e_1' } }; });
    var body = {
      email: 'reader@example.com',
      name: 'A Reader',
      outlook: 'Charter enquiries in the western Med are down about a fifth on last year.'
    };
    var chain = Promise.resolve();
    var codes = [];
    for (var i = 0; i < 4; i++) {
      chain = chain.then(function () {
        return run(submit, req({ body: body })).then(function (r) { codes.push(r.code); });
      });
    }
    return chain.then(function () {
      assert.deepStrictEqual(codes, [200, 200, 200, 429], codes.join(','));
    });
  });
});

tests.push(function () {
  return check('a refused request sends no email at all', function () {
    lib.resetRateLimit();
    stubFetch(unknownContact);
    var chain = Promise.resolve();
    for (var i = 0; i < 5; i++) {
      chain = chain.then(function () { return run(subscribe, req()); });
    }
    return chain.then(function () {
      var before = sent.length;
      return run(subscribe, req()).then(function (r) {
        assert.strictEqual(r.code, 429);
        assert.strictEqual(sent.length, before, 'the blocked call must not reach Resend');
      });
    });
  });
});

/* -------------------------------------------------------- subscriber privacy */

tests.push(function () {
  return check('a known address and an unknown one get the identical reply', function () {
    lib.resetRateLimit();
    stubFetch(unknownContact);
    return run(subscribe, req()).then(function (a) {
      lib.resetRateLimit();
      stubFetch(confirmedContact);
      return run(subscribe, req()).then(function (b) {
        assert.strictEqual(a.code, b.code, a.code + ' vs ' + b.code);
        assert.deepStrictEqual(a.payload, b.payload,
          JSON.stringify(a.payload) + ' vs ' + JSON.stringify(b.payload));
      });
    });
  });
});

tests.push(function () {
  return check('no reply anywhere says an address is already subscribed', function () {
    lib.resetRateLimit();
    stubFetch(confirmedContact);
    return run(subscribe, req()).then(function (r) {
      var text = JSON.stringify(r.payload).toLowerCase();
      assert.ok(!/already/.test(text), 'leaked: ' + text);
      assert.ok(!/on the list/.test(text), 'leaked: ' + text);
    });
  });
});

tests.push(function () {
  return check('a confirmed contact is never rewritten, so it cannot be reset', function () {
    lib.resetRateLimit();
    stubFetch(confirmedContact);
    return run(subscribe, req()).then(function () {
      var writes = sent.filter(function (c) {
        return c.method === 'POST' && /\/contacts$/.test(c.url);
      });
      assert.strictEqual(writes.length, 0,
        'wrote to /contacts for an already-confirmed reader: ' + JSON.stringify(writes));
    });
  });
});

tests.push(function () {
  return check('both cases take the same path, so timing tells nothing either', function () {
    lib.resetRateLimit();
    stubFetch(unknownContact);
    return run(subscribe, req()).then(function () {
      var a = sent.filter(function (c) { return /\/emails$/.test(c.url); }).length;
      lib.resetRateLimit();
      stubFetch(confirmedContact);
      return run(subscribe, req()).then(function () {
        var b = sent.filter(function (c) { return /\/emails$/.test(c.url); }).length;
        assert.strictEqual(a, 1, 'a new reader should be emailed once');
        assert.strictEqual(b, 1, 'an existing reader should be emailed once too');
      });
    });
  });
});

/* ------------------------------------------------- what must not have changed */

tests.push(function () {
  return check('new contacts are still created unsubscribed — double opt-in intact', function () {
    lib.resetRateLimit();
    stubFetch(unknownContact);
    return run(subscribe, req()).then(function () {
      var write = sent.filter(function (c) {
        return c.method === 'POST' && /\/contacts$/.test(c.url);
      })[0];
      assert.ok(write, 'no contact was created');
      assert.strictEqual(write.body.unsubscribed, true);
    });
  });
});

tests.push(function () {
  return check('the honeypot still answers 200 and sends nothing', function () {
    lib.resetRateLimit();
    stubFetch(unknownContact);
    return run(subscribe, req({
      body: { email: 'bot@example.com', website: 'http://spam.example' }
    })).then(function (r) {
      assert.strictEqual(r.code, 200);
      assert.strictEqual(sent.length, 0);
    });
  });
});

tests.push(function () {
  return check('a malformed address is still refused', function () {
    lib.resetRateLimit();
    stubFetch(unknownContact);
    return run(subscribe, req({ body: { email: 'not-an-address' } })).then(function (r) {
      assert.strictEqual(r.code, 400);
      assert.strictEqual(sent.length, 0);
    });
  });
});

tests.push(function () {
  return check('control characters are still stripped out of header-bound fields', function () {
    assert.strictEqual(lib.clean('A\r\nBcc: victim@example.com', 200),
      'A  Bcc: victim@example.com');
  });
});

tests.push(function () {
  return check('a confirmation link still cannot be edited to confirm someone else', function () {
    var exp = Math.floor(Date.now() / 1000) + 3600;
    var sig = lib.signConfirm('reader@example.com', exp);
    assert.ok(lib.verifyConfirm('reader@example.com', exp, sig));
    assert.ok(!lib.verifyConfirm('someone@example.com', exp, sig));
    assert.ok(!lib.verifyConfirm('reader@example.com', exp + 1, sig));
  });
});

/* ------------------------------------------------------------ canonical host */

tests.push(function () {
  return check('every page declares the same canonical host', function () {
    var fs = require('fs');
    var root = path.join(__dirname, '..');
    var pages = fs.readdirSync(root).filter(function (f) { return /\.html$/.test(f); });
    var editions = path.join(root, 'editions');
    if (fs.existsSync(editions)) {
      fs.readdirSync(editions).forEach(function (f) {
        if (/\.html$/.test(f)) pages.push(path.join('editions', f));
      });
    }
    var hosts = {};
    pages.forEach(function (rel) {
      var html = fs.readFileSync(path.join(root, rel), 'utf8');
      var re = /(?:rel="canonical" href|property="og:url" content)="https:\/\/([^/"]+)/g;
      var m;
      while ((m = re.exec(html))) (hosts[m[1]] = hosts[m[1]] || []).push(rel);
    });
    var found = Object.keys(hosts);
    assert.strictEqual(found.length, 1,
      'canonical URLs disagree on the host: ' + JSON.stringify(hosts));
    assert.strictEqual(found[0], HOST,
      'canonical host is ' + found[0] + ', expected the apex ' + HOST);

    var sitemap = fs.readFileSync(path.join(root, 'sitemap.xml'), 'utf8');
    var bad = (sitemap.match(/<loc>https:\/\/(?!thehelmandhorizon\.com)[^<]*/g) || []);
    assert.strictEqual(bad.length, 0, 'sitemap disagrees: ' + bad.join(', '));
  });
});

/* -------------------------------------------------------------------- runner */

tests
  .reduce(function (chain, t) { return chain.then(t); }, Promise.resolve())
  .then(function () {
    console.log('\n' + (failures.length
      ? failures.length + ' FAILED: ' + failures.join('; ')
      : passed + ' checks passed'));
    process.exit(failures.length ? 1 : 0);
  });
