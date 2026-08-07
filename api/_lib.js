/* Shared helpers for the Helm & Horizon API routes.
   No dependencies — Vercel's Node runtime provides global fetch. */

'use strict';

var crypto = require('crypto');

var RESEND_API = 'https://api.resend.com';

/* Deliberately permissive. Real validation is the confirmation email; this
   only rejects input that cannot possibly be an address. */
var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function isEmail(v) {
  return typeof v === 'string' && v.length <= 254 && EMAIL_RE.test(v);
}

/* Trim, cap, and strip control characters. Anything bound for an email
   header must not be able to carry CR/LF. */
function clean(v, max) {
  if (typeof v !== 'string') return '';
  return v
    .replace(/[\x00-\x1f\x7f]/g, ' ')
    .trim()
    .slice(0, max || 200);
}

function readBody(req) {
  /* Vercel parses application/json into req.body, but be defensive: a raw
     string body shows up when the content-type is missing or unexpected. */
  var b = req.body;
  if (b == null) return {};
  if (typeof b === 'string') {
    try {
      return JSON.parse(b);
    } catch (e) {
      return {};
    }
  }
  return typeof b === 'object' ? b : {};
}

function json(res, status, payload) {
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.status(status).send(JSON.stringify(payload));
}

/* Same-origin guard. These endpoints are only ever called by our own pages,
   so reject cross-origin callers rather than serving as an open relay.

   A missing Origin used to pass. That exempted exactly the callers worth
   stopping: browsers attach Origin to every POST, so anything arriving without
   one is a script, and both routes send mail. Referer is accepted as a fallback
   because a handful of privacy tools and corporate proxies strip Origin, and
   Sec-Fetch-Site is honoured where the browser sends it.

   This is not a security boundary on its own — headers are trivially forged —
   which is why it is paired with the rate limit below. */
function sameOrigin(req) {
  var host = req.headers['x-forwarded-host'] || req.headers.host || '';
  var site = req.headers['sec-fetch-site'];
  if (site === 'cross-site' || site === 'same-site') return false;

  var stated = req.headers.origin || req.headers.referer;
  if (!stated) return site === 'same-origin' || site === 'none';
  try {
    return new URL(stated).host === host;
  } catch (e) {
    return false;
  }
}

/* ----------------------------------------------------------------------
   Rate limiting.

   Both routes send email through Resend on an unauthenticated request, so
   without a ceiling anyone can burn the sending quota, damage the domain's
   reputation, or point a stream of confirmation mail at someone else's inbox.

   The counters live in module scope, which means per warm instance rather
   than per deployment. That is a speed bump, not a wall: a distributed caller
   spread across enough cold starts still gets through. It is what is
   available without adding a datastore, and it turns a trivial flood into an
   expensive one. If abuse ever justifies the dependency, the replacement is
   Vercel KV or Upstash behind this same function signature.
   ---------------------------------------------------------------------- */

var HITS = new Map();
var WINDOW_MS = 10 * 60 * 1000;
var MAX_KEYS = 5000;

function clientKey(req) {
  var fwd = req.headers['x-forwarded-for'] || '';
  /* The left-most entry is the client; the rest are proxies that appended
     themselves. Vercel sets this, so it is not attacker-controlled here. */
  var ip = String(fwd).split(',')[0].trim();
  return ip || req.headers['x-real-ip'] || 'unknown';
}

function rateLimit(req, limit) {
  var now = Date.now();
  var key = clientKey(req);

  /* Sweep on write rather than on a timer — a serverless instance has no
     reliable background tick, and an unbounded Map is its own denial of
     service. */
  if (HITS.size > MAX_KEYS) {
    HITS.forEach(function (times, k) {
      if (!times.some(function (t) { return now - t < WINDOW_MS; })) HITS.delete(k);
    });
    if (HITS.size > MAX_KEYS) HITS.clear();
  }

  var times = (HITS.get(key) || []).filter(function (t) { return now - t < WINDOW_MS; });
  if (times.length >= limit) {
    var retry = Math.ceil((WINDOW_MS - (now - times[0])) / 1000);
    HITS.set(key, times);
    return retry > 0 ? retry : 1;
  }
  times.push(now);
  HITS.set(key, times);
  return 0;
}

/* Exposed so the tests can start from a known state. */
function resetRateLimit() {
  HITS.clear();
}

function resend(path, body, method) {
  var key = process.env.RESEND_API_KEY;
  if (!key) return Promise.reject(new Error('RESEND_API_KEY is not set'));
  var opts = {
    method: method || 'POST',
    headers: {
      Authorization: 'Bearer ' + key,
      'Content-Type': 'application/json'
    }
  };
  if (body != null) opts.body = JSON.stringify(body);
  return fetch(RESEND_API + path, opts).then(function (r) {
    return r
      .text()
      .then(function (t) {
        var parsed = {};
        try {
          parsed = t ? JSON.parse(t) : {};
        } catch (e) {
          parsed = { raw: t };
        }
        return { ok: r.ok, status: r.status, body: parsed };
      });
  });
}

/* Shared preflight for both routes: method, origin, and rate.
   Returns true when the request has been answered and the caller should stop. */
function guard(req, res, limit) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    json(res, 405, { error: 'Method not allowed' });
    return true;
  }
  if (!sameOrigin(req)) {
    json(res, 403, { error: 'Forbidden' });
    return true;
  }
  var retry = rateLimit(req, limit || 5);
  if (retry) {
    res.setHeader('Retry-After', String(retry));
    json(res, 429, { error: 'Too many requests. Please try again in a few minutes.' });
    return true;
  }
  return false;
}

/* ----------------------------------------------------------------------
   Confirmation links.

   The link carries the address, an expiry, and an HMAC over both, so the
   double opt-in flow needs no database: a link cannot be forged, edited to
   confirm somebody else's address, or replayed after it expires.
   ---------------------------------------------------------------------- */

function b64url(buf) {
  return Buffer.from(buf).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function unb64url(s) {
  var t = String(s).replace(/-/g, '+').replace(/_/g, '/');
  return Buffer.from(t, 'base64').toString('utf8');
}

/* Prefer an explicit CONFIRM_SECRET. Falling back to a value derived from the
   API key keeps this working with no extra configuration, and the derivation
   means the API key itself is never used directly as a signing key. Rotating
   the API key invalidates links that are still in flight, which is an
   acceptable trade for one less secret to manage. */
function confirmSecret() {
  if (process.env.CONFIRM_SECRET) return process.env.CONFIRM_SECRET;
  var key = process.env.RESEND_API_KEY;
  if (!key) return null;
  return crypto.createHmac('sha256', key).update('helm-horizon/confirm/v1').digest('hex');
}

function signConfirm(email, exp) {
  var secret = confirmSecret();
  if (!secret) return null;
  return b64url(crypto.createHmac('sha256', secret).update(email + '.' + exp).digest());
}

function verifyConfirm(email, exp, sig) {
  var expected = signConfirm(email, exp);
  if (!expected || !sig) return false;
  var a = Buffer.from(expected);
  var b = Buffer.from(String(sig));
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}

/* Build the absolute confirm URL from the request, so preview deployments
   produce links that point at themselves rather than at production. */
function confirmUrl(req, email, ttlDays) {
  var exp = Math.floor(Date.now() / 1000) + (ttlDays || 7) * 86400;
  var sig = signConfirm(email, exp);
  if (!sig) return null;
  var host = req.headers['x-forwarded-host'] || req.headers.host || '';
  var proto = req.headers['x-forwarded-proto'] || 'https';
  return (
    proto + '://' + host + '/api/confirm' +
    '?e=' + encodeURIComponent(b64url(email)) +
    '&x=' + exp +
    '&t=' + encodeURIComponent(sig)
  );
}

module.exports = {
  isEmail: isEmail,
  clean: clean,
  readBody: readBody,
  json: json,
  resend: resend,
  guard: guard,
  sameOrigin: sameOrigin,
  rateLimit: rateLimit,
  resetRateLimit: resetRateLimit,
  b64url: b64url,
  unb64url: unb64url,
  signConfirm: signConfirm,
  verifyConfirm: verifyConfirm,
  confirmUrl: confirmUrl
};
