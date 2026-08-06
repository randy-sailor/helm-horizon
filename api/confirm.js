/* GET /api/confirm?e=<b64url email>&x=<expiry>&t=<signature>
   Completes double opt-in: verifies the signed link and flips the contact
   from unsubscribed to active. Redirects to a page either way, because this
   is opened by a person clicking a link in an email, not by our own script. */

'use strict';

var lib = require('./_lib');

function redirect(res, path) {
  res.setHeader('Location', path);
  res.setHeader('Cache-Control', 'no-store');
  res.status(302).send('');
}

module.exports = async function handler(req, res) {
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.setHeader('Allow', 'GET');
    return lib.json(res, 405, { error: 'Method not allowed' });
  }

  var q = req.query || {};
  var email = '';
  try {
    email = lib.unb64url(q.e || '').toLowerCase();
  } catch (e) {
    email = '';
  }
  var exp = parseInt(q.x, 10);

  if (!lib.isEmail(email) || !exp || !q.t) {
    return redirect(res, '/confirm-failed');
  }
  if (exp < Math.floor(Date.now() / 1000)) {
    return redirect(res, '/confirm-failed?reason=expired');
  }
  if (!lib.verifyConfirm(email, exp, q.t)) {
    console.error('Confirm link failed signature check');
    return redirect(res, '/confirm-failed');
  }

  try {
    /* Update by email, so no contact id lookup is needed. */
    var r = await lib.resend(
      '/contacts/' + encodeURIComponent(email),
      { unsubscribed: false },
      'PATCH'
    );

    if (!r.ok) {
      console.error('Confirm update failed', r.status, JSON.stringify(r.body));
      return redirect(res, '/confirm-failed');
    }

    return redirect(res, '/confirmed');
  } catch (err) {
    console.error('confirm failed', err && err.message);
    return redirect(res, '/confirm-failed');
  }
};
