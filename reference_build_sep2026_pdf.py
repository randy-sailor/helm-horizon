#!/usr/bin/env python3
"""Build the September 2026 Helm & Horizon newsletter PDF companion."""
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether
)
from reportlab.platypus.flowables import Flowable
import os

FONT_DIR = "/home/user/workspace/fonts"

try:
    pdfmetrics.registerFont(TTFont("Inter", os.path.join(FONT_DIR, "Inter-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Inter-Bold", os.path.join(FONT_DIR, "Inter-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DMSans", os.path.join(FONT_DIR, "DMSans.ttf")))
    pdfmetrics.registerFontFamily(
        "Inter", normal="Inter", bold="Inter-Bold", italic="Inter", boldItalic="Inter-Bold"
    )
    BODY_FONT = "Inter"
    BOLD_FONT = "Inter-Bold"
    HEAD_FONT = "DMSans"
except Exception as e:
    print(f"Font registration warning: {e}")
    BODY_FONT = "Helvetica"
    BOLD_FONT = "Helvetica-Bold"
    HEAD_FONT = "Helvetica-Bold"

NAVY = colors.HexColor("#0b2a4a")
DEEP_NAVY = colors.HexColor("#06192e")
GOLD = colors.HexColor("#c9a55a")
LIGHT_BLUE = colors.HexColor("#cfdcec")
SOFT_BG = colors.HexColor("#f4f7fa")
WARN_BG = colors.HexColor("#fff7e8")
WARN_BORDER = colors.HexColor("#f0d9a8")
WARN_TEXT = colors.HexColor("#5a4410")
WARN_TITLE = colors.HexColor("#8a6212")
TEXT = colors.HexColor("#1a2a3a")
MUTED = colors.HexColor("#5e7186")
LINK = colors.HexColor("#0b5fa5")
DIVIDER = colors.HexColor("#e3e8ee")

OUT_PATH = "/home/user/workspace/cron_tracking/0123b8f1/Helm_Horizon_September2026.pdf"


class HeaderBanner(Flowable):
    def __init__(self, width, height=1.6*inch):
        Flowable.__init__(self)
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        c.setFillColor(NAVY)
        c.rect(0, 0, self.width, self.height, stroke=0, fill=1)
        c.setFillColor(LIGHT_BLUE)
        c.setFont(HEAD_FONT, 9)
        c.drawString(0.3*inch, self.height - 0.35*inch, "HELM  &  HORIZON")
        c.drawRightString(self.width - 0.3*inch, self.height - 0.35*inch,
                          "September 2026  \u00b7  Vol. 1, No. 9")
        c.setFillColor(colors.white)
        c.setFont(HEAD_FONT, 22)
        c.drawString(0.3*inch, self.height - 0.85*inch, "Margins Up, Volumes Down:")
        c.drawString(0.3*inch, self.height - 1.15*inch, "The Second-Half Split Screen")
        c.setStrokeColor(GOLD)
        c.setLineWidth(2)
        c.line(0.3*inch, self.height - 1.4*inch, 1.5*inch, self.height - 1.4*inch)


class SectionLabel(Flowable):
    def __init__(self, label, title, width):
        Flowable.__init__(self)
        self.label = label
        self.title = title
        self.width = width
        self.height = 0.55*inch

    def draw(self):
        c = self.canv
        c.setFillColor(GOLD)
        c.setFont(BOLD_FONT, 8.5)
        c.drawString(0, self.height - 0.2*inch, self.label.upper())
        c.setFillColor(NAVY)
        c.setFont(HEAD_FONT, 17)
        c.drawString(0, self.height - 0.5*inch, self.title)


class Divider(Flowable):
    def __init__(self, width):
        Flowable.__init__(self)
        self.width = width
        self.height = 0.05*inch

    def draw(self):
        self.canv.setStrokeColor(DIVIDER)
        self.canv.setLineWidth(0.5)
        self.canv.line(0, 0, self.width, 0)


styles = {
    "body": ParagraphStyle("body", fontName=BODY_FONT, fontSize=10.5, leading=15.5,
                           textColor=TEXT, spaceAfter=8, alignment=TA_LEFT),
    "feature_title": ParagraphStyle("feature_title", fontName=HEAD_FONT, fontSize=17, leading=21,
                                    textColor=NAVY, spaceAfter=10),
    "callout_label": ParagraphStyle("callout_label", fontName=BOLD_FONT, fontSize=9, leading=11,
                                    textColor=NAVY, spaceAfter=3),
    "callout_body": ParagraphStyle("callout_body", fontName=BODY_FONT, fontSize=10, leading=14,
                                   textColor=TEXT, spaceAfter=2),
    "panel_h": ParagraphStyle("panel_h", fontName=BOLD_FONT, fontSize=10.5, leading=13,
                              textColor=GOLD, spaceAfter=6),
    "risk_label": ParagraphStyle("risk_label", fontName=BOLD_FONT, fontSize=8.5, leading=11,
                                 textColor=WARN_TITLE, spaceAfter=3),
    "risk_body": ParagraphStyle("risk_body", fontName=BODY_FONT, fontSize=9, leading=12.5,
                                textColor=WARN_TEXT),
    "step_n": ParagraphStyle("step_n", fontName=BOLD_FONT, fontSize=22, leading=26,
                             textColor=GOLD, alignment=TA_CENTER),
    "step_title": ParagraphStyle("step_title", fontName=BOLD_FONT, fontSize=11.5, leading=14,
                                 textColor=NAVY, spaceAfter=4),
    "step_body": ParagraphStyle("step_body", fontName=BODY_FONT, fontSize=10, leading=14.5,
                                textColor=TEXT),
    "subtitle": ParagraphStyle("subtitle", fontName=BODY_FONT, fontSize=10, leading=13,
                               textColor=MUTED, spaceAfter=8),
    "footer": ParagraphStyle("footer", fontName=BODY_FONT, fontSize=8.5, leading=11.5,
                             textColor=colors.HexColor("#7e93ac")),
    "voices": ParagraphStyle("voices", fontName=BODY_FONT, fontSize=10, leading=14,
                             textColor=TEXT),
}

LINK_STYLE = 'color="#0b5fa5"'

def link(text, url):
    return f'<a href="{url}" {LINK_STYLE}>{text}</a>'


def build_story(width):
    story = []
    story.append(HeaderBanner(width))
    story.append(Spacer(1, 0.25*inch))

    editor = (
        f'<font name="{BOLD_FONT}">From the desk:</font> Earnings season delivered the '
        'split-screen we expected. MarineMax posted a Q3 revenue miss and a record 35.7% '
        'gross margin (up 530 bps) while confirming Blackstone, Donerail, and Centerbridge '
        'as its three final-round bidders. Brunswick beat top-line, raised full-year guidance '
        'to $4.35-$4.75 EPS on tariff refunds and mix, and now sits on $278M of Q2 free cash '
        'flow. OneWater hit its below-4x leverage target a quarter early on a 4% revenue '
        'decline. The dealer channel is smaller, more premium, and dramatically more '
        'profitable \u2014 the volume tourists have left. Meanwhile the Med charter market '
        'is off 20-30% and Italian Sea Group filed for court-supervised insolvency, drawing '
        'a Sanlorenzo-backed consortium bid. Below: what the earnings tape and the Monaco '
        'run-up mean for your Q4 book.'
    )
    story.append(Paragraph(editor, styles["body"]))
    story.append(Spacer(1, 0.1*inch))

    # Featured Story
    story.append(SectionLabel("Featured Story",
                              "Three Bidders, One Endgame:", width))
    story.append(Paragraph("The MarineMax Auction Enters Final Round",
                           styles["feature_title"]))

    p1 = (
        f'On July 24, Reuters reported that <b>Blackstone, Donerail, and Centerbridge '
        f'Partners</b> have advanced to the third and final round of bidding for MarineMax '
        f'(NYSE: HZO), with Donerail\'s raised all-cash offer of ~$35/share (roughly a '
        f'$1B enterprise value on the equity base) now benchmarking the process '
        f'({link("Reuters", "https://www.reuters.com/business/blackstone-donerail-among-final-bidders-yacht-retailer-marinemax-sources-say-2026-07-24/")}). '
        f'Shares jumped 6.5% on the report to close near $36.41 '
        f'({link("Tampa Bay Business Journal via ITA", "https://itayachtscanada.com/marinemax-announces-third-quarter-q3-earnings-and-an-update-on-the-potential-sale-of-the-marinemax-group-to-three-prospective-buyers/")}). '
        f'Blackstone\'s interest reads through directly from its 2025 <b>$5.65B Safe Harbor '
        f'acquisition</b>: MarineMax\'s IGY Marinas and 65 owned marina and storage locations '
        f'are the strategic prize '
        f'({link("SuperYacht Times", "https://www.facebook.com/SuperYachtTimes/posts/blackstone-and-donerail-are-reportedly-among-the-final-bidders-for-marinemaxaccording-to-reuters-th/1588618659298167/")}).'
    )
    p2 = (
        f'The July 23 Q3 print made the case for a premium. Revenue of <b>$611.3M missed '
        f'consensus by ~$71M</b>, but gross margin expanded <b>530 basis points to a record '
        f'35.7%</b>, adjusted EBITDA jumped <b>44% to $51.3M</b>, and adjusted EPS surged to '
        f'<b>$0.81 from $0.05</b> '
        f'({link("Yahoo Finance / Quartr", "https://finance.yahoo.com/quote/HZO/earnings/HZO-Q3-2026-earnings_call-653690.html")}). '
        f'Management reaffirmed FY26 adjusted EBITDA of <b>$110-125M</b> and adjusted EPS of '
        f'<b>$0.40-$0.95</b>, and disclosed that acquisitions since 2019 have added '
        f'<b>$700M of high-margin revenue</b> \u2014 brokerage, F&amp;I, marinas, superyachts, '
        f'and parts &amp; service '
        f'({link("Quartr Q3 summary", "https://quartr.com/events/marinemax-inc-hzo-q3-2026_3siVEb7h")}). '
        f'Inventory is down $118M year-over-year to $788.6M; cash is $174.8M '
        f'({link("TradingView / 8-K", "https://www.tradingview.com/news/tradingview:57b1b553a043e:0-marinemax-reports-q3-fiscal-2026-revenue-611-3m-gross-margin-35-7-adj-diluted-eps-0-81/")}). '
        f'Bidders are buying a cleaner balance sheet, a higher-margin business mix, and a '
        f'marina platform that acts like a moat.'
    )
    p3 = (
        f'<b>The read for dealers and brokers:</b> whoever wins, the model is validated '
        f'\u2014 dealer economics survive a down cycle only if brokerage, service, marinas, '
        f'and superyachts carry the P&amp;L while new-boat volumes correct. Every MarineMax '
        f'competitor now has to answer the same question in its own board deck: what is your '
        f'non-new-boat gross-profit share, and where can it be next year? Meanwhile, at the '
        f'builder tier, <b>The Italian Sea Group filed for court-supervised insolvency</b>, '
        f'and a Sanlorenzo-led consortium (Polo Nautico Carrara) has submitted a debt-free, '
        f'going-concern bid for the Admiral, Tecnomar, and Perini Navi brands, with '
        f'Azimut-Benetti also circling select assets '
        f'({link("Reuters", "https://www.reuters.com/business/italys-sanlorenzo-backs-bid-embattled-yacht-maker-italian-sea-group-2026-07-27/")}). '
        f'The consolidation wave has crossed from dealer to builder.'
    )
    story.append(Paragraph(p1, styles["body"]))
    story.append(Paragraph(p2, styles["body"]))
    story.append(Paragraph(p3, styles["body"]))

    takeaway_inner = [
        [Paragraph("KEY TAKEAWAY", styles["callout_label"])],
        [Paragraph(
            "The Q2/Q3 earnings tape validates a two-track model: volumes down (HZO SSS -7%, "
            "ONEW -4%, NMMA -7.1% rolling 12-mo) but margins and cash flow up. That gap only "
            "widens for dealers heavy in brokerage, F&amp;I, marinas, and service. Independent "
            "operators still running a 2022-era new-boat-first P&amp;L will find both financing "
            "and exit valuations increasingly hostile as the HZO comp lands in Q4.",
            styles["callout_body"])]
    ]
    takeaway = Table(takeaway_inner, colWidths=[width - 0.1*inch])
    takeaway.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SOFT_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(Spacer(1, 0.05*inch))
    story.append(takeaway)
    story.append(Spacer(1, 0.2*inch))
    story.append(Divider(width))
    story.append(Spacer(1, 0.15*inch))

    # Indicators
    story.append(SectionLabel("Economic Indicators & Risk", "By the Numbers", width))
    story.append(Spacer(1, 0.1*inch))

    us_text = (
        f'\u2022 HZO Q3: revenue <b>$611.3M (-7%)</b>, GM <b>35.7% (+530 bps)</b>, adj '
        f'EBITDA <b>$51.3M (+44%)</b>, adj EPS <b>$0.81</b> '
        f'({link("Yahoo", "https://finance.yahoo.com/markets/stocks/articles/marinemax-inc-hzo-q3-2026-210330404.html")})<br/><br/>'
        f'\u2022 Brunswick Q2: net sales <b>$1.558B (+8%)</b>, adj EPS <b>$1.56 (+34%)</b>, '
        f'FY guide raised to <b>$4.35-$4.75</b> EPS '
        f'({link("Investing.com", "https://www.investing.com/news/company-news/brunswick-q2-2026-slides-all-segments-grow-guidance-raised-93CH-4825713")})<br/><br/>'
        f'\u2022 OneWater Q3: revenue <b>$530.7M (-4%)</b>, GM <b>24.0% (+70 bps)</b>, adj '
        f'net leverage <b>3.7x</b> (below 4x target) '
        f'({link("MarketBeat", "https://www.marketbeat.com/instant-alerts/onewater-marine-q3-earnings-call-highlights-2026-07-30/")})<br/><br/>'
        f'\u2022 NMMA rolling 12-mo new powerboat retail <b>-7.1%</b> to 214,292 units through '
        f'April '
        f'({link("Marine Business World", "https://www.marinebusinessworld.com/news/298024/Mixed-sales-data-from-latest-industry-association")})<br/><br/>'
        f'\u2022 US recreational marine spending totaled <b>$54B in 2025</b>; pre-owned = '
        f'79.7% of unit sales '
        f'({link("Boating Industry Canada / NMMA", "https://boatingindustry.ca/research/nmma-reports-that-u-s-recreational-marine-spending-reached-54-billion-in-2025/")})'
    )
    us_panel = Table(
        [[Paragraph("UNITED STATES", styles["panel_h"])],
         [Paragraph(us_text, ParagraphStyle("us", fontName=BODY_FONT, fontSize=9.3,
                                             leading=13.5, textColor=colors.white))]],
        colWidths=[3.4*inch]
    )
    us_panel.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))

    global_text = (
        f'\u2022 <b>2,157 pre-owned yachts &gt;24m</b> on the market July 1, ~$18.8B asking '
        f'value '
        f'({link("365 Yachts Intelligence", "https://www.linkedin.com/pulse/365-yachts-market-intelligence-august-1-2026-update-shelly-melcher-7klje")})<br/><br/>'
        f'\u2022 Edmiston H1 2026: superyacht sales <b>-13% by units</b>, <b>-7% by value</b>'
        f' \u2014 quality-over-quantity market '
        f'({link("Edmiston", "https://www.edmiston.com/Q2-2026-market-update/")})<br/><br/>'
        f'\u2022 Med charter rates down <b>20-30% YoY</b>; unusually high inventory on French '
        f'Riviera, Amalfi, Greek Isles '
        f'({link("CNBC", "https://www.cnbc.com/2026/07/22/mediterranean-yacht-rentals.html")})<br/><br/>'
        f'\u2022 Booking lead times <b>118 days (2025) \u2192 83 days (2026)</b>, -30% YoY '
        f'({link("Lisbon by Boat", "https://www.lisbonbyboat.com/post/tourism-trends-for-sailing-2026-what-to-expect")})<br/><br/>'
        f'\u2022 Monaco Yacht Show Sept 23-26: <b>~120 yachts expected</b>, 43 newly delivered '
        f'({link("Boat International", "https://www.boatinternational.com/yachts/news/biggest-yachting-news-stories-july-2026")})<br/><br/>'
        f'\u2022 Fed held benchmark rate <b>3.50-3.75%</b> at end of July '
        f'({link("365 Yachts", "https://www.linkedin.com/pulse/365-yachts-market-intelligence-august-1-2026-update-shelly-melcher-7klje")})'
    )
    global_panel = Table(
        [[Paragraph("GLOBAL", styles["panel_h"])],
         [Paragraph(global_text, ParagraphStyle("gl", fontName=BODY_FONT, fontSize=9.3,
                                                 leading=13.5, textColor=colors.white))]],
        colWidths=[3.4*inch]
    )
    global_panel.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))

    us_risk = Table(
        [[Paragraph("US RISKS", styles["risk_label"])],
         [Paragraph("Florida brokerage: 4,316 active listings July 24; median asking $349,995; "
                    "100+ ft segment median $7.4M and $61,600 per foot. Hurricane season now "
                    "in peak window as HZO sale decision approaches; consensus-view exit "
                    "multiple resets industry-wide when the deal announces.",
                    styles["risk_body"])]],
        colWidths=[3.4*inch]
    )
    us_risk.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WARN_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, WARN_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    global_risk = Table(
        [[Paragraph("GLOBAL RISKS", styles["risk_label"])],
         [Paragraph("EU27 diesel hit EUR 1.929/L July 16 (+18% vs Feb baseline); Russia diesel "
                    "export ban July 8-31 tightened supply; MGO in ARA up 73.5% since Feb. "
                    "Hormuz war-risk 5-10% of hull value; London JWC widened Red Sea high-risk "
                    "zone July 29; Bab el-Mandeb premiums doubled to 1%+.",
                    styles["risk_body"])]],
        colWidths=[3.4*inch]
    )
    global_risk.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WARN_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, WARN_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    us_stack = Table([[us_panel], [Spacer(1, 0.08*inch)], [us_risk]], colWidths=[3.4*inch])
    us_stack.setStyle(TableStyle([("LEFTPADDING", (0,0), (-1,-1), 0),
                                   ("RIGHTPADDING", (0,0), (-1,-1), 0),
                                   ("TOPPADDING", (0,0), (-1,-1), 0),
                                   ("BOTTOMPADDING", (0,0), (-1,-1), 0)]))
    global_stack = Table([[global_panel], [Spacer(1, 0.08*inch)], [global_risk]],
                         colWidths=[3.4*inch])
    global_stack.setStyle(TableStyle([("LEFTPADDING", (0,0), (-1,-1), 0),
                                       ("RIGHTPADDING", (0,0), (-1,-1), 0),
                                       ("TOPPADDING", (0,0), (-1,-1), 0),
                                       ("BOTTOMPADDING", (0,0), (-1,-1), 0)]))

    two_col = Table([[us_stack, global_stack]], colWidths=[3.5*inch, 3.5*inch])
    two_col.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(two_col)
    story.append(Spacer(1, 0.2*inch))

    story.append(PageBreak())

    # Action steps
    story.append(SectionLabel("Three Action Steps", "What to Do This Quarter", width))
    story.append(Spacer(1, 0.15*inch))

    steps = [
        ("1", "Run the HZO playbook on your own P&L before year-end.",
         "MarineMax's Q3 didn't beat because boats sold \u2014 same-store sales were down 7%. "
         "It beat because brokerage, F&amp;I, marinas, superyachts, and parts &amp; service now "
         "carry the gross profit. Break out your last-twelve-month gross profit by revenue line "
         "and mark the non-new-boat share. If it is below 40%, you are running a 2022 business "
         "model in a 2026 market. Set a written FY27 target \u2014 the multiple your business "
         "is worth in a sale conversation will move with that ratio far more than with unit "
         "volume."),
        ("2", "Move charter cross-currency exposure to the front of the risk register.",
         "With EU diesel back at EUR 1.93/litre and MGO up 73.5% since February, a Med charter "
         "contract priced in EUR against a USD-cost book \u2014 provisioning, US-based crew "
         "payroll, delivery voyage fuel \u2014 is now materially different from what your APA "
         "assumed in April. Requote every August-October Med charter with a fresh fuel "
         "assumption, an FX buffer of 300-500 bps, and an explicit clause for Red Sea / Hormuz "
         "war-risk surcharge pass-through. Owners will accept honest math; they will not accept "
         "surprise APA overruns."),
        ("3", "Book Monaco with a builder-services agenda, not a boat-shopping agenda.",
         "Monaco Yacht Show runs September 23-26, with ~120 yachts and 43 new deliveries "
         "expected \u2014 but the real story on the pontoons will be builder distress. With "
         "Italian Sea Group in insolvency proceedings and a Sanlorenzo-led consortium bidding, "
         "refit, warranty, and completion questions will drive more meaningful conversations "
         "than new orders. Come with a list: which builders have open orders on which of your "
         "clients' hulls, which yards have credible completion risk, and which service "
         "providers you can extend a preferred-vendor relationship to before demand snaps. The "
         "best Monaco value this year is in the yards, not the demo boats."),
    ]
    for num, title, body in steps:
        circle = Table([[Paragraph(num, styles["step_n"])]],
                       colWidths=[0.55*inch], rowHeights=[0.55*inch])
        circle.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        text_cell = [
            Paragraph(title, styles["step_title"]),
            Paragraph(body, styles["step_body"]),
        ]
        row = Table([[circle, text_cell]], colWidths=[0.75*inch, width - 0.75*inch])
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (1, 0), (1, 0), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(KeepTogether([row, Spacer(1, 0.18*inch)]))

    story.append(Spacer(1, 0.1*inch))
    story.append(Divider(width))
    story.append(Spacer(1, 0.18*inch))

    # Player profile
    story.append(SectionLabel("Industry Player Profile", "Brunswick Corporation (NYSE: BC)", width))
    story.append(Paragraph(
        "<i>The propulsion, parts, and Freedom Boat Club engine that keeps printing through "
        "the volume trough.</i>",
        styles["subtitle"]))

    profile_p1 = (
        f'Headquartered in Mettawa, Illinois, Brunswick is the world\'s largest marine-'
        f'recreation manufacturer \u2014 Mercury Marine propulsion, Boston Whaler, Sea Ray, '
        f'Bayliner, Lund, Harris, Navico Group electronics, plus the Freedom Boat Club '
        f'shared-access platform. On July 30, BC reported Q2 net sales of <b>$1.558B (+8%)</b>, '
        f'adjusted operating earnings of $150.1M (+19%), adjusted EPS of <b>$1.56 (+34%)</b>, '
        f'and Q2 free cash flow of $278M with conversion &gt;250% '
        f'({link("Investing.com", "https://www.investing.com/news/company-news/brunswick-q2-2026-slides-all-segments-grow-guidance-raised-93CH-4825713")}). '
        f'All four segments grew year-over-year for the fourth consecutive quarter. Propulsion '
        f'posted $644M (+8%), Engine Parts &amp; Accessories $367.9M (+9%) with 23.3% '
        f'operating margin, Navico $215.8M (+7%), Boat $424.4M (+5%) '
        f'({link("Stock Titan / 8-K", "https://www.stocktitan.net/sec-filings/BC/8-k-brunswick-corp-reports-material-event-df9545f8bacc.html")}).'
    )
    profile_p2 = (
        f'<b>Why it matters now:</b> Brunswick raised its FY26 guide to <b>$5.7-5.8B in '
        f'revenue, ~8% operating margin, $4.35-$4.75 adjusted EPS, and $400M+ free cash flow</b> '
        f'({link("Brunswick IR", "https://www.brunswick.com/news/press-releases/detail/1003/brunswick-corporation-releases-2026-second-quarter-earnings")}). '
        f'Roughly $0.30 of the raise reflects Phase 2 IEEPA tariff refunds ($30.4M cost-of-'
        f'sales credit plus a $24.6M state tax benefit); the other $0.20 is operational. '
        f'Freedom Boat Club hit its <b>450th location</b> in June, converting new-boat volume '
        f'softness into recurring-revenue membership economics. Brunswick is a real-time '
        f'barometer of the marine channel: parts &amp; accessories signal what fleets are '
        f'actually running, propulsion signals OEM confidence, and Freedom signals what '
        f'happens to would-be first-time buyers when new-boat affordability breaks.'
    )
    profile_p3 = (
        f'<b>Watch for:</b> Q3 guide of $1.4-1.5B revenue and $1.20-$1.40 adjusted EPS (about '
        f'a 15% top-line step-down vs Q2, in line with normal seasonality), the trajectory of '
        f'Navico\'s autonomy and lower-cost sensor stack, and whether Freedom Boat Club\'s '
        f'international footprint (now well over 100 non-US clubs) keeps outpacing its US '
        f'comps.'
    )
    profile_body = [
        Paragraph(profile_p1, styles["body"]),
        Paragraph(profile_p2, styles["body"]),
        Paragraph(profile_p3, styles["body"]),
    ]
    profile_box = Table([[profile_body]], colWidths=[width - 0.1*inch])
    profile_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SOFT_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(profile_box)
    story.append(Spacer(1, 0.2*inch))
    story.append(Divider(width))
    story.append(Spacer(1, 0.15*inch))

    # Voices from the Field
    story.append(SectionLabel("Voices from the Field", "Reader Submissions", width))
    voices_text = (
        '<i>This section runs reader-submitted outlooks from brokers, dealers, builders, '
        'captains, and supply-chain partners. Q2 earnings from HZO, BC, and ONEW confirmed '
        'the two-track market \u2014 record margins on shrinking volumes \u2014 but the '
        'on-the-water color is where the next-quarter shift usually shows up first. Send us '
        'what you\'re seeing on the Monaco run-in, on used inventory absorption, on charter '
        'reprice negotiations, and on refit-yard capacity. One quote per issue gets the lead '
        'position, and we run through October.</i><br/><br/>'
        '\u2014 The Helm &amp; Horizon editors'
    )
    voices_box = Table([[Paragraph(voices_text, styles["voices"])]],
                       colWidths=[width - 0.1*inch])
    voices_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SOFT_BG),
        ("LINEBEFORE", (0, 0), (0, -1), 3, GOLD),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(voices_box)
    story.append(Spacer(1, 0.2*inch))

    # Closing CTA
    cta_text = (
        '<font color="#c9a55a"><b>GET INVOLVED</b></font><br/><br/>'
        '<font color="#cfdcec"><b>Forwarded this?</b> Subscribe to receive Helm &amp; Horizon '
        'every month. <b>Have an outlook of your own?</b> Submit it for the next edition \u2014 '
        'we feature reader perspectives every issue.</font><br/><br/>'
        f'<font color="#cfdcec">{link("Subscribe", "https://docs.google.com/forms/d/e/1FAIpQLSfNSSENINyRWBQhOscZ9ec2uafQn3MhvPs1DFpDIxL6YdTxpQ/viewform")}'
        f'  \u00b7  {link("Submit Your Outlook", "https://docs.google.com/forms/d/e/1FAIpQLSeBD8cdX4-ZHT2qtRUwkY6ovXm9FhzJDSFyhgvuiX_3u5Uo0g/viewform")}</font>'
    )
    cta = Table([[Paragraph(cta_text, ParagraphStyle("cta", fontName=BODY_FONT, fontSize=10.5,
                                                     leading=15, textColor=colors.white))]],
                colWidths=[width - 0.1*inch])
    cta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 18),
        ("RIGHTPADDING", (0, 0), (-1, -1), 18),
        ("TOPPADDING", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
    ]))
    story.append(cta)
    story.append(Spacer(1, 0.1*inch))

    footer_text = (
        '<b><font color="#cfdcec">Helm &amp; Horizon</font></b> \u00b7 A monthly market '
        'briefing for yacht industry leaders.<br/>'
        'Sources cited inline with clickable URLs. Data as of late July / early August 2026. '
        'Not investment advice.<br/>'
        '<i>Companion to the Helm &amp; Horizon email edition, September 2026.</i>'
    )
    footer = Table([[Paragraph(footer_text, styles["footer"])]], colWidths=[width - 0.1*inch])
    footer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DEEP_NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 18),
        ("RIGHTPADDING", (0, 0), (-1, -1), 18),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(footer)
    return story


def build_pdf():
    page_w, page_h = LETTER
    margin = 0.5 * inch
    content_w = page_w - 2 * margin

    doc = SimpleDocTemplate(
        OUT_PATH,
        pagesize=LETTER,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
        title="Helm & Horizon \u2014 September 2026 (Vol. 1, No. 9)",
        author="Perplexity Computer",
        subject="Helm & Horizon Newsletter",
    )
    story = build_story(content_w)
    doc.build(story)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    build_pdf()
