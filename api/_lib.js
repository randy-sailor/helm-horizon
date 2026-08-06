/* Shared helpers for the Helm & Horizon API routes.
   No dependencies — Vercel's Node runtime provides global fetch. */

'use strict';

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
   so reject cross-origin callers rather than serving as an open relay. */
function sameOrigin(req) {
  var origin = req.headers.origin;
  if (!origin) return true; /* non-CORS clients send no Origin */
  var host = req.headers['x-forwarded-host'] || req.headers.host || '';
  try {
    return new URL(origin).host === host;
  } catch (e) {
    return false;
  }
}

function resend(path, body) {
  var key = process.env.RESEND_API_KEY;
  if (!key) return Promise.reject(new Error('RESEND_API_KEY is not set'));
  return fetch(RESEND_API + path, {
    method: 'POST',
    headers: {
      Authorization: 'Bearer ' + key,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  }).then(function (r) {
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

/* Shared preflight for both routes: method, origin, and payload shape.
   Returns null when the request is fine, or a handled-response marker. */
function guard(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    json(res, 405, { error: 'Method not allowed' });
    return true;
  }
  if (!sameOrigin(req)) {
    json(res, 403, { error: 'Forbidden' });
    return true;
  }
  return false;
}

module.exports = { isEmail: isEmail, clean: clean, readBody: readBody, json: json, resend: resend, guard: guard };
