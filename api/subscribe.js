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
  /* Double opt-in: the contact starts unsubscribed and only becomes active
     when the reader clicks the link in the confirmation email. */
  var payload = {
    email: email,
    first_name: first,
    last_name: last,
    unsubscribed: true
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
    /* Look first. Creating a contact that already exists could otherwise flip
       a confirmed subscriber back to unsubscribed — someone re-entering their
       address would quietly remove themselves from the list. */
    var existing = await lib.resend('/contacts/' + encodeURIComponent(email), null, 'GET');
    if (existing.ok && existing.body && existing.body.unsubscribed === false) {
      return lib.json(res, 200, {
        ok: true,
        message: 'You are already on the list. The next issue is on its way.'
      });
    }

    var r = await lib.resend('/contacts', payload);

    /* The custom properties and the segment are enrichment; the subscription
       is the point. A custom property that does not exist on the account, or
       a stale segment id, would otherwise cost us the signup entirely — so if
       the enriched payload is rejected, fall back to the minimum and keep the
       reader. Both attempts are logged so the cause stays visible. */
    if (!r.ok && r.status !== 409 && (payload.properties || payload.segments)) {
      console.error(
        'Enriched contact rejected',
        r.status,
        JSON.stringify(r.body),
        '— retrying without properties/segments'
      );
      r = await lib.resend('/contacts', {
        email: email,
        first_name: first,
        last_name: last,
        unsubscribed: true
      });
      if (r.ok) console.error('Fallback succeeded: contact created without properties/segments');
    }

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

    /* The contact exists but is inert until confirmed. Send the link. */
    var url = lib.confirmUrl(req, email, 7);
    var from = process.env.MAIL_FROM || process.env.SUBMIT_FROM;
    if (!url || !from) {
      console.error('MAIL_FROM/SUBMIT_FROM missing, or the confirm link could not be signed');
      return lib.json(res, 500, {
        error: 'We could not send your confirmation email. Please email editor@thehelmandhorizon.com.'
      });
    }

    var mail = await lib.resend('/emails', {
      from: from,
      to: [email],
      subject: 'Confirm your Helm & Horizon subscription',
      text:
        'Thanks for subscribing to Helm & Horizon.\n\n' +
        'Confirm your subscription by opening this link:\n\n' +
        url +
        '\n\nThe link is valid for seven days. If you did not request this, ' +
        'ignore this email — no issues will be sent unless you confirm.\n\n' +
        'Helm & Horizon — a monthly market briefing for yacht industry leaders.\n' +
        'Published by The Walton Group, Inc.\n'
    });

    if (!mail.ok) {
      console.error('Confirmation email failed', mail.status, JSON.stringify(mail.body));
      return lib.json(res, 502, {
        error: 'We could not send your confirmation email. Please email editor@thehelmandhorizon.com.'
      });
    }

    return lib.json(res, 200, {
      ok: true,
      message: 'Almost there. Check your inbox and click the link to confirm.'
    });
  } catch (err) {
    console.error('subscribe failed', err && err.message);
    return lib.json(res, 500, {
      error: 'We could not add you just now. Please email editor@thehelmandhorizon.com.'
    });
  }
};
