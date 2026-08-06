/* POST /api/subscribe — add a reader as a Resend contact.
   Same-origin only. Requires RESEND_API_KEY. RESEND_SEGMENT_ID is optional. */

'use strict';

var lib = require('./_lib');

module.exports = async function handler(req, res) {
  if (lib.guard(req, res)) return;

  var body = lib.readBody(req);

  /* Honeypot: the "website" field is hidden from humans by CSS. Anything
     that fills it is a bot. Return 200 so it does not learn otherwise. */
  if (lib.clean(body.website, 100)) return lib.json(res, 200, { ok: true });

  var email = lib.clean(body.email, 254).toLowerCase();
  if (!lib.isEmail(email)) {
    return lib.json(res, 400, { error: 'Please enter a valid email address.' });
  }

  if (!process.env.RESEND_API_KEY) {
    console.error('RESEND_API_KEY is not set');
    return lib.json(res, 500, { error: 'Subscriptions are not configured yet.' });
  }

  /* Resend contacts carry first/last name, so split the single name field
     on the first space and keep the remainder as the surname. */
  var name = lib.clean(body.name, 120);
  var space = name.indexOf(' ');
  var first = space === -1 ? name : name.slice(0, space);
  var last = space === -1 ? '' : name.slice(space + 1);

  /* Contacts are global in Resend's current model — no audience needed.
     Role and company become custom contact properties, which makes them
     usable for segmenting and personalising a Broadcast. */
  var payload = {
    email: email,
    first_name: first,
    last_name: last,
    unsubscribed: false
  };

  var role = lib.clean(body.role, 60);
  var company = lib.clean(body.company, 120);
  if (role || company) {
    payload.properties = {};
    if (role) payload.properties.role = role;
    if (company) payload.properties.company = company;
  }

  /* Optional. Set RESEND_SEGMENT_ID to file new readers into a segment;
     leave it unset and they are simply global contacts. */
  var segment = process.env.RESEND_SEGMENT_ID;
  if (segment) payload.segments = [{ id: segment }];

  try {
    var r = await lib.resend('/contacts', payload);

    /* An address already on the list is a success from the reader's point
       of view, and saying so would disclose who is subscribed. */
    if (!r.ok && r.status !== 409) {
      console.error('Resend contacts error', r.status, JSON.stringify(r.body));
      /* Creating a contact is not a send, so a sending_access key cannot do
         it — the single most likely cause of a rejection here. Say so in the
         logs rather than leaving it to be inferred from a bare 401. */
      if (r.status === 401 || r.status === 403) {
        console.error(
          'Resend rejected the API key for POST /contacts. Creating contacts ' +
            'requires a full_access key; sending_access can only send emails.'
        );
      }
      return lib.json(res, 502, {
        error: 'We could not add you just now. Please email editor@thehelmandhorizon.com.'
      });
    }

    return lib.json(res, 200, { ok: true });
  } catch (err) {
    console.error('subscribe failed', err && err.message);
    return lib.json(res, 500, {
      error: 'We could not add you just now. Please email editor@thehelmandhorizon.com.'
    });
  }
};
