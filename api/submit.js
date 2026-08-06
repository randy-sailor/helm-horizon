/* POST /api/submit — email a "Voices from the Field" outlook to the editor.
   Same-origin only. The recipient is fixed by environment variable, so this
   cannot be used to deliver mail to an arbitrary third party. */

'use strict';

var lib = require('./_lib');

module.exports = async function handler(req, res) {
  if (lib.guard(req, res)) return;

  var body = lib.readBody(req);

  if (lib.clean(body.website, 100)) return lib.json(res, 200, { ok: true });

  var email = lib.clean(body.email, 254).toLowerCase();
  if (!lib.isEmail(email)) {
    return lib.json(res, 400, { error: 'Please enter a valid email address.' });
  }

  var outlook = lib.clean(body.outlook, 8000);
  if (outlook.length < 20) {
    return lib.json(res, 400, { error: 'Please tell us a little more about what you are seeing.' });
  }

  var from = process.env.SUBMIT_FROM;
  var to = process.env.EDITOR_EMAIL;
  if (!from || !to) {
    console.error('SUBMIT_FROM or EDITOR_EMAIL is not set');
    return lib.json(res, 500, { error: 'Submissions are not configured yet.' });
  }

  var name = lib.clean(body.name, 120) || '(no name given)';
  var lines = [
    'Name: ' + name,
    'Email: ' + email,
    'Company and role: ' + (lib.clean(body.company_role, 200) || '—'),
    'Market or region: ' + (lib.clean(body.region, 200) || '—'),
    'Permission to quote: ' + (lib.clean(body.permission_to_quote, 60) || '—'),
    '',
    'Outlook:',
    outlook
  ];

  try {
    /* Plain text only: the body is reader-supplied and never interpolated
       into HTML. reply_to is validated above, so it cannot inject headers. */
    var r = await lib.resend('/emails', {
      from: from,
      to: [to],
      reply_to: email,
      subject: 'Voices from the Field — submission from ' + name,
      text: lines.join('\n')
    });

    if (!r.ok) {
      console.error('Resend send error', r.status, JSON.stringify(r.body));
      return lib.json(res, 502, {
        error: 'We could not send that. Please email randy@waltongroup.net directly.'
      });
    }
    return lib.json(res, 200, { ok: true });
  } catch (err) {
    console.error('submit failed', err && err.message);
    return lib.json(res, 500, {
      error: 'We could not send that. Please email randy@waltongroup.net directly.'
    });
  }
};
