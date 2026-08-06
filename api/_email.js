/* Branded email templates.

   Email HTML is not web HTML: no flexbox, no grid, no external stylesheet,
   no web fonts worth relying on. Layout is tables, styling is inline, and the
   palette is the site's own tokens hard-coded because custom properties do
   not survive most clients.

   The masthead is typographic rather than an image. Remote images are blocked
   by default in Outlook and often in Gmail, and a wordmark that always renders
   looks more deliberate than a broken image placeholder. */

'use strict';

var NAVY_DEEP = '#06192e';
var NAVY = '#0b2a4a';
var GOLD = '#c9a55a';
var PAPER = '#f7f5f0';
var INK = '#14202c';
var INK_SOFT = '#4a5b6c';
var RULE = '#dcd6c9';

var DISPLAY = "Georgia, 'Iowan Old Style', 'Times New Roman', serif";
var BODY = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif";

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/* Wraps body content in the masthead / footer shell. `preheader` is the
   snippet inboxes show next to the subject line; hiding it keeps it out of
   the visible email while still populating that preview. */
function shell(opts) {
  var preheader = esc(opts.preheader || '');
  return (
    '<!doctype html>\n' +
    '<html lang="en">\n<head>\n' +
    '<meta charset="utf-8" />\n' +
    '<meta name="viewport" content="width=device-width, initial-scale=1" />\n' +
    '<meta name="color-scheme" content="light" />\n' +
    '<meta name="supported-color-schemes" content="light" />\n' +
    '<title>' + esc(opts.title || 'Helm & Horizon') + '</title>\n' +
    '</head>\n' +
    '<body style="margin:0;padding:0;background:' + PAPER + ';">\n' +
    '<div style="display:none;max-height:0;overflow:hidden;opacity:0;">' + preheader + '</div>\n' +
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:' + PAPER + ';">\n' +
    '<tr><td align="center" style="padding:24px 12px;">\n' +
    '<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:#ffffff;border:1px solid ' + RULE + ';">\n' +

    /* Masthead */
    '<tr><td style="background:' + NAVY_DEEP + ';padding:26px 32px;">\n' +
    '<div style="font-family:' + DISPLAY + ';font-size:20px;color:' + PAPER + ';letter-spacing:0.04em;">Helm &amp; Horizon</div>\n' +
    '<div style="font-family:' + BODY + ';font-size:11px;color:' + GOLD + ';letter-spacing:0.16em;text-transform:uppercase;padding-top:6px;">A monthly market briefing</div>\n' +
    '</td></tr>\n' +
    '<tr><td style="background:' + GOLD + ';height:3px;line-height:3px;font-size:0;">&nbsp;</td></tr>\n' +

    /* Body */
    '<tr><td style="padding:32px;font-family:' + BODY + ';font-size:16px;line-height:1.6;color:' + INK_SOFT + ';">\n' +
    opts.body +
    '</td></tr>\n' +

    /* Footer */
    '<tr><td style="border-top:1px solid ' + RULE + ';padding:20px 32px 26px;font-family:' + BODY + ';font-size:12px;line-height:1.6;color:#7c8794;">\n' +
    opts.footer +
    '</td></tr>\n' +

    '</table>\n</td></tr>\n</table>\n</body>\n</html>'
  );
}

/* A button that survives Outlook: a table cell with a background colour, not
   a styled anchor. */
function button(href, label) {
  return (
    '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:28px 0;">\n' +
    '<tr><td align="center" bgcolor="' + GOLD + '" style="background:' + GOLD + ';border-radius:2px;">\n' +
    '<a href="' + esc(href) + '" style="display:inline-block;padding:14px 30px;font-family:' + BODY +
    ';font-size:15px;font-weight:bold;color:' + NAVY_DEEP + ';text-decoration:none;letter-spacing:0.01em;">' +
    esc(label) + '</a>\n' +
    '</td></tr>\n</table>'
  );
}

function confirmation(opts) {
  var url = opts.url;
  var name = (opts.name || '').trim();
  var greeting = name ? 'Hello ' + esc(name.split(' ')[0]) + ',' : 'Hello,';

  var body =
    '<p style="margin:0 0 18px;color:' + INK + ';">' + greeting + '</p>\n' +
    '<h1 style="margin:0 0 18px;font-family:' + DISPLAY + ';font-size:26px;line-height:1.2;font-weight:500;color:' + INK + ';">Confirm your subscription</h1>\n' +
    '<p style="margin:0 0 16px;">One issue a month, on the first Thursday: the earnings tape, the charter picture, the risk notices, and three things worth doing about it. Every figure cited to a primary source.</p>\n' +
    '<p style="margin:0 0 4px;">Confirm the address to start receiving it.</p>\n' +
    button(url, 'Confirm subscription') +
    '<p style="margin:0 0 8px;font-size:13px;">If the button does not work, paste this into your browser:</p>\n' +
    '<p style="margin:0 0 20px;font-size:13px;word-break:break-all;"><a href="' + esc(url) + '" style="color:' + NAVY + ';">' + esc(url) + '</a></p>\n' +
    '<p style="margin:0;padding-top:18px;border-top:1px solid ' + RULE + ';font-size:13px;">This link is valid for seven days. Nothing will be sent unless you confirm.</p>';

  var footer =
    '<p style="margin:0 0 8px;">You are receiving this because this address was entered at ' +
    '<a href="https://thehelmandhorizon.com" style="color:#7c8794;">thehelmandhorizon.com</a>. ' +
    'If that was not you, ignore this email and nothing further will be sent.</p>\n' +
    '<p style="margin:0;">Helm &amp; Horizon is published by The Walton Group, Inc. Sources cited inline. Not investment advice.</p>';

  var text =
    'Helm & Horizon — a monthly market briefing for yacht industry leaders\n' +
    '======================================================================\n\n' +
    greeting.replace(/&#39;/g, "'") + '\n\n' +
    'CONFIRM YOUR SUBSCRIPTION\n\n' +
    'One issue a month, on the first Thursday: the earnings tape, the charter\n' +
    'picture, the risk notices, and three things worth doing about it. Every\n' +
    'figure cited to a primary source.\n\n' +
    'Confirm the address to start receiving it:\n\n' +
    url + '\n\n' +
    'This link is valid for seven days. Nothing will be sent unless you confirm.\n\n' +
    '----------------------------------------------------------------------\n' +
    'You are receiving this because this address was entered at\n' +
    'thehelmandhorizon.com. If that was not you, ignore this email and\n' +
    'nothing further will be sent.\n\n' +
    'Helm & Horizon is published by The Walton Group, Inc.\n' +
    'Sources cited inline. Not investment advice.\n';

  return {
    subject: 'Confirm your Helm & Horizon subscription',
    html: shell({
      title: 'Confirm your Helm & Horizon subscription',
      preheader: 'One click to confirm, and the next issue is yours.',
      body: body,
      footer: footer
    }),
    text: text
  };
}

module.exports = { confirmation: confirmation, esc: esc, shell: shell, button: button };
