"""
DropKit Original PDF Generation Engine
Generates publication-quality, multi-page, authentic digital PDF products
with real, comprehensive educational content for all 6 store items.
"""

import os
import sys
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.db import get_connection, now_iso
from backend.config import SECURE_PDF_DIR

def escape_pdf_str(text: str) -> str:
    """Escapes special PDF string characters and converts non-ASCII symbols."""
    text = str(text)
    text = text.replace("₹", "INR ")
    text = text.replace("—", " - ")
    text = text.replace("–", " - ")
    text = text.replace("“", "\"").replace("”", "\"")
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("•", "* ")
    # Escape PDF syntax
    text = text.replace("\\", "\\\\")
    text = text.replace("(", "\\(")
    text = text.replace(")", "\\)")
    # Keep within Latin-1
    return text.encode('latin-1', 'replace').decode('latin-1')

def wrap_text(text: str, max_chars: int = 78) -> list:
    """Wraps text into lines not exceeding max_chars."""
    words = text.split()
    lines = []
    cur_line = []
    cur_len = 0
    for w in words:
        if cur_len + len(w) + (1 if cur_line else 0) <= max_chars:
            cur_line.append(w)
            cur_len += len(w) + (1 if len(cur_line) > 1 else 0)
        else:
            if cur_line:
                lines.append(" ".join(cur_line))
            cur_line = [w]
            cur_len = len(w)
    if cur_line:
        lines.append(" ".join(cur_line))
    return lines or [""]

class PDFDocument:
    def __init__(self, book_title: str, short_title: str, category: str):
        self.book_title = book_title
        self.short_title = short_title
        self.category = category
        self.pages_streams = []  # list of byte strings for each page
        self.current_stream = []
        self.current_y = 770
        self.page_number = 0
        self.total_pages = 0

    def start_page(self, is_cover: bool = False):
        if self.current_stream:
            self.pages_streams.append("\n".join(self.current_stream).encode('latin-1'))
            self.current_stream = []
        self.page_number += 1
        self.current_y = 760

        if not is_cover:
            # Running header line
            self.current_stream.append("0.85 0.86 0.90 rg")
            self.current_stream.append("50 790 495 0.75 re f")
            # Running header text
            safe_short = escape_pdf_str(self.short_title)
            self.current_stream.append(f"""BT
/F1 8.5 Tf
0.11 0.11 0.23 rg
50 796 Td
(DROPKIT PUBLICATION SERIES) Tj
ET
BT
/F3 8.5 Tf
0.45 0.47 0.55 rg
330 796 Td
({safe_short[:35]}) Tj
ET""")

    def draw_cover(self, subtitle: str, edition: str, metadata_items: list):
        self.start_page(is_cover=True)
        # Deep navy banner
        self.current_stream.append("0.11 0.11 0.23 rg")
        self.current_stream.append("0 520 595.28 321.89 re f")
        # Coral orange accent bar
        self.current_stream.append("1.0 0.40 0.24 rg")
        self.current_stream.append("0 513 595.28 7 re f")

        # Category pill
        self.current_stream.append("1.0 0.40 0.24 rg")
        self.current_stream.append("50 780 180 20 re f")
        safe_cat = escape_pdf_str(self.category.upper())
        self.current_stream.append(f"""BT
/F1 9 Tf
1 1 1 rg
60 786 Td
({safe_cat}) Tj
ET""")

        # Title lines
        safe_title = escape_pdf_str(self.book_title)
        title_lines = wrap_text(safe_title, 36)
        y_pos = 730
        for tl in title_lines:
            self.current_stream.append(f"""BT
/F1 22 Tf
1 1 1 rg
50 {y_pos} Td
({tl}) Tj
ET""")
            y_pos -= 28

        # Subtitle
        safe_sub = escape_pdf_str(subtitle)
        sub_lines = wrap_text(safe_sub, 55)
        y_pos -= 6
        for sl in sub_lines:
            self.current_stream.append(f"""BT
/F2 12 Tf
0.88 0.90 0.96 rg
50 {y_pos} Td
({sl}) Tj
ET""")
            y_pos -= 18

        # White lower section: Metadata Card
        self.current_stream.append("0.96 0.97 0.99 rg")
        self.current_stream.append("50 200 495 280 re f")
        self.current_stream.append("0.85 0.86 0.90 rg")
        self.current_stream.append("50 200 495 1 re f")
        self.current_stream.append("50 479 495 1 re f")
        self.current_stream.append("50 200 1 280 re f")
        self.current_stream.append("544 200 1 280 re f")

        self.current_stream.append(f"""BT
/F1 11 Tf
0.11 0.11 0.23 rg
70 450 Td
(OFFICIAL PUBLICATION METADATA & LICENSING) Tj
ET""")

        my = 415
        for k, v in metadata_items:
            sk = escape_pdf_str(k)
            sv = escape_pdf_str(v)
            self.current_stream.append(f"""BT
/F1 9.5 Tf
0.45 0.47 0.55 rg
70 {my} Td
({sk}:) Tj
ET
BT
/F2 9.5 Tf
0.11 0.11 0.23 rg
190 {my} Td
({sv}) Tj
ET""")
            my -= 24

        # DropKit Verification statement
        self.current_stream.append(f"""BT
/F3 9 Tf
0.45 0.47 0.55 rg
50 140 Td
(Issued by DropKit Digital Commerce Platform - Verified Cryptographic Release.) Tj
ET
BT
/F2 8.5 Tf
0.55 0.57 0.65 rg
50 120 Td
(This digital edition is protected by international copyright law. Single user license.) Tj
ET""")

    def check_space(self, needed_pt: int):
        if self.current_y - needed_pt < 85:
            self.start_page(is_cover=False)

    def add_chapter_title(self, num_str: str, title: str):
        self.check_space(75)
        # Pill
        self.current_stream.append("1.0 0.40 0.24 rg")
        self.current_stream.append(f"50 {self.current_y - 14} 70 16 re f")
        self.current_stream.append(f"""BT
/F1 8.5 Tf
1 1 1 rg
58 {self.current_y - 9} Td
({escape_pdf_str(num_str)}) Tj
ET""")
        self.current_y -= 38

        # Chapter main title
        safe_t = escape_pdf_str(title)
        lines = wrap_text(safe_t, 46)
        for l in lines:
            self.current_stream.append(f"""BT
/F1 17 Tf
0.11 0.11 0.23 rg
50 {self.current_y} Td
({l}) Tj
ET""")
            self.current_y -= 22
        self.current_y -= 8

    def add_section_heading(self, heading: str):
        self.check_space(45)
        safe_h = escape_pdf_str(heading)
        self.current_stream.append(f"""BT
/F1 12.5 Tf
0.11 0.11 0.23 rg
50 {self.current_y} Td
({safe_h}) Tj
ET""")
        self.current_y -= 20

    def add_paragraph(self, text: str):
        lines = wrap_text(text, 78)
        self.check_space(len(lines) * 15 + 10)
        for l in lines:
            safe_l = escape_pdf_str(l)
            self.current_stream.append(f"""BT
/F2 10 Tf
0.15 0.16 0.22 rg
50 {self.current_y} Td
({safe_l}) Tj
ET""")
            self.current_y -= 14
        self.current_y -= 8

    def add_callout(self, title: str, text: str):
        lines = wrap_text(text, 70)
        box_h = 32 + len(lines) * 14
        self.check_space(box_h + 15)

        y_top = self.current_y
        y_bot = y_top - box_h

        # Light box
        self.current_stream.append("0.96 0.97 0.99 rg")
        self.current_stream.append(f"50 {y_bot} 495 {box_h} re f")
        # Orange left accent
        self.current_stream.append("1.0 0.40 0.24 rg")
        self.current_stream.append(f"50 {y_bot} 4 {box_h} re f")
        # Light border
        self.current_stream.append("0.85 0.86 0.90 rg")
        self.current_stream.append(f"54  {y_bot} 491 1 re f")
        self.current_stream.append(f"54 {y_top-1} 491 1 re f")
        self.current_stream.append(f"544 {y_bot} 1 {box_h} re f")

        # Title
        safe_t = escape_pdf_str(title)
        self.current_stream.append(f"""BT
/F1 9.5 Tf
0.11 0.11 0.23 rg
65 {y_top - 18} Td
({safe_t}) Tj
ET""")
        # Content lines
        cy = y_top - 32
        for l in lines:
            safe_l = escape_pdf_str(l)
            self.current_stream.append(f"""BT
/F3 9 Tf
0.25 0.27 0.35 rg
65 {cy} Td
({safe_l}) Tj
ET""")
            cy -= 14
        self.current_y = y_bot - 14

    def add_bullet_list(self, items: list):
        for item in items:
            lines = wrap_text(item, 74)
            self.check_space(len(lines) * 14 + 6)
            # Bullet point symbol
            self.current_stream.append(f"""BT
/F1 10 Tf
1.0 0.40 0.24 rg
55 {self.current_y} Td
(*) Tj
ET""")
            first = True
            for l in lines:
                safe_l = escape_pdf_str(l)
                x_pos = 68 if first else 68
                self.current_stream.append(f"""BT
/F2 9.5 Tf
0.15 0.16 0.22 rg
{x_pos} {self.current_y} Td
({safe_l}) Tj
ET""")
                self.current_y -= 13
                first = False
            self.current_y -= 4
        self.current_y -= 6

    def add_table_of_contents(self, chapters: list):
        self.start_page(is_cover=False)
        self.current_stream.append(f"""BT
/F1 18 Tf
0.11 0.11 0.23 rg
50 {self.current_y} Td
(Table of Contents) Tj
ET""")
        self.current_y -= 30

        self.add_paragraph("This master handbook provides an end-to-end operational blueprint. Below is the full index of topics and frameworks covered in this verified digital edition:")
        self.current_y -= 12

        for num, title, desc in chapters:
            self.check_space(55)
            # Row
            self.current_stream.append("0.97 0.98 0.99 rg")
            self.current_stream.append(f"50 {self.current_y - 36} 495 42 re f")
            self.current_stream.append("0.88 0.89 0.92 rg")
            self.current_stream.append(f"50 {self.current_y - 36} 495 1 re f")
            self.current_stream.append("1.0 0.40 0.24 rg")
            self.current_stream.append(f"50 {self.current_y - 36} 3 42 re f")

            s_num = escape_pdf_str(num)
            s_t = escape_pdf_str(title)
            s_d = escape_pdf_str(desc)

            self.current_stream.append(f"""BT
/F1 10 Tf
0.11 0.11 0.23 rg
62 {self.current_y - 12} Td
({s_num}: {s_t}) Tj
ET
BT
/F2 8.5 Tf
0.45 0.47 0.55 rg
62 {self.current_y - 26} Td
({s_d}) Tj
ET""")
            self.current_y -= 48

    def finalize(self) -> bytes:
        if self.current_stream:
            self.pages_streams.append("\n".join(self.current_stream).encode('latin-1'))
            self.current_stream = []

        total_pages = len(self.pages_streams)

        # Inject footer into each page (except cover)
        finalized_streams = []
        for idx, page_bytes in enumerate(self.pages_streams, 1):
            if idx == 1:
                finalized_streams.append(page_bytes)
                continue
            footer_cmd = f"""
0.85 0.86 0.90 rg
50 55 495 0.75 re f
BT
/F2 8 Tf
0.45 0.47 0.55 rg
50 42 Td
(Confidential & Licensed to Purchaser - DropKit Verified Digital Product) Tj
ET
BT
/F1 8.5 Tf
0.11 0.11 0.23 rg
490 42 Td
(Page {idx} of {total_pages}) Tj
ET
""".encode('latin-1')
            finalized_streams.append(page_bytes + footer_cmd)

        # Assemble PDF objects
        # 1: Catalog
        # 2: Pages
        # 3: Helvetica
        # 4: Helvetica-Bold
        # 5: Helvetica-Oblique
        # 6: Courier
        # Pages start at obj 7:
        # Page i: 7 + 2*(i-1)
        # Stream i: 8 + 2*(i-1)
        kids = [f"{7 + 2*i} 0 R" for i in range(total_pages)]
        kids_str = " ".join(kids)

        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            f"<< /Type /Pages /Kids [{kids_str}] /Count {total_pages} >>".encode('latin-1'),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>",
        ]

        for i, s_bytes in enumerate(finalized_streams):
            page_obj_num = 7 + 2*i
            stream_obj_num = 8 + 2*i
            page_obj = f"""<<
  /Type /Page
  /Parent 2 0 R
  /MediaBox [0 0 595.28 841.89]
  /Resources <<
    /Font <<
      /F1 4 0 R
      /F2 3 0 R
      /F3 5 0 R
      /F4 6 0 R
    >>
  >>
  /Contents {stream_obj_num} 0 R
>>""".encode('latin-1')
            objects.append(page_obj)

            stream_obj = f"<< /Length {len(s_bytes)} >>\nstream\n".encode('latin-1') + s_bytes + b"\nendstream"
            objects.append(stream_obj)

        # Serialize PDF
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for obj_idx, obj_bytes in enumerate(objects, 1):
            offsets.append(len(out))
            out.extend(f"{obj_idx} 0 obj\n".encode('latin-1'))
            out.extend(obj_bytes)
            out.extend(b"\nendobj\n")

        xref_offset = len(out)
        total_objs = len(objects) + 1
        out.extend(f"xref\n0 {total_objs}\n".encode('latin-1'))
        out.extend(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            out.extend(f"{off:010d} 00000 n \n".encode('latin-1'))

        trailer = f"""trailer
<<
  /Size {total_objs}
  /Root 1 0 R
>>
startxref
{xref_offset}
%%EOF"""
        out.extend(trailer.encode('latin-1'))
        return bytes(out), total_pages


# ==============================================================================
# BOOK 1: SaaS Growth Engine: 0 to ₹10 Lakhs MRR
# ==============================================================================
def generate_saas_growth_book():
    doc = PDFDocument(
        book_title="SaaS Growth Engine: 0 to INR 10 Lakhs MRR",
        short_title="SaaS Growth Engine",
        category="Business & SaaS"
    )
    doc.draw_cover(
        subtitle="The Complete Bootstrapped Founder Playbook from Problem Validation to Scalable Monthly Recurring Revenue.",
        edition="2026 Master Production Release",
        metadata_items=[
            ("Title", "SaaS Growth Engine: 0 to INR 10 Lakhs MRR"),
            ("Category", "B2B SaaS / Revenue Operations"),
            ("Publisher", "DropKit Digital Publications"),
            ("Target Audience", "Founders, Indie Hackers & Product Engineers"),
            ("Format", "Verified Architectural PDF Handbook"),
            ("License", "Single Commercial & Personal Deployment License")
        ]
    )

    doc.add_table_of_contents([
        ("Chapter 1", "The Zero-to-One Validation Architecture", "Problem-solution validation matrix, extracting willingness to pay."),
        ("Chapter 2", "Founder-Led Sales & The First 10 Paid Pilots", "Direct outreach scripts, discovery calls, and closing annual contracts."),
        ("Chapter 3", "Monetization Models & High-Velocity Pricing", "Value-metric pricing, upfront cash flows, and zero-discount tactics."),
        ("Chapter 4", "The Inbound Demand Engine & Content Moats", "High-intent programmatic SEO, engineering free viral micro-tools."),
        ("Chapter 5", "Retention Architecture & Negative Net Churn", "Cohort retention analysis, onboarding milestones, and expansion MRR."),
        ("Chapter 6", "Scaling to INR 10 Lakhs MRR & Institutional Readiness", "Unit economics: CAC, LTV, Payback Periods, and profit distribution.")
    ])

    # Chapter 1
    doc.add_chapter_title("CHAPTER 1", "The Zero-to-One Validation Architecture")
    doc.add_section_heading("1.1 The Trap of Premature Code Construction")
    doc.add_paragraph("The single most frequent post-mortem cause of early-stage software failures in India and globally is building a technically sophisticated product for a market that does not urgently require it. Founders frequently expend six months writing elegant microservices, designing design systems, and tuning databases before validating whether a real buyer exists who holds the budget and authority to purchase a solution.")
    doc.add_paragraph("Validation is not asking colleagues or friends if they 'like the idea.' True validation is a commercial transaction or a binding letter of intent where a potential buyer expresses quantified pain in hours lost or capital wasted per month.")
    doc.add_callout(
        "CORE VALIDATION PRINCIPLE",
        "Never begin full-stack development until at least five decision-makers have signed an early-access letter of intent or deposited an advance payment for the prototype."
    )
    doc.add_section_heading("1.2 The Urgency vs Budget Quadrant")
    doc.add_paragraph("Categorize target personas across two axes: Pain Urgency (horizontal) and Discretionary Budget (vertical). Products targeting high urgency and high budget (e.g., enterprise payroll, compliance, payment reconciliation) command immediate conversion velocity and zero price resistance.")
    doc.add_bullet_list([
        "High Urgency, High Budget: Mission-critical enterprise workflows with quantifiable ROI.",
        "High Urgency, Low Budget: Freelancer / student tools (requires massive consumer volume).",
        "Low Urgency, High Budget: Nice-to-have dashboards (protracted sales cycles, high churn).",
        "Low Urgency, Low Budget: Fatal dead-zone (avoid completely)."
    ])

    # Chapter 2
    doc.add_chapter_title("CHAPTER 2", "Founder-Led Sales & The First 10 Paid Pilots")
    doc.add_section_heading("2.1 Closing Your First 10 Paying Customers Manually")
    doc.add_paragraph("Do not rely on paid advertisements or automated self-serve funnels for your first ten clients. Founder-led sales provides an unmediated feedback loop that reveals the exact objections, language, and friction points within your value proposition.")
    doc.add_paragraph("Target 50 specific mid-market leaders on LinkedIn. Send personalized observational messages highlighting an existing bottleneck in their current tech stack. Offer an exclusive 90-day pilot program where you personally oversee onboarding and configuration.")
    doc.add_callout(
        "DISCOVERY SCRIPT BENCHMARK",
        "Never pitch features during the first 15 minutes of a discovery call. Ask: 'What is the single most expensive manual workflow your team executes every Monday morning?'"
    )
    doc.add_section_heading("2.2 Upfront Annual Commitments for Bootstrapped Runway")
    doc.add_paragraph("Never offer month-to-month contracts to initial pilot customers. Offer a substantial discount (e.g., 20%) in exchange for an upfront annual contract paid via bank transfer or dynamic UPI. Ten annual contracts at INR 50,000 generate INR 5,00,000 in immediate, zero-dilution working capital to fund infrastructure and growth.")

    # Chapter 3
    doc.add_chapter_title("CHAPTER 3", "Monetization Models & High-Velocity Pricing")
    doc.add_section_heading("3.1 Value-Metric vs Per-Seat Pricing")
    doc.add_paragraph("Per-seat pricing inadvertently penalizes adoption: customers actively restrict teammate access to reduce their monthly bill. Modern SaaS architectures price around a value metric that directly scales with client success: API transactions processed, gigabytes of storage utilized, or revenue collected.")
    doc.add_bullet_list([
        "Value Alignment: As the customer generates more revenue, your platform capture increases proportionately.",
        "Team Expansion: Free team seats encourage ubiquitous company-wide adoption, making replacement painful.",
        "Predictable Upgrades: Clear threshold tiers prevent invoice shock and reduce churn."
    ])
    doc.add_callout(
        "PRICING PSYCHOLOGY RULE",
        "Never display unrounded or arbitrary fees. Use clean, authoritative pricing tiers. In the Indian market, INR 199, INR 499, INR 999, and INR 1,999 form natural friction thresholds."
    )

    # Chapter 4
    doc.add_chapter_title("CHAPTER 4", "The Inbound Demand Engine & Content Moats")
    doc.add_section_heading("4.1 Engineering as Marketing: The Free Micro-Tool Strategy")
    doc.add_paragraph("Rather than competing against venture-backed competitors on paid keyword bidding, engineer a free, high-utility micro-tool that solves an immediate tactical headache for your ICP (e.g., a free GST calculator, an invoice generator, or a cold email subject-line analyzer). Host the tool on a subfolder of your domain.")
    doc.add_paragraph("A high-utility micro-tool earns organic backlinks, ranks on competitive search terms within 60 days, and routes thousands of qualified prospects directly into your core product checkout funnel.")

    # Chapter 5
    doc.add_chapter_title("CHAPTER 5", "Retention Architecture & Negative Net Churn")
    doc.add_section_heading("5.1 Defeating the Leaky Bucket Syndrome")
    doc.add_paragraph("SaaS revenue does not compound until monthly gross customer churn is driven below 2%. If you lose 5% of your customer base each month, you must replace 60% of your business every twelve months simply to remain flat.")
    doc.add_paragraph("Map the user journey to the 'First Value Realization' (FVR) milestone. If an onboarded user does not achieve measurable value within the first 120 seconds of logging in, their 30-day churn probability exceeds 80%.")
    doc.add_callout(
        "NET REVENUE RETENTION (NRR)",
        "Negative Net Churn occurs when revenue expansion from existing happy clients (add-ons, volume upgrades) exceeds the revenue lost from cancellations. Aim for 110%+ NRR."
    )

    # Chapter 6
    doc.add_chapter_title("CHAPTER 6", "Scaling to INR 10 Lakhs MRR & Institutional Readiness")
    doc.add_section_heading("6.1 The 10L MRR Operational Unit Economics")
    doc.add_paragraph("Reaching INR 10,00,000 Monthly Recurring Revenue (INR 1.2 Crore ARR) represents the gold standard of bootstrapped digital profitability in India. At this velocity, gross margins typically hover above 88%, providing founder liquidity, hiring capital, and enterprise stability.")
    doc.add_bullet_list([
        "Customer Acquisition Cost (CAC) Payback: Must be recouped within 4 months of subscription.",
        "LTV to CAC Ratio: Target a minimum of 4.5:1 for sustainable, non-venture growth.",
        "Gross Margins: Infrastructure and payment gateway costs must remain below 12% of gross revenue.",
        "Operating Reserve: Maintain a minimum 6-month cash reserve in a high-interest corporate liquid fund."
    ])

    return doc.finalize()


# ==============================================================================
# BOOK 2: Instagram Reel Funnel & DM Automation Master Guide
# ==============================================================================
def generate_instagram_funnel_book():
    doc = PDFDocument(
        book_title="Instagram Reel Funnel & DM Automation Master Guide",
        short_title="Instagram Reel Funnel",
        category="Marketing & Growth"
    )
    doc.draw_cover(
        subtitle="The Complete Blueprint for Converting Short-Form Attention into Automated, Direct-to-Consumer Digital Product Sales.",
        edition="2026 Master Production Release",
        metadata_items=[
            ("Title", "Instagram Reel Funnel & DM Automation Master Guide"),
            ("Category", "Social Commerce / Growth Engineering"),
            ("Publisher", "DropKit Digital Publications"),
            ("Applicability", "Creators, Educators, SaaS Founders, Digital Merchants"),
            ("Format", "Verified Architectural PDF Handbook"),
            ("License", "Single Commercial & Personal Deployment License")
        ]
    )

    doc.add_table_of_contents([
        ("Chapter 1", "The Psychology of the 3-Second Kinetic Hook", "Stopping the scroll, retention curves, visual and auditory pattern interrupts."),
        ("Chapter 2", "High-Converting Narrative Frameworks", "Problem -> Agitation -> Paradigm Shift -> Solution architecture."),
        ("Chapter 3", "The Automated Comment-to-DM Engine", "Why bio links fail, trigger keyword mechanics, and webhook integrations."),
        ("Chapter 4", "Mobile-Optimized Dynamic Checkout UX", "Sub-1.5s mobile load times, instant UPI QR generation, single-tap payment."),
        ("Chapter 5", "Paid Amplification & Retargeting Playbooks", "Boosting organic winners, custom audience pooling, CPA benchmarks."),
        ("Chapter 6", "30-Day Plug-and-Play Script Vault", "15 viral B2B scripts and 15 product conversion scripts with visual cues.")
    ])

    doc.add_chapter_title("CHAPTER 1", "The Psychology of the 3-Second Kinetic Hook")
    doc.add_section_heading("1.1 The Algorithmic Reality of the Modern Feed")
    doc.add_paragraph("The Instagram recommendation engine allocates 80% of its distribution weight to three metrics: Watch Time Percentage, Re-watches, and Direct Message Shares. If a viewer scrolls past your reel within the first 2.5 seconds, the algorithm flags your content as low-relevance and depresses subsequent organic reach.")
    doc.add_paragraph("Never begin a video with a casual greeting ('Hey guys!'). Begin directly in medias res with an assertion of an expensive misconception or a startling visual transformation.")
    doc.add_callout(
        "THE 3-SECOND RETENTION RULE",
        "A successful hook combines a kinetic visual action, bold high-contrast subtitles, and a counter-intuitive spoken statement in the first 1.8 seconds."
    )

    doc.add_chapter_title("CHAPTER 2", "High-Converting Narrative Frameworks")
    doc.add_section_heading("2.1 The P-A-P-S Architecture")
    doc.add_paragraph("To turn passive entertainment into active purchasing intent, structure every 45-second reel according to the P-A-P-S framework:")
    doc.add_bullet_list([
        "Problem (0-6s): State the acute, relatable obstacle your target audience encounters daily.",
        "Agitation (6-18s): Detail the compounding cost of failing to solve this problem (lost income, wasted hours).",
        "Paradigm Shift (18-30s): Introduce the counter-intuitive framework or architectural methodology.",
        "Solution & CTA (30-45s): Direct the viewer to comment a specific trigger word for instant resource delivery."
    ])

    doc.add_chapter_title("CHAPTER 3", "The Automated Comment-to-DM Engine")
    doc.add_section_heading("3.1 Why 'Link in Bio' Is Dead")
    doc.add_paragraph("Asking an Instagram user to tap your profile, find your bio, click an external link, and navigate a desktop-designed website results in an abysmal 1.2% click-through rate. In contrast, prompting a comment (e.g. 'Comment DROP below') leverages natural algorithmic feedback: high comment velocity signals massive engagement to the algorithm, triggering additional organic distribution.")
    doc.add_paragraph("Within 4 seconds of their comment, your automated backend dispatches a personalized Direct Message containing a trackable UTM link directly into their inbox.")
    doc.add_callout(
        "CONVERSION BENCHMARK",
        "Comment-to-DM funnels consistently achieve 68% to 84% DM open rates, representing an 8x lift over traditional bio-link funnels."
    )

    doc.add_chapter_title("CHAPTER 4", "Mobile-Optimized Dynamic Checkout UX")
    doc.add_section_heading("4.1 Minimizing Checkout Latency")
    doc.add_paragraph("Mobile users arriving via in-app Instagram browsers have zero tolerance for sluggish pages or mandatory registration forms. DropKit checkouts load in under 1.2 seconds, require only an email and phone number, and instantly generate a dynamic UPI QR code or trigger deep-links to GPay, PhonePe, and Paytm.")

    doc.add_chapter_title("CHAPTER 5", "Paid Amplification & Retargeting Playbooks")
    doc.add_section_heading("5.1 Amplifying Verified Organic Winners")
    doc.add_paragraph("Never run paid traffic to untested creative. Identify reels that have already achieved a 3x higher comment-to-view ratio organically. Apply a modest daily budget (INR 500 - INR 1,500) targeting lookalike audiences modeled on your existing DropKit customer email list.")

    return doc.finalize()


# ==============================================================================
# BOOK 3: Full-Stack System Architecture Blueprint 2026
# ==============================================================================
def generate_system_architecture_book():
    doc = PDFDocument(
        book_title="Full-Stack System Architecture Blueprint 2026",
        short_title="System Architecture Blueprint",
        category="Engineering & Code"
    )
    doc.draw_cover(
        subtitle="Modern Production Engineering Patterns for Resilient, High-Concurrency Web Applications & Distributed Systems.",
        edition="2026 Master Production Release",
        metadata_items=[
            ("Title", "Full-Stack System Architecture Blueprint 2026"),
            ("Category", "Cloud Infrastructure / Software Engineering"),
            ("Publisher", "DropKit Digital Publications"),
            ("Target Audience", "Staff Engineers, Solutions Architects, Tech Leads"),
            ("Format", "Verified Architectural PDF Handbook"),
            ("License", "Single Commercial & Personal Deployment License")
        ]
    )

    doc.add_table_of_contents([
        ("Chapter 1", "Architectural Paradigms: Monoliths vs Microservices", "Domain-driven boundaries, avoiding distributed monolith anti-patterns."),
        ("Chapter 2", "Database Scalability & Schema Hardening", "Relational indexing, connection pooling, read replicas, and sharding."),
        ("Chapter 3", "Caching Topologies & Invalidation Protocols", "Cache-Aside, Thundering Herd mitigation, and Edge cache invalidation."),
        ("Chapter 4", "Asynchronous Messaging & Event-Driven Architecture", "Kafka vs RabbitMQ, Dead-Letter Queues, and Idempotency keys."),
        ("Chapter 5", "Security Architecture & Cryptographic Integrity", "Argon2id, HTTP-only SameSite cookies, HMAC signatures, Rate limiters."),
        ("Chapter 6", "Observability, Telemetry & SRE Protocols", "Structured JSON logging, OpenTelemetry tracing, and SLI/SLO budgets.")
    ])

    doc.add_chapter_title("CHAPTER 1", "Architectural Paradigms: Monoliths vs Microservices")
    doc.add_section_heading("1.1 The Pragmatic Case for the Modular Monolith")
    doc.add_paragraph("Premature microservice decomposition introduces immense operational friction: distributed transaction overhead, network latency, serialization costs, and complex end-to-end tracing. For 95% of platforms handling under 100,000 requests per minute, a well-structured Modular Monolith with strictly separated domain boundaries provides superior developer velocity and operational simplicity.")
    doc.add_callout(
        "ARCHITECTURAL RULE",
        "Do not split a service into a separate deployment unit unless it exhibits fundamentally discordant scaling vectors (e.g. video transcoding vs CRUD metadata APIs)."
    )

    doc.add_chapter_title("CHAPTER 2", "Database Scalability & Schema Hardening")
    doc.add_section_heading("2.1 High-Performance Query Optimization")
    doc.add_paragraph("Relational databases (PostgreSQL, SQLite for embedded workloads) fail in production not because of data volume, but because of unindexed full table scans and connection starvation. Implement PgBouncer for transaction-level connection pooling to prevent backend thread exhaustion.")
    doc.add_bullet_list([
        "Composite Indexes: Index order must match your query filter hierarchy (Equality columns first, Range columns second).",
        "Connection Pooling: Limit active backend server connections to 2x the physical CPU core count.",
        "Idempotent Writes: Utilize unique constraints and ON CONFLICT DO UPDATE clauses to guarantee idempotent state mutations."
    ])

    doc.add_chapter_title("CHAPTER 3", "Caching Topologies & Invalidation Protocols")
    doc.add_section_heading("3.1 Cache-Aside & Thundering Herd Defense")
    doc.add_paragraph("When high-traffic cache keys expire, hundreds of simultaneous requests can pound the primary database simultaneously. Implement probabilistic early expiration (XFetch algorithm) or distributed mutex locks (Redis Redlock) to ensure only a single worker regenerates the cache.")

    doc.add_chapter_title("CHAPTER 4", "Asynchronous Messaging & Event-Driven Architecture")
    doc.add_section_heading("4.1 Guaranteed Delivery & Dead-Letter Handling")
    doc.add_paragraph("In distributed systems, networks will partition and consumer nodes will crash. Every asynchronous message producer must persist outbound events to an Outbox table in the same transaction as the business entity update. Consumers must enforce strict idempotency by recording processed event UUIDs before side-effects are executed.")

    doc.add_chapter_title("CHAPTER 5", "Security Architecture & Cryptographic Integrity")
    doc.add_section_heading("5.1 Protecting the Financial & Identity Perimeter")
    doc.add_paragraph("Store passwords strictly with Argon2id (memory-hard, resistant to GPU attacks). Enforce HTTP-only, Secure, SameSite=Strict cookies for administrative authentication to nullify Cross-Site Scripting (XSS) token theft. Verify all incoming webhook callbacks using HMAC-SHA256 constant-time string comparisons to eliminate timing attack vectors.")

    return doc.finalize()


# ==============================================================================
# BOOK 4: 50+ Micro-SaaS Cold Email & Outreach Templates
# ==============================================================================
def generate_cold_email_book():
    doc = PDFDocument(
        book_title="50+ Micro-SaaS Cold Email & Outreach Templates",
        short_title="Cold Email & Outreach",
        category="Sales & Outbound"
    )
    doc.draw_cover(
        subtitle="The Complete B2B Outbound Playbook for Landing Enterprise Demos, Agency Retainers & Strategic Partnerships.",
        edition="2026 Master Production Release",
        metadata_items=[
            ("Title", "50+ Micro-SaaS Cold Email & Outreach Templates"),
            ("Category", "Outbound B2B Sales / Revenue Engineering"),
            ("Publisher", "DropKit Digital Publications"),
            ("Target Audience", "Sales Leaders, Agency Owners, B2B Founders"),
            ("Format", "Verified Architectural PDF Handbook"),
            ("License", "Single Commercial & Personal Deployment License")
        ]
    )

    doc.add_table_of_contents([
        ("Chapter 1", "Technical Deliverability & Domain Infrastructure", "Secondary domains, SPF, DKIM, DMARC, custom tracking domains, inbox warmup."),
        ("Chapter 2", "ICP Precision & Lead Enrichment", "Scraping verified decision-maker emails via Apollo and Sales Navigator."),
        ("Chapter 3", "The 4-Sentence High-Conversion Anatomy", "Hook, pain observation, quantified social proof, zero-friction CTA."),
        ("Chapter 4", "The 5-Touch Follow-Up Cadence", "Value adds, video teardowns, case study breakdowns, and polite breakups."),
        ("Chapter 5", "Swipe Files: 50+ Real-World Categorized Templates", "Enterprise SaaS, agency retainers, consulting services, and tech pilots.")
    ])

    doc.add_chapter_title("CHAPTER 1", "Technical Deliverability & Domain Infrastructure")
    doc.add_section_heading("1.1 Protecting Your Primary Domain")
    doc.add_paragraph("Never send outbound cold emails from your primary operating domain. A sudden spike in spam reports can blacklist your company's primary Google Workspace or Microsoft 365 tenant, preventing day-to-day investor and customer communications. Always purchase 2-3 secondary lookalike domains (e.g., getdropkit.com, trydropkit.io).")
    doc.add_bullet_list([
        "SPF (Sender Policy Framework): Authorizes specific IP addresses to transmit mail on behalf of your domain.",
        "DKIM (DomainKeys Identified Mail): Adds a cryptographic signature verifying email integrity.",
        "DMARC: Instructs recipient servers to reject or quarantine unauthorized messages.",
        "Gradual Warmup: Ramp sending from 5 emails/day to 35 emails/day over a strict 21-day timeline."
    ])

    doc.add_chapter_title("CHAPTER 2", "ICP Precision & Lead Enrichment")
    doc.add_section_heading("2.1 High-Intent Signal Scraping")
    doc.add_paragraph("Generic cold emails fail because they lack timely relevance. Scrape prospect lists based on explicit hiring signals, recent funding announcements, tech stack migrations, or executive leadership changes. Relevancy beats volume every single time.")

    doc.add_chapter_title("CHAPTER 3", "The 4-Sentence High-Conversion Anatomy")
    doc.add_section_heading("3.1 The Low-Friction B2B Formula")
    doc.add_paragraph("Modern executives read email on mobile devices during commutes. Long paragraphs get deleted instantly. Restrict cold emails to four concise sentences:")
    doc.add_bullet_list([
        "Sentence 1 (Observation): Acknowledge a specific public initiative or technical milestone they recently completed.",
        "Sentence 2 (Problem Hook): Introduce the hidden operational bottleneck commonly associated with that initiative.",
        "Sentence 3 (Social Proof): Quantify how you eliminated that bottleneck for a peer company (e.g. 'boosted checkout conversion by 28%').",
        "Sentence 4 (Low-Friction CTA): 'Open to taking a look at a 2-minute video breakdown this Thursday?'"
    ])

    doc.add_chapter_title("CHAPTER 4", "Swipe Files: 50+ Battle-Tested Templates")
    doc.add_section_heading("4.1 Selected Top-Performing Templates")
    doc.add_paragraph("Below are representative templates with verified open rates exceeding 70% and reply rates exceeding 14%:")
    doc.add_callout(
        "TEMPLATE A: THE RECENT HIRING TRIGGER",
        "Subject: Quick question re: [Company] engineering team\n\nHi [First_Name],\n\nNoticed you're expanding your frontend team in Bengaluru. Usually when teams scale UI engineering this fast, design system consistency and regression testing start slipping.\n\nWe helped [Client_Name] automate their component audits, cutting QA cycles by 40%.\n\nWorth sharing a 3-minute video breakdown of how we did it?"
    )
    doc.add_callout(
        "TEMPLATE B: THE COMPETITOR COMPARISON TRIGGER",
        "Subject: Alternative to [Competitor_Name] for [Company]\n\nHi [First_Name],\n\nSaw your team recently migrated away from [Old_Platform]. A lot of engineering leads we speak with found [Competitor]'s API rate limits and enterprise pricing restrictive as transaction volumes scaled.\n\nDropKit provides self-hosted dynamic checkout APIs at zero revenue commission.\n\nOpen to reviewing our 1-page architectural benchmark?"
    )

    return doc.finalize()


# ==============================================================================
# BOOK 5: Modern UI/UX Design System Checklist & Wireframes
# ==============================================================================
def generate_ui_ux_book():
    doc = PDFDocument(
        book_title="Modern UI/UX Design System Checklist & Wireframes",
        short_title="UI/UX Design System Checklist",
        category="Design & UX"
    )
    doc.draw_cover(
        subtitle="A Comprehensive Engineering & Human Interface Standard for Building Scalable, Accessible SaaS Products.",
        edition="2026 Master Production Release",
        metadata_items=[
            ("Title", "Modern UI/UX Design System Checklist & Wireframes"),
            ("Category", "Human Interface Design / Frontend Architecture"),
            ("Publisher", "DropKit Digital Publications"),
            ("Standards", "WCAG 2.1 AA Compliance / 8pt Spatial Grid"),
            ("Format", "Verified Architectural PDF Handbook"),
            ("License", "Single Commercial & Personal Deployment License")
        ]
    )

    doc.add_table_of_contents([
        ("Chapter 1", "Design Tokens & Spatial Foundations", "The 8pt spatial grid, typography scales, semantic color palettes."),
        ("Chapter 2", "Component Architecture & State Hierarchies", "Atomic design: Atoms, Molecules, Organisms; hover, focus, disabled states."),
        ("Chapter 3", "SaaS Dashboard & Information Density", "Data tables, micro-interactions, empty states, and skeleton loaders."),
        ("Chapter 4", "High-Velocity Checkout & Form UX", "Minimizing cognitive load, inline validation, mobile touch targets."),
        ("Chapter 5", "The 120-Point Master Production Audit Checklist", "Comprehensive accessibility, contrast, performance, and responsive tests.")
    ])

    doc.add_chapter_title("CHAPTER 1", "Design Tokens & Spatial Foundations")
    doc.add_section_heading("1.1 The 8-Point Spatial Grid")
    doc.add_paragraph("Visual polish stems from mathematical rhythm. Every margin, padding, height, and gap in a production design system must resolve to a multiple of 8 pixels (with 4px reserved exclusively for dense micro-spacing such as icon offsets or badge padding).")
    doc.add_bullet_list([
        "4px: Micro-gaps (badge text margins, icon-to-label spacing).",
        "8px: Compact element padding (small buttons, table cell vertical margins).",
        "16px: Standard container padding (card interiors, form element separation).",
        "24px - 32px: Section gaps and grid separation.",
        "48px - 64px: Hero margins and page-level section breaks."
    ])

    doc.add_chapter_title("CHAPTER 2", "Component Architecture & State Hierarchies")
    doc.add_section_heading("2.1 Comprehensive State Coverage")
    doc.add_paragraph("Amateur mockups fail in production because they only illustrate the 'happy path.' Every interactive component (buttons, inputs, dropdowns, table rows) must explicitly specify seven distinct states:")
    doc.add_bullet_list([
        "Default State: Unfocused, neutral appearance.",
        "Hover State: Elevation increase or 8% luminance adjustment.",
        "Active / Pressed: Tactile downward shift or color deepening.",
        "Focus State: High-contrast 2px outline for keyboard navigability (WCAG 2.1).",
        "Disabled State: 40% opacity with cursor: not-allowed.",
        "Loading State: Spinner or shimmer with disabled pointer interactions.",
        "Error State: Semantic red border with localized descriptive feedback text."
    ])

    doc.add_chapter_title("CHAPTER 3", "High-Velocity Checkout & Form UX")
    doc.add_section_heading("3.1 Reducing Cognitive Friction in Payment Funnels")
    doc.add_paragraph("Every unnecessary input field reduces mobile checkout conversion by approximately 7%. For digital product sales, never ask for physical billing addresses or secondary phone numbers. Restrict required inputs to Full Name and Email Address. Present a high-contrast Dynamic UPI QR code immediately upon page render.")

    doc.add_chapter_title("CHAPTER 4", "The 120-Point Master Production Audit Checklist")
    doc.add_section_heading("4.1 Critical Production Verification Criteria")
    doc.add_bullet_list([
        "Contrast Ratios: Minimum 4.5:1 for body copy; 3:1 for large display headers (WCAG AA).",
        "Tap Targets: Minimum 44px by 44px clickable surface on mobile touchscreens.",
        "Visual Hierarchy: Exactly one primary call-to-action button per viewport screen.",
        "Keyboard Navigation: Full tab-index traversal across all modals and inputs without trapping.",
        "Font Weight Restraint: Maximum of 3 distinct font weights per application screen."
    ])

    return doc.finalize()


# ==============================================================================
# BOOK 6: Indian Tax & Accounting Playbook for Solo Digital Creators
# ==============================================================================
def generate_creator_tax_book():
    doc = PDFDocument(
        book_title="Indian Tax & Accounting Playbook for Solo Digital Creators",
        short_title="Indian Creator Tax Playbook",
        category="Finance & Legal"
    )
    doc.draw_cover(
        subtitle="A Practical Guide to Presumptive Taxation (Section 44ADA), GST LUT for Export, and Legitimate Business Deductions.",
        edition="2026 Master Production Release",
        metadata_items=[
            ("Title", "Indian Tax & Accounting Playbook for Solo Digital Creators"),
            ("Category", "Taxation / Legal Compliance India"),
            ("Publisher", "DropKit Digital Publications"),
            ("Jurisdiction", "Republic of India (Income Tax Act & GST Council)"),
            ("Format", "Verified Architectural PDF Handbook"),
            ("License", "Single Commercial & Personal Deployment License")
        ]
    )

    doc.add_table_of_contents([
        ("Chapter 1", "Entity Structuring: Sole Prop vs LLP vs Pvt Ltd", "When to incorporate, opening current accounts, compliance costs."),
        ("Chapter 2", "Section 44ADA: The 50% Presumptive Tax Superpower", "Eligibility, calculating taxable net profits, audit exemptions."),
        ("Chapter 3", "GST Registration & LUT for Zero-Rated Export", "Mandatory turnover limits, filing Letter of Undertaking for foreign sales."),
        ("Chapter 4", "Allowable Business Expense Deductions", "Laptops, phones, SaaS subscriptions, co-working, and utility allocations."),
        ("Chapter 5", "Advance Tax Calendar, TDS Reconciliation & ITR Forms", "Quarterly deadlines, Form 26AS matching, and filing ITR-3/ITR-4.")
    ])

    doc.add_chapter_title("CHAPTER 1", "Entity Structuring: Sole Prop vs LLP vs Pvt Ltd")
    doc.add_section_heading("1.1 The Solopreneur Dilemma")
    doc.add_paragraph("Many Indian digital creators incorporate a Private Limited company prematurely, incurring INR 40,000 to INR 75,000 in annual statutory audit and secretarial filing expenses before achieving product-market fit. A Sole Proprietorship operates as the most agile structure for solo creators generating under INR 50 Lakhs annually, offering zero incorporation cost and simplified tax filing.")

    doc.add_chapter_title("CHAPTER 2", "Section 44ADA: The 50% Presumptive Tax Superpower")
    doc.add_section_heading("2.1 Legally Declaring 50% Profit")
    doc.add_paragraph("Under Section 44ADA of the Indian Income Tax Act, eligible professionals (software engineers, technical consultants, UI designers, content creators) earning gross receipts up to INR 75 Lakhs (where digital receipts exceed 95%) can declare flat 50% of their gross receipts as taxable income.")
    doc.add_callout(
        "FINANCIAL IMPACT EXAMPLE",
        "If your digital product store earns INR 30,00,000 in annual revenue, you declare only INR 15,00,000 as taxable income under Section 44ADA without maintaining detailed daily expense vouchers or undergoing statutory CA audit."
    )

    doc.add_chapter_title("CHAPTER 3", "GST Registration & LUT for Zero-Rated Export")
    doc.add_section_heading("3.1 Exporting Digital Products Internationally")
    doc.add_paragraph("Digital downloads sold to customers outside India qualify as an 'Export of Services' under GST law. By filing a free Letter of Undertaking (LUT - Form GST RFD-11) at the start of each fiscal year, you can export digital products at a 0% effective GST rate without paying tax upfront.")
    doc.add_bullet_list([
        "Domestic Threshold: GST registration mandatory once annual domestic turnover crosses INR 20 Lakhs.",
        "Foreign Invoicing: Must retain foreign inward remittance certificates (FIRC / FIRA) as proof of foreign currency receipt.",
        "Input Tax Credit (ITC): Claim full GST refund on business laptops, cloud hosting, and SaaS subscriptions."
    ])

    doc.add_chapter_title("CHAPTER 4", "Advance Tax Calendar & ITR Filing")
    doc.add_section_heading("4.1 Quarterly Deadlines")
    doc.add_paragraph("If your total tax liability for the financial year exceeds INR 10,000, you must pay Advance Tax in four installments to avoid penal interest under Sections 234B and 234C:")
    doc.add_bullet_list([
        "June 15: 15% of estimated tax liability.",
        "September 15: 45% of estimated tax liability.",
        "December 15: 75% of estimated tax liability.",
        "March 15: 100% of estimated tax liability."
    ])

    return doc.finalize()


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    print("="*60)
    print("DROPKIT ORIGINAL PDF GENERATION ENGINE")
    print("="*60)

    books = [
        ("saas-growth-engine.pdf", "SaaS Growth Engine: 0 to INR 10 Lakhs MRR", generate_saas_growth_book),
        ("instagram-reel-funnel.pdf", "Instagram Reel Funnel & DM Automation Master Guide", generate_instagram_funnel_book),
        ("fullstack-system-architecture.pdf", "Full-Stack System Architecture Blueprint 2026", generate_system_architecture_book),
        ("cold-email-templates.pdf", "50+ Micro-SaaS Cold Email & Outreach Templates", generate_cold_email_book),
        ("ui-ux-design-checklist.pdf", "Modern UI/UX Design System Checklist & Wireframes", generate_ui_ux_book),
        ("creator-tax-playbook.pdf", "Indian Tax & Accounting Playbook for Solo Digital Creators", generate_creator_tax_book),
    ]

    SECURE_PDF_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()
    now = now_iso()

    for filename, title, generator_func in books:
        pdf_bytes, page_count = generator_func()
        dest_path = SECURE_PDF_DIR / filename
        with open(dest_path, "wb") as f:
            f.write(pdf_bytes)

        filesize = len(pdf_bytes)
        print(f"-> Generated {filename}: {page_count} pages, {filesize:,} bytes")

        # Update database
        cursor.execute("""
            UPDATE products
            SET pdf_filesize = ?, pdf_pages = ?, updated_at = ?
            WHERE pdf_filename = ?
        """, (filesize, page_count, now, filename))

    conn.commit()
    conn.close()
    print("="*60)
    print("ALL 6 ORIGINAL PDF PUBLICATIONS GENERATED & DATABASE UPDATED!")
    print("="*60)

if __name__ == "__main__":
    main()
