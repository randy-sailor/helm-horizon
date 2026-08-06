#!/usr/bin/env python3
"""Render an edition's PDF companion from the same JSON as the web page.

    python3 tools/render_pdf.py content/editions/september-2026.json
    python3 tools/render_pdf.py content/editions/september-2026.json --out /tmp/x.pdf

The PDF and the page are two renderings of one source, and the filename comes
from `render_html.pdf_name` so the page's download link and the file on disk
cannot drift apart.

Design tokens are the ones in `assets/base.css`. Type is not: Zodiak and Satoshi
are served to browsers from Fontshare and are not in this repository, so the PDF
uses the best sans available on the machine and says which one it picked. That
is a deliberate substitution, not an oversight — see `--fonts`.
"""

import argparse
import json
import os
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)
from reportlab.platypus.flowables import Flowable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_html import MD_BOLD, MD_ITAL, MD_LINK, pdf_name, plain  # noqa: E402

# ------------------------------------------------------------------- the palette
# assets/base.css, verbatim. Change them there and change them here.

NAVY = colors.HexColor('#0b2a4a')
DEEP_NAVY = colors.HexColor('#06192e')
GOLD = colors.HexColor('#c9a55a')
LIGHT_BLUE = colors.HexColor('#cfdcec')
SOFT_BG = colors.HexColor('#f4f7fa')
WARN_BG = colors.HexColor('#fff7e8')
WARN_BORDER = colors.HexColor('#f0d9a8')
WARN_TEXT = colors.HexColor('#5a4410')
WARN_TITLE = colors.HexColor('#8a6212')
TEXT = colors.HexColor('#1a2a3a')
MUTED = colors.HexColor('#5e7186')
LINK = '#0b5fa5'
DIVIDER = colors.HexColor('#e3e8ee')

SITE = 'https://thehelmandhorizon.com'


# --------------------------------------------------------------------- the type

# Ordered best to worst. The base-14 Helvetica at the end always exists but
# cannot draw a minus sign or an arrow, which the indicators are full of.
FONT_CANDIDATES = [
    ('DejaVu Sans', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
     '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
     '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf'),
    ('Liberation Sans', '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
     '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
     '/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf'),
    ('FreeSans', '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
     '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
     '/usr/share/fonts/truetype/freefont/FreeSansOblique.ttf'),
]

# Typography the editions actually use that WinAnsi cannot encode. Without this
# a Helvetica fallback prints "-7%" as a black box, which reads as a defect in
# the data rather than in the font.
NON_WINANSI = {
    '−': '-',      # minus sign, as in "−7%"
    '→': '->',     # rightwards arrow, as in "118 -> 83 days"
    '≤': '<=',
    '≥': '>=',
    '×': 'x',      # multiplication sign, as in "3.7x"
    '≈': '~',
    '′': "'",
    '″': '"',
}


def resolve_fonts(prefer=None):
    """Register the best available sans. Returns (body, bold, italic, name)."""
    for name, regular, bold, italic in FONT_CANDIDATES:
        if prefer and prefer.lower() not in name.lower():
            continue
        if not all(os.path.exists(p) for p in (regular, bold)):
            continue
        # Some packages ship regular and bold but no oblique — DejaVu on this
        # image, for one. Upright italics beat falling back to a font that
        # cannot draw a minus sign.
        if not os.path.exists(italic):
            italic = regular
        try:
            key = name.replace(' ', '')
            pdfmetrics.registerFont(TTFont(key, regular))
            pdfmetrics.registerFont(TTFont(key + '-Bold', bold))
            pdfmetrics.registerFont(TTFont(key + '-Italic', italic))
            pdfmetrics.registerFontFamily(key, normal=key, bold=key + '-Bold',
                                          italic=key + '-Italic',
                                          boldItalic=key + '-Bold')
            return key, key + '-Bold', key + '-Italic', name
        except Exception:
            continue
    return 'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique', 'Helvetica (built in)'


# ---------------------------------------------------------------- markdown -> RL

def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def rl(s, unicode_ok=True):
    """[text](url) -> <a>, **bold** -> <b>, *italic* -> <i>. Rest is escaped.

    ReportLab's paragraph parser takes a small HTML subset, so this is a sibling
    of render_html.inline() rather than a reuse of it: no target, no rel, <b>
    instead of <strong>.
    """
    out, pos = [], 0
    for m in MD_LINK.finditer(s):
        out.append(_emph(esc(s[pos:m.start()])))
        out.append('<a href="%s" color="%s">%s</a>'
                   % (esc(m.group(2)), LINK, _emph(esc(m.group(1)))))
        pos = m.end()
    out.append(_emph(esc(s[pos:])))
    text = ''.join(out)
    if not unicode_ok:
        for bad, ok in NON_WINANSI.items():
            text = text.replace(bad, ok)
    return text


def _emph(escaped):
    escaped = MD_BOLD.sub(r'<b>\1</b>', escaped)
    return MD_ITAL.sub(r'<i>\1</i>', escaped)


def flatten(s, unicode_ok=True):
    """Markdown out, for text drawn straight onto the canvas."""
    text = plain(s)
    if not unicode_ok:
        for bad, ok in NON_WINANSI.items():
            text = text.replace(bad, ok)
    return text


# ------------------------------------------------------------------- flowables

class Banner(Flowable):
    """The masthead block: brand, issue line, headline, gold rule."""

    def __init__(self, width, brand, issue, lines, fonts):
        Flowable.__init__(self)
        self.width = width
        self.brand, self.issue, self.lines, self.fonts = brand, issue, lines, fonts
        self.height = 1.15 * inch + 0.3 * inch * len(lines)

    def draw(self):
        c, (body, bold, _italic) = self.canv, self.fonts
        c.setFillColor(NAVY)
        c.rect(0, 0, self.width, self.height, stroke=0, fill=1)
        c.setFillColor(LIGHT_BLUE)
        c.setFont(bold, 9)
        c.drawString(0.3 * inch, self.height - 0.35 * inch, self.brand)
        c.drawRightString(self.width - 0.3 * inch, self.height - 0.35 * inch, self.issue)
        c.setFillColor(colors.white)
        c.setFont(bold, 22)
        y = self.height - 0.85 * inch
        for line in self.lines:
            c.drawString(0.3 * inch, y, line)
            y -= 0.3 * inch
        c.setStrokeColor(GOLD)
        c.setLineWidth(2)
        c.line(0.3 * inch, y - 0.05 * inch, 1.5 * inch, y - 0.05 * inch)


class SectionLabel(Flowable):
    def __init__(self, label, title, width, fonts):
        Flowable.__init__(self)
        self.label, self.title, self.width, self.fonts = label, title, width, fonts
        self.height = 0.55 * inch

    def draw(self):
        c, (body, bold, _italic) = self.canv, self.fonts
        c.setFillColor(GOLD)
        c.setFont(bold, 8.5)
        c.drawString(0, self.height - 0.2 * inch, self.label.upper())
        c.setFillColor(NAVY)
        c.setFont(bold, 17)
        c.drawString(0, self.height - 0.5 * inch, self.title)


class Divider(Flowable):
    def __init__(self, width):
        Flowable.__init__(self)
        self.width, self.height = width, 0.05 * inch

    def draw(self):
        self.canv.setStrokeColor(DIVIDER)
        self.canv.setLineWidth(0.5)
        self.canv.line(0, 0, self.width, 0)


def boxed(content, width, background, pad=12, border=None, rule=None):
    """A tinted panel. One table row per flowable, so it can break across pages.

    A single-row table cannot split, and a five-inch profile box that will not
    split leaves half a page empty every time it does not fit. One row per
    paragraph costs nothing and lets the tint continue onto the next page.
    """
    rows = content if isinstance(content, list) else [content]
    t = Table([[r] for r in rows], colWidths=[width], splitByRow=1)
    style = [('BACKGROUND', (0, 0), (-1, -1), background),
             ('LEFTPADDING', (0, 0), (-1, -1), pad),
             ('RIGHTPADDING', (0, 0), (-1, -1), pad),
             # Padding on the outside of the panel only; rows sit flush against
             # each other so their own spaceAfter controls the rhythm.
             ('TOPPADDING', (0, 0), (-1, -1), 0),
             ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
             ('TOPPADDING', (0, 0), (0, 0), pad - 2),
             ('BOTTOMPADDING', (0, -1), (0, -1), pad - 2)]
    if border:
        style.append(('BOX', (0, 0), (-1, -1), 0.5, border))
    if rule:
        style.append(('LINEBEFORE', (0, 0), (0, -1), 3, rule))
    t.setStyle(TableStyle(style))
    return t


NO_PAD = [('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
          ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
          ('VALIGN', (0, 0), (-1, -1), 'TOP')]


def glued(flowables, width):
    """One row, one cell — a unit that cannot split across a page.

    KeepTogether reports an infinite height inside a table cell and blows up the
    layout, so this is how a heading stays with its first paragraph inside a
    tinted panel.
    """
    t = Table([[flowables]], colWidths=[width])
    t.setStyle(TableStyle(NO_PAD))
    return t


def bare(rows, width):
    """A table used purely for stacking, with no padding of its own."""
    t = Table([[r] for r in rows], colWidths=[width])
    t.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                           ('TOPPADDING', (0, 0), (-1, -1), 0),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                           ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    return t


# ----------------------------------------------------------------------- styles

def make_styles(body, bold, italic):
    def s(name, **kw):
        kw.setdefault('fontName', body)
        return ParagraphStyle(name, **kw)
    return {
        'body': s('body', fontSize=10.5, leading=15.5, textColor=TEXT, spaceAfter=8,
                  alignment=TA_LEFT),
        'lead': s('lead', fontSize=11, leading=16.5, textColor=TEXT, spaceAfter=9),
        'feature_title': s('feature_title', fontName=bold, fontSize=17, leading=21,
                           textColor=NAVY, spaceAfter=10),
        'sub_head': s('sub_head', fontName=bold, fontSize=12.5, leading=16,
                      textColor=NAVY, spaceAfter=5),
        'callout_label': s('callout_label', fontName=bold, fontSize=9, leading=11,
                           textColor=NAVY, spaceAfter=3),
        'callout_body': s('callout_body', fontSize=10, leading=14, textColor=TEXT),
        'panel_h': s('panel_h', fontName=bold, fontSize=10.5, leading=13, textColor=GOLD,
                     spaceAfter=6),
        'panel_body': s('panel_body', fontSize=9.3, leading=13.5, textColor=colors.white),
        'risk_label': s('risk_label', fontName=bold, fontSize=8.5, leading=11,
                        textColor=WARN_TITLE, spaceAfter=3),
        'risk_body': s('risk_body', fontSize=9, leading=12.5, textColor=WARN_TEXT),
        'step_n': s('step_n', fontName=bold, fontSize=22, leading=26, textColor=GOLD,
                    alignment=TA_CENTER),
        'step_title': s('step_title', fontName=bold, fontSize=11.5, leading=14,
                        textColor=NAVY, spaceAfter=4),
        'step_body': s('step_body', fontSize=10, leading=14.5, textColor=TEXT),
        'subtitle': s('subtitle', fontName=italic, fontSize=10, leading=13, textColor=MUTED,
                      spaceAfter=8),
        'caption': s('caption', fontName=italic, fontSize=9, leading=12, textColor=MUTED),
        'quote': s('quote', fontName=italic, fontSize=10.5, leading=15, textColor=TEXT,
                   spaceAfter=4),
        'attrib': s('attrib', fontName=bold, fontSize=8.5, leading=11, textColor=NAVY),
        'cta': s('cta', fontSize=10.5, leading=15, textColor=colors.white),
        'footer': s('footer', fontSize=8.5, leading=12.5, textColor=colors.HexColor('#b3c6dd')),
    }


# ------------------------------------------------------------------- the story

def build_story(ed, width, st, fonts, unicode_ok):
    body_font, bold_font, _italic = fonts
    story = []

    def md(s, style='body'):
        return Paragraph(rl(s, unicode_ok), st[style])

    def txt(s, style='body'):
        return Paragraph(esc(flatten(s, unicode_ok)), st[style])

    def label(eyebrow, title):
        return SectionLabel(eyebrow, flatten(title, unicode_ok), width, fonts)

    def rule(space_before=0.2, space_after=0.15):
        return [Spacer(1, space_before * inch), Divider(width), Spacer(1, space_after * inch)]

    # ---- masthead
    headline = flatten(ed['headline'], unicode_ok)
    story.append(Banner(width, 'HELM  &  HORIZON',
                        '%s  ·  Vol. %d, No. %d' % (ed['month'], ed['volume'], ed['number'])
                        if unicode_ok else
                        '%s  -  Vol. %d, No. %d' % (ed['month'], ed['volume'], ed['number']),
                        wrap_headline(headline), fonts))
    story.append(Spacer(1, 0.22 * inch))

    # ---- from the desk
    desk = list(ed.get('from_the_desk') or [])
    if desk:
        first = '<b>From the desk:</b> ' + rl(desk[0], unicode_ok)
        story.append(Paragraph(first, st['lead']))
        for p in desk[1:]:
            story.append(md(p, 'lead'))
    story.append(Spacer(1, 0.1 * inch))

    # ---- featured
    feat = ed['featured']
    story.append(label('Featured story', feat['title']))
    story.append(Spacer(1, 0.08 * inch))
    for sec in feat.get('sections') or []:
        if 'figure' in sec:
            # The web page shows the image; the PDF carries the caption, because
            # a caption with no picture still says something and a missing
            # picture with no caption says nothing.
            cap = sec['figure'].get('caption') or sec['figure'].get('alt')
            if cap:
                story.append(boxed(md(cap, 'caption'), width - 0.1 * inch, SOFT_BG, pad=10,
                                   rule=GOLD))
                story.append(Spacer(1, 0.12 * inch))
            continue
        paras = [md(p) for p in sec.get('body') or []]
        if sec.get('heading'):
            # A heading stranded at the foot of a page reads as the end of the
            # section rather than the start of one, so it travels with its
            # first paragraph.
            head = md(sec['heading'], 'sub_head')
            story.append(KeepTogether([head, paras[0]]) if paras else head)
            paras = paras[1:]
        story.extend(paras)

    take = feat.get('takeaway')
    if take and take.get('body'):
        story.append(Spacer(1, 0.05 * inch))
        story.append(boxed([txt(take.get('eyebrow') or 'Key takeaway', 'callout_label'),
                            md(take['body'], 'callout_body')],
                           width - 0.1 * inch, SOFT_BG))

    story += rule()

    # ---- by the numbers
    # The two columns are one indivisible flowable, so the label has to travel
    # with them or it strands itself at the foot of the previous page. No forced
    # page break: let it land where it lands and keep the pages full.
    story.append(KeepTogether([label('Economic indicators and risk', 'By the numbers'),
                               Spacer(1, 0.1 * inch),
                               indicator_columns(ed, width, st, unicode_ok)]))
    story += rule()

    # ---- three action steps
    actions = ed.get('actions') or []
    story.append(KeepTogether([label('Three action steps', 'What to do this quarter'),
                               Spacer(1, 0.15 * inch)]))
    for i, a in enumerate(actions, start=1):
        circle = Table([[Paragraph(str(i), st['step_n'])]],
                       colWidths=[0.55 * inch], rowHeights=[0.55 * inch])
        circle.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0)]))
        row = Table([[circle, [md(a['title'], 'step_title'), md(a['body'], 'step_body')]]],
                    colWidths=[0.75 * inch, width - 0.75 * inch])
        row.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (1, 0), (1, 0), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0)]))
        story.append(KeepTogether([row, Spacer(1, 0.18 * inch)]))

    story += rule(space_before=0.1, space_after=0.18)

    # ---- profile
    prof = ed['profile']
    title = prof['company'] + (' (%s)' % prof['ticker'] if prof.get('ticker') else '')
    story.append(label('Industry player profile', title))
    if prof.get('dek'):
        story.append(md(prof['dek'], 'subtitle'))
    inner = []
    for sec in prof.get('sections') or []:
        paras = [md(p) for p in sec.get('body') or []]
        if sec.get('heading'):
            head = md(sec['heading'], 'sub_head')
            # One row, so the box splits above the heading rather than under it.
            inner.append(glued([head, paras[0]], width - 0.1 * inch - 32) if paras else head)
            paras = paras[1:]
        inner.extend(paras)
    story.append(boxed(inner, width - 0.1 * inch, SOFT_BG, pad=16))

    story += rule()

    # ---- voices
    story.append(label('Voices from the field', 'Reader submissions'))
    inner = []
    for v in ed.get('voices') or []:
        # The validator refuses this edition outright, but a renderer that would
        # print an uncleared quote if the validator were skipped is a liability.
        if v.get('permission_to_quote') is not True:
            raise SystemExit('refusing to render a quote without permission: %r'
                             % v.get('attribution'))
        inner.append(md('“%s”' % v['quote'] if unicode_ok else '"%s"' % v['quote'],
                        'quote'))
        who = v['attribution'] + (' · ' + v['role'] if v.get('role') else '')
        inner.append(txt(who.upper() if unicode_ok else who.upper(), 'attrib'))
        inner.append(Spacer(1, 0.1 * inch))
    for p in ed.get('voices_intro') or []:
        inner.append(md(p, 'callout_body'))
        inner.append(Spacer(1, 0.06 * inch))
    inner.append(txt('— The Helm & Horizon editors' if unicode_ok
                     else '- The Helm & Horizon editors', 'attrib'))
    story.append(boxed(inner, width - 0.1 * inch, SOFT_BG, pad=14, rule=GOLD))
    story.append(Spacer(1, 0.2 * inch))

    # ---- call to action
    cta = ('<font color="#c9a55a"><b>GET INVOLVED</b></font><br/><br/>'
           '<font color="#cfdcec"><b>Forwarded this?</b> Subscribe to receive Helm &amp; '
           'Horizon every month. <b>Have an outlook of your own?</b> Submit it for the next '
           'edition &mdash; we feature reader perspectives every issue.</font><br/><br/>'
           '<font color="#cfdcec"><a href="%s/subscribe" color="#c9a55a">Subscribe</a>'
           '  ·  <a href="%s/submit" color="#c9a55a">Submit your outlook</a></font>'
           % (SITE, SITE))
    cta_box = boxed(Paragraph(cta, st['cta']), width - 0.1 * inch, NAVY, pad=18)

    # ---- colophon
    foot = ('<b><font color="#cfdcec">Helm &amp; Horizon</font></b> · A monthly market '
            'briefing for yacht industry leaders.<br/>%s<br/>'
            '<i>Companion to the Helm &amp; Horizon web edition, %s &mdash; %s/editions/%s</i>'
            % (esc(flatten(ed.get('colophon') or '', unicode_ok)), esc(ed['month']),
               SITE, ed['slug']))
    # The call to action and the colophon are one navy block in two tones. Glued
    # so the colophon never strands itself alone on a final page.
    story.append(glued([cta_box,
                        boxed(Paragraph(foot, st['footer']), width - 0.1 * inch,
                              DEEP_NAVY, pad=14)],
                       width - 0.1 * inch))
    return story


def wrap_headline(headline, per_line=34):
    """Two banner lines at most; the banner is drawn, so it cannot reflow."""
    words, lines, cur = headline.split(), [], ''
    for w in words:
        if cur and len(cur) + 1 + len(w) > per_line:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w).strip()
    if cur:
        lines.append(cur)
    if len(lines) > 2:
        lines = [lines[0], ' '.join(lines[1:])]
    return lines


def indicator_columns(ed, width, st, unicode_ok):
    """Two navy panels of figures with a risk panel under each."""
    col = (width - 0.1 * inch) / 2

    def panel(region, heading):
        rows = ['• <b>%s</b> %s (%s)' % (
                    rl(i['label'], unicode_ok), rl(i['value'], unicode_ok),
                    '<a href="%s" color="#cfdcec">%s</a>'
                    % (esc(i['source']['url']), rl(i['source'].get('title') or 'source',
                                                   unicode_ok)))
                for i in ed.get('indicators') or [] if i.get('region') == region]
        cells = [Paragraph(heading, st['panel_h']),
                 Paragraph('<br/><br/>'.join(rows), st['panel_body'])]
        return boxed(cells, col - 0.05 * inch, NAVY, pad=11)

    def risk(region):
        r = next((x for x in ed.get('risks') or [] if x.get('region') == region), None)
        if not r:
            return Spacer(1, 0)
        cells = [Paragraph('%s RISKS' % r['title'].upper(), st['risk_label']),
                 Paragraph(rl(r['body'], unicode_ok), st['risk_body'])]
        return boxed(cells, col - 0.05 * inch, WARN_BG, pad=10, border=WARN_BORDER)

    def stack(region, heading):
        return bare([panel(region, heading), Spacer(1, 0.08 * inch), risk(region)],
                    col - 0.05 * inch)

    two = Table([[stack('us', 'UNITED STATES'), stack('global', 'GLOBAL')]],
                colWidths=[col, col])
    two.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (0, 0), 0), ('RIGHTPADDING', (0, 0), (0, 0), 6),
        ('LEFTPADDING', (1, 0), (1, 0), 6), ('RIGHTPADDING', (1, 0), (1, 0), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    return two


# ------------------------------------------------------------------------- main

def render(ed, out, prefer_font=None):
    body, bold, italic, font_name = resolve_fonts(prefer_font)
    unicode_ok = body != 'Helvetica'
    page_w, page_h = LETTER
    margin = 0.5 * inch
    width = page_w - 2 * margin

    doc = SimpleDocTemplate(
        out, pagesize=LETTER,
        leftMargin=margin, rightMargin=margin, topMargin=margin, bottomMargin=margin,
        title='Helm & Horizon — %s (Vol. %d, No. %d)'
              % (ed['month'], ed['volume'], ed['number']),
        author='The Walton Group, Inc.',
        subject=plain(ed['dek']),
    )
    doc.build(build_story(ed, width, make_styles(body, bold, italic),
                          (body, bold, italic), unicode_ok))
    return font_name, unicode_ok


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('edition', nargs='?', help='content/editions/<slug>.json')
    ap.add_argument('--out', help='output path (default: pdf/Helm_Horizon_<Month><Year>.pdf)')
    ap.add_argument('--font', help='prefer a specific family, e.g. "liberation"')
    ap.add_argument('--fonts', action='store_true', help='list what type is available and exit')
    args = ap.parse_args()

    if args.fonts:
        for name, regular, bold, italic in FONT_CANDIDATES:
            have = all(os.path.exists(p) for p in (regular, bold))
            print('%-4s %s' % ('ok' if have else '--', name))
        print('ok   Helvetica (built in, no minus sign or arrow)')
        _b, _bo, _i, chosen = resolve_fonts(args.font)
        print('\nwould use: %s' % chosen)
        return 0

    if not args.edition:
        ap.error('give an edition JSON path (or --fonts)')

    ed = json.load(open(args.edition, encoding='utf-8'))
    out = args.out or os.path.join('pdf', pdf_name(ed['slug']))
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)

    font_name, unicode_ok = render(ed, out)
    print('wrote %s (%d KB)' % (out, round(os.path.getsize(out) / 1024)))
    print('  type          %s' % font_name)
    if not unicode_ok:
        print('  note          no Unicode font found; minus signs and arrows were')
        print('                transliterated so they do not print as boxes')
    return 0


if __name__ == '__main__':
    sys.exit(main())
