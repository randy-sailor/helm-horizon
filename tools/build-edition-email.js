#!/usr/bin/env node
/* Turns an edition page into a branded email edition.
 *
 *   node tools/build-edition-email.js editions/september-2026.html
 *   -> emails/september-2026.html
 *
 * Paste the output into a Resend Broadcast. It reuses api/_email.js for the
 * masthead, footer and button, so the email and the confirmation mail cannot
 * drift apart.
 *
 * No dependencies: a small parser covers the subset of markup the editions
 * actually use, and the build asserts that every heading, paragraph and link
 * survived the conversion.
 */

'use strict';

var fs = require('fs');
var pathmod = require('path');
var tpl = require('../api/_email');

var SITE = 'https://thehelmandhorizon.com';

var NAVY_DEEP = '#06192e';
var NAVY = '#0b2a4a';
var GOLD = '#c9a55a';
var INK = '#14202c';
var INK_SOFT = '#4a5b6c';
var INK_FAINT = '#5a6a78';
var RULE = '#dcd6c9';
var PAPER_WARM = '#efeae0';
var WARN_BG = '#fdf6e8';
var LIGHT_BLUE = '#cfdcec';

var DISPLAY = "Georgia, 'Iowan Old Style', 'Times New Roman', serif";
var BODY = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif";

/* ---------------------------------------------------------------- parser */

var VOID = { img: 1, br: 1, hr: 1, meta: 1, link: 1, input: 1, source: 1 };

function parseAttrs(s) {
  var attrs = {};
  var re = /([^\s"'>\/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?/g;
  var m;
  while ((m = re.exec(s))) {
    attrs[m[1].toLowerCase()] = m[2] !== undefined ? m[2] : m[3] !== undefined ? m[3] : m[4] || '';
  }
  return attrs;
}

function parse(html) {
  var root = { tag: '#root', attrs: {}, children: [] };
  var stack = [root];
  var re = /<!--[\s\S]*?-->|<(\/?)([a-zA-Z0-9]+)((?:\s+[^\s"'>\/=]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'>]+))?)*)\s*(\/?)>|([^<]+)/g;
  var m;
  while ((m = re.exec(html))) {
    if (m[0].slice(0, 4) === '<!--') continue;
    if (m[5] !== undefined) {
      stack[stack.length - 1].children.push({ tag: '#text', text: m[5] });
      continue;
    }
    var closing = m[1] === '/';
    var tag = m[2].toLowerCase();
    if (closing) {
      for (var i = stack.length - 1; i > 0; i--) {
        if (stack[i].tag === tag) { stack.length = i; break; }
      }
      continue;
    }
    var node = { tag: tag, attrs: parseAttrs(m[3] || ''), children: [] };
    stack[stack.length - 1].children.push(node);
    if (!m[4] && !VOID[tag]) stack.push(node);
  }
  return root;
}

/* Source text arrives already HTML-escaped (&mdash;, &amp;, …). Decode it to
   real characters so tpl.esc() can re-encode exactly what needs encoding —
   escaping twice would print "&mdash;" literally in the inbox. The document
   declares UTF-8, so the decoded characters travel fine. */
var ENTITIES = {
  amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ',
  mdash: '—', ndash: '–', hellip: '…', middot: '·',
  lsquo: '‘', rsquo: '’', ldquo: '“', rdquo: '”',
  euro: '€', pound: '£', copy: '©', reg: '®',
  minus: '−', times: '×', rarr: '→', larr: '←',
  deg: '°', bull: '•', trade: '™'
};

function decode(s) {
  return String(s == null ? '' : s).replace(/&(#x?[0-9a-fA-F]+|[a-zA-Z]+);/g, function (m, ref) {
    if (ref.charAt(0) === '#') {
      var code = ref.charAt(1) === 'x' || ref.charAt(1) === 'X'
        ? parseInt(ref.slice(2), 16)
        : parseInt(ref.slice(1), 10);
      return isNaN(code) ? m : String.fromCodePoint(code);
    }
    return Object.prototype.hasOwnProperty.call(ENTITIES, ref) ? ENTITIES[ref] : m;
  });
}

function hasClass(n, c) {
  return n.attrs && n.attrs.class && (' ' + n.attrs.class + ' ').indexOf(' ' + c + ' ') !== -1;
}

function find(node, pred, out) {
  out = out || [];
  (node.children || []).forEach(function (c) {
    if (pred(c)) out.push(c);
    find(c, pred, out);
  });
  return out;
}

function firstBy(node, pred) {
  var r = find(node, pred);
  return r.length ? r[0] : null;
}

/* Collapsed text content, for assertions and for plain-text output. */
function textOf(node) {
  if (node.tag === '#text') return decode(node.text);
  return (node.children || []).map(textOf).join('');
}

function squash(s) {
  return s.replace(/\s+/g, ' ').trim();
}

/* ------------------------------------------------------------- inline map */

/* Inline markup is kept but restyled: links get brand colour, strong gets ink.
   Anything unrecognised degrades to its text so nothing is silently dropped. */
function inline(node) {
  if (node.tag === '#text') return tpl.esc(decode(node.text));
  var kids = (node.children || []).map(inline).join('');
  switch (node.tag) {
    case 'a':
      var href = decode(node.attrs.href || '');
      if (href.charAt(0) === '/') href = SITE + href;
      if (href.charAt(0) === '#') return kids;
      return '<a href="' + tpl.esc(href) + '" style="color:' + NAVY + ';text-decoration:underline;">' + kids + '</a>';
    case 'strong':
    case 'b':
      return '<strong style="color:' + INK + ';font-weight:bold;">' + kids + '</strong>';
    case 'em':
    case 'i':
      return '<em>' + kids + '</em>';
    case 'br':
      return '<br />';
    default:
      return kids;
  }
}

/* --------------------------------------------------------------- blocks */

function para(node) {
  var html = inline(node).trim();
  if (!html) return '';
  return '<p style="margin:0 0 16px;font-family:' + BODY + ';font-size:16px;line-height:1.6;color:' + INK_SOFT + ';">' + html + '</p>\n';
}

function h2(node) {
  return (
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:34px 0 0;">\n' +
    '<tr><td style="border-top:1px solid ' + RULE + ';padding-top:22px;">\n' +
    '<h2 style="margin:0 0 14px;font-family:' + DISPLAY + ';font-size:23px;line-height:1.25;font-weight:500;color:' + INK + ';">' +
    inline(node).trim() + '</h2>\n</td></tr></table>\n'
  );
}

function h3(node) {
  return '<h3 style="margin:24px 0 10px;font-family:' + BODY + ';font-size:17px;line-height:1.35;font-weight:bold;color:' + INK + ';">' +
    inline(node).trim() + '</h3>\n';
}

/* ul.datalist renders as label/value rows; a plain ul renders as bullets. */
function list(node) {
  var items = (node.children || []).filter(function (c) { return c.tag === 'li'; });
  if (!items.length) return '';

  if (hasClass(node, 'datalist')) {
    var rows = items.map(function (li) {
      var label = firstBy(li, function (n) { return n.tag === 'span'; });
      var value = firstBy(li, function (n) { return n.tag === 'b'; });
      if (!label || !value) {
        return '<tr><td colspan="2" style="padding:9px 0;border-bottom:1px solid ' + RULE + ';font-family:' + BODY +
          ';font-size:15px;color:' + INK_SOFT + ';">' + inline(li).trim() + '</td></tr>';
      }
      return '<tr>' +
        '<td style="padding:9px 12px 9px 0;border-bottom:1px solid ' + RULE + ';font-family:' + BODY +
        ';font-size:15px;line-height:1.45;color:' + INK_SOFT + ';">' + inline(label).trim() + '</td>' +
        '<td align="right" style="padding:9px 0;border-bottom:1px solid ' + RULE + ';font-family:' + BODY +
        ';font-size:15px;line-height:1.45;font-weight:bold;color:' + INK + ';white-space:nowrap;">' + inline(value).trim() + '</td>' +
        '</tr>';
    }).join('\n');
    return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 20px;">\n' + rows + '\n</table>\n';
  }

  if (hasClass(node, 'keylist')) {
    var kl = items.map(function (li) {
      var s = firstBy(li, function (n) { return n.tag === 'strong'; });
      var v = firstBy(li, function (n) { return n.tag === 'span'; });
      return '<tr><td style="padding:8px 0;border-bottom:1px solid ' + RULE + ';font-family:' + BODY +
        ';font-size:15px;color:' + INK_SOFT + ';">' +
        (s ? '<strong style="color:' + INK + ';">' + inline(s).trim() + '</strong> ' : '') +
        (v ? inline(v).trim() : (s ? '' : inline(li).trim())) + '</td></tr>';
    }).join('\n');
    return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 20px;">\n' + kl + '\n</table>\n';
  }

  return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 18px;">\n' +
    items.map(function (li) {
      return '<tr><td width="18" valign="top" style="font-family:' + BODY + ';font-size:16px;line-height:1.6;color:' + GOLD + ';">&bull;</td>' +
        '<td style="font-family:' + BODY + ';font-size:16px;line-height:1.6;color:' + INK_SOFT + ';padding-bottom:6px;">' +
        inline(li).trim() + '</td></tr>';
    }).join('\n') + '\n</table>\n';
}

function callout(node) {
  var eyebrow = firstBy(node, function (n) { return hasClass(n, 'eyebrow'); });
  var ps = (node.children || []).filter(function (c) { return c.tag === 'p' && !hasClass(c, 'eyebrow'); });
  return (
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:26px 0;">\n' +
    '<tr><td width="4" bgcolor="' + GOLD + '" style="background:' + GOLD + ';font-size:0;line-height:0;">&nbsp;</td>\n' +
    '<td bgcolor="' + NAVY + '" style="background:' + NAVY + ';padding:22px 24px;">\n' +
    (eyebrow ? '<div style="font-family:' + BODY + ';font-size:11px;letter-spacing:0.16em;text-transform:uppercase;color:' + GOLD + ';padding-bottom:10px;">' + squash(textOf(eyebrow)) + '</div>\n' : '') +
    ps.map(function (p) {
      return '<p style="margin:0 0 10px;font-family:' + BODY + ';font-size:16px;line-height:1.6;color:' + LIGHT_BLUE + ';">' + inline(p).trim() + '</p>';
    }).join('\n') +
    '\n</td></tr></table>\n'
  );
}

function warn(node) {
  var h = firstBy(node, function (n) { return n.tag === 'h4'; });
  var ps = (node.children || []).filter(function (c) { return c.tag === 'p'; });
  return (
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 16px;">\n' +
    '<tr><td width="4" bgcolor="' + GOLD + '" style="background:' + GOLD + ';font-size:0;line-height:0;">&nbsp;</td>\n' +
    '<td bgcolor="' + WARN_BG + '" style="background:' + WARN_BG + ';padding:18px 20px;">\n' +
    (h ? '<div style="font-family:' + BODY + ';font-size:11px;letter-spacing:0.14em;text-transform:uppercase;font-weight:bold;color:#8a6a1f;padding-bottom:8px;">' + squash(textOf(h)) + '</div>\n' : '') +
    ps.map(function (p) {
      return '<p style="margin:0 0 8px;font-family:' + BODY + ';font-size:15px;line-height:1.6;color:' + INK_SOFT + ';">' + inline(p).trim() + '</p>';
    }).join('\n') +
    '\n</td></tr></table>\n'
  );
}

function steps(node) {
  var arts = (node.children || []).filter(function (c) { return c.tag === 'article'; });
  return arts.map(function (a) {
    var n = firstBy(a, function (x) { return hasClass(x, 'step__n'); });
    var heading = firstBy(a, function (x) { return x.tag === 'h3'; });
    var ps = find(a, function (x) { return x.tag === 'p'; });
    return (
      '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 22px;">\n' +
      '<tr><td width="42" valign="top" style="padding-right:14px;">\n' +
      '<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>' +
      '<td width="34" height="34" align="center" valign="middle" bgcolor="' + NAVY + '" style="background:' + NAVY +
      ';font-family:' + DISPLAY + ';font-size:16px;color:' + GOLD + ';">' + (n ? squash(textOf(n)) : '&bull;') + '</td>' +
      '</tr></table>\n</td>\n<td valign="top">\n' +
      (heading ? '<div style="font-family:' + BODY + ';font-size:16px;line-height:1.4;font-weight:bold;color:' + INK + ';padding-bottom:6px;">' + inline(heading).trim() + '</div>\n' : '') +
      ps.map(function (p) {
        return '<p style="margin:0 0 10px;font-family:' + BODY + ';font-size:15px;line-height:1.6;color:' + INK_SOFT + ';">' + inline(p).trim() + '</p>';
      }).join('\n') +
      '\n</td></tr></table>\n'
    );
  }).join('');
}

function figure(node) {
  var img = firstBy(node, function (n) { return n.tag === 'img'; });
  var cap = firstBy(node, function (n) { return n.tag === 'figcaption'; });
  if (!img) return '';
  var src = decode(img.attrs.src || '');
  if (src.charAt(0) === '/') src = SITE + src;
  return (
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0;">\n' +
    '<tr><td><img src="' + tpl.esc(src) + '" alt="' + tpl.esc(decode(img.attrs.alt || '')) +
    '" width="536" style="display:block;width:100%;max-width:536px;height:auto;border:0;" /></td></tr>\n' +
    (cap ? '<tr><td style="padding-top:8px;font-family:' + BODY + ';font-size:12px;line-height:1.5;color:' + INK_FAINT + ';">' + inline(cap).trim() + '</td></tr>\n' : '') +
    '</table>\n'
  );
}

function btnRow(node) {
  var links = find(node, function (n) { return n.tag === 'a'; });
  return links.map(function (a) {
    var href = decode(a.attrs.href || '');
    if (href.charAt(0) === '/') href = SITE + href;
    if (href.charAt(0) === '#') return '';
    return tpl.button(href, squash(textOf(a)));
  }).join('');
}

/* Dispatch for a top-level block inside <article class="prose">. */
function block(node) {
  if (node.tag === '#text') return '';
  if (node.tag === 'h2') return h2(node);
  if (node.tag === 'h3') return h3(node);
  if (node.tag === 'p') return para(node);
  if (node.tag === 'ul') return list(node);
  if (node.tag === 'figure') return figure(node);
  if (hasClass(node, 'callout')) return callout(node);
  if (hasClass(node, 'warn')) return warn(node);
  if (hasClass(node, 'steps')) return steps(node);
  if (hasClass(node, 'btn-row')) return btnRow(node);
  /* Unknown wrapper: descend rather than drop its contents. */
  return (node.children || []).map(block).join('');
}

/* ----------------------------------------------------------------- build */

function build(srcPath) {
  var src = fs.readFileSync(srcPath, 'utf8');
  var doc = parse(src);

  var article = firstBy(doc, function (n) { return hasClass(n, 'prose'); });
  if (!article) throw new Error('No <article class="prose"> found in ' + srcPath);

  var hero = firstBy(doc, function (n) { return hasClass(n, 'hero__meta'); });
  var meta = hero ? find(hero, function (n) { return n.tag === 'span'; }).map(function (s) { return squash(textOf(s)); }) : [];

  var h1 = firstBy(doc, function (n) { return n.tag === 'h1'; });
  var headline = h1 ? squash(textOf(h1)) : 'Helm & Horizon';

  var slug = pathmod.basename(srcPath).replace(/\.html$/, '');
  var editionUrl = SITE + '/editions/' + slug;

  var canonical = firstBy(doc, function (n) { return n.tag === 'link' && n.attrs.rel === 'canonical'; });
  if (canonical && canonical.attrs.href) editionUrl = decode(canonical.attrs.href);

  var desc = firstBy(doc, function (n) { return n.tag === 'meta' && n.attrs.property === 'og:description'; });
  var preheader = desc ? squash(decode(desc.attrs.content || '')) : headline;

  var body =
    /* Issue line + headline */
    '<div style="font-family:' + BODY + ';font-size:11px;letter-spacing:0.16em;text-transform:uppercase;color:' + INK_FAINT + ';padding-bottom:12px;">' +
    tpl.esc(meta.join('  ·  ')) + '</div>\n' +
    '<h1 style="margin:0 0 14px;font-family:' + DISPLAY + ';font-size:30px;line-height:1.18;font-weight:500;color:' + INK + ';">' +
    tpl.esc(headline) + '</h1>\n' +
    '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 22px;"><tr>' +
    '<td width="72" height="3" bgcolor="' + GOLD + '" style="background:' + GOLD + ';font-size:0;line-height:0;">&nbsp;</td>' +
    '</tr></table>\n' +
    (article.children || []).map(block).join('') +
    /* Read online / PDF */
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:30px 0 0;">\n' +
    '<tr><td bgcolor="' + PAPER_WARM + '" style="background:' + PAPER_WARM + ';padding:20px 22px;font-family:' + BODY +
    ';font-size:15px;line-height:1.6;color:' + INK_SOFT + ';">' +
    'Prefer to read it in the browser, or circulate it internally? ' +
    '<a href="' + tpl.esc(editionUrl) + '" style="color:' + NAVY + ';">Read this issue online</a> or ' +
    '<a href="' + SITE + '/pdf/Helm_Horizon_' + slugToPdf(slug) + '.pdf" style="color:' + NAVY + ';">download the PDF companion</a>.' +
    '</td></tr></table>\n';

  var footer =
    '<p style="margin:0 0 8px;">You are receiving this because you confirmed a subscription at ' +
    '<a href="' + SITE + '" style="color:#7c8794;">thehelmandhorizon.com</a>. ' +
    '<a href="{{{RESEND_UNSUBSCRIBE_URL}}}" style="color:#7c8794;text-decoration:underline;">Unsubscribe</a> from any issue.</p>\n' +
    '<p style="margin:0;">Helm &amp; Horizon is published by The Walton Group, Inc. Sources cited inline. Not investment advice.</p>';

  var html = tpl.shell({
    title: headline + ' — Helm & Horizon',
    preheader: preheader,
    body: body,
    footer: footer
  });

  return { html: html, headline: headline, meta: meta, article: article, editionUrl: editionUrl };
}

/* september-2026 -> September2026, matching the existing pdf/ filenames. */
function slugToPdf(slug) {
  var parts = slug.split('-');
  if (parts.length !== 2) return slug;
  return parts[0].charAt(0).toUpperCase() + parts[0].slice(1) + parts[1];
}

/* ------------------------------------------------------------ assertions */

/* The conversion is lossy by design (nav, sidebar, scripts are dropped), but
   nothing from the article body should vanish silently. */
function verify(result) {
  var problems = [];
  var out = result.html;

  /* Compare rendered text, not markup. A paragraph containing a link has no
     contiguous run of plain text, so substring-matching the HTML gives false
     alarms — which is exactly what it did on the first run. */
  var outText = squash(textOf(parse(out)));

  find(result.article, function (n) { return n.tag === 'a'; })
    .map(function (a) { return decode(a.attrs.href || ''); })
    .filter(function (h) { return h && h.charAt(0) !== '#'; })
    .forEach(function (h) {
      var abs = h.charAt(0) === '/' ? SITE + h : h;
      if (out.indexOf(tpl.esc(abs)) === -1) problems.push('link missing from email: ' + h);
    });

  find(result.article, function (n) { return n.tag === 'h2' || n.tag === 'h3'; }).forEach(function (h) {
    var t = squash(textOf(h));
    if (t && outText.indexOf(t) === -1) problems.push('heading missing: ' + t.slice(0, 50));
  });

  find(result.article, function (n) { return n.tag === 'p'; }).forEach(function (p) {
    var t = squash(textOf(p));
    if (t.length < 40) return;
    if (outText.indexOf(t) === -1) problems.push('paragraph missing: ' + t.slice(0, 50) + '…');
  });

  find(result.article, function (n) { return n.tag === 'li'; }).forEach(function (li) {
    var t = squash(textOf(li));
    if (t.length < 8) return;
    if (outText.indexOf(t.slice(0, 30)) === -1) problems.push('list item missing: ' + t.slice(0, 40));
  });

  if (out.indexOf('{{{RESEND_UNSUBSCRIBE_URL}}}') === -1) problems.push('unsubscribe variable missing');
  if (/display:\s*(flex|grid)/.test(out)) problems.push('flex or grid present — will not render in email');
  if (/<link|@import/.test(out)) problems.push('external stylesheet reference present');
  /* Double-escaped entities are invisible in source but print literally. */
  var dbl = out.match(/&amp;(?:[a-z]+|#\d+);/g);
  if (dbl) problems.push('double-escaped entities (' + dbl.length + '), e.g. ' + dbl[0]);
  return problems;
}

/* ------------------------------------------------------------------ main */

if (require.main === module) {
  var input = process.argv[2];
  if (!input) {
    console.error('usage: node tools/build-edition-email.js editions/<slug>.html');
    process.exit(1);
  }
  var result = build(input);
  var problems = verify(result);

  var slug = pathmod.basename(input).replace(/\.html$/, '');
  var outDir = pathmod.join(__dirname, '..', 'emails');
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  var outPath = pathmod.join(outDir, slug + '.html');
  fs.writeFileSync(outPath, result.html);

  console.log('built  ' + pathmod.relative(process.cwd(), outPath));
  console.log('       ' + result.headline);
  console.log('       ' + result.meta.join(' · '));
  console.log('       ' + Math.round(result.html.length / 1024) + ' KB');
  if (problems.length) {
    console.log('\nPROBLEMS');
    problems.forEach(function (p) { console.log('  - ' + p); });
    process.exit(1);
  }
  console.log('       content check passed');
}

module.exports = { build: build, verify: verify, parse: parse };
