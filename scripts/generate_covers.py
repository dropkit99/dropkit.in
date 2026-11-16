import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import PUBLIC_COVER_DIR
from backend.db import get_connection

COVERS = [
    {
        "filename": "cover_saas_growth.svg",
        "title": "SaaS Growth Engine",
        "subtitle": "0 to ₹10 Lakhs MRR Scaling Roadmap",
        "tag": "BUSINESS & SAAS",
        "pages": "48 Pages",
        "accent": "#FF653D",
        "icon": "🚀"
    },
    {
        "filename": "cover_instagram_funnel.svg",
        "title": "Instagram Reel Funnel",
        "subtitle": "DM Automation & Lead Conversion Guide",
        "tag": "MARKETING & SALES",
        "pages": "32 Pages",
        "accent": "#E1306C",
        "icon": "📸"
    },
    {
        "filename": "cover_system_architecture.svg",
        "title": "Full-Stack System Architecture",
        "subtitle": "Enterprise Cloud & Microservices Blueprint 2026",
        "tag": "DEVELOPER PLAYBOOKS",
        "pages": "72 Pages",
        "accent": "#3B82F6",
        "icon": "⚡"
    },
    {
        "filename": "cover_cold_emails.svg",
        "title": "50+ Micro-SaaS Cold Emails",
        "subtitle": "High-Converting B2B Outreach Templates",
        "tag": "OUTREACH & SALES",
        "pages": "24 Pages",
        "accent": "#10B981",
        "icon": "✉️"
    },
    {
        "filename": "cover_ui_ux_checklist.svg",
        "title": "Modern UI/UX Design System",
        "subtitle": "200+ SaaS Wireframes & Design Token Checklist",
        "tag": "DESIGN & UI KITS",
        "pages": "56 Pages",
        "accent": "#8B5CF6",
        "icon": "🎨"
    },
    {
        "filename": "cover_tax_playbook.svg",
        "title": "Indian Creator Tax Playbook",
        "subtitle": "GST, Section 44ADA & Accounting Compliance",
        "tag": "FINANCE & COMPLIANCE",
        "pages": "64 Pages",
        "accent": "#F59E0B",
        "icon": "📊"
    }
]

def generate_svg_cover(c):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 800" width="100%" height="100%">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1B1D3B"/>
      <stop offset="60%" stop-color="#15172E"/>
      <stop offset="100%" stop-color="#0E0F1F"/>
    </linearGradient>
    <linearGradient id="accentGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{c['accent']}"/>
      <stop offset="100%" stop-color="#FF653D"/>
    </linearGradient>
    <filter id="cardShadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="12" stdDeviation="16" flood-color="#000" flood-opacity="0.4"/>
    </filter>
  </defs>

  <!-- Background -->
  <rect width="600" height="800" fill="url(#bgGrad)"/>

  <!-- Geometric Grid & Glow Accents -->
  <circle cx="500" cy="150" r="220" fill="{c['accent']}" opacity="0.12"/>
  <circle cx="100" cy="700" r="180" fill="#FF653D" opacity="0.08"/>
  <rect x="0" y="0" width="600" height="8" fill="url(#accentGrad)"/>

  <!-- Left Spine simulation -->
  <rect x="0" y="0" width="24" height="800" fill="#121326" opacity="0.6"/>
  <line x1="24" y1="0" x2="24" y2="800" stroke="rgba(255,255,255,0.08)" stroke-width="2"/>

  <!-- Header Branding -->
  <g transform="translate(60, 55)">
    <!-- Droplet Icon -->
    <circle cx="20" cy="20" r="18" fill="#FF653D"/>
    <path d="M 20 10 C 26 20 26 25 20 28 C 14 25 14 20 20 10 Z" fill="#FFFFFF"/>
    <text x="48" y="26" font-family="'Plus Jakarta Sans', system-ui, sans-serif" font-size="20" font-weight="800" fill="#FFFFFF">DropKit</text>
    <text x="135" y="26" font-family="system-ui, sans-serif" font-size="12" font-weight="600" fill="#74778D" letter-spacing="1">PUBLICATIONS</text>
  </g>

  <!-- Category Tag -->
  <g transform="translate(60, 140)">
    <rect width="200" height="30" rx="6" fill="rgba(255, 101, 61, 0.15)" stroke="rgba(255, 101, 61, 0.4)" stroke-width="1"/>
    <text x="14" y="20" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#FF653D" letter-spacing="1.5">{c['tag']}</text>
  </g>

  <!-- Title Area -->
  <g transform="translate(60, 230)">
    <text x="0" y="0" font-family="'Plus Jakarta Sans', system-ui, sans-serif" font-size="44" font-weight="800" fill="#FFFFFF" line-height="1.2">
      {c['title'][:22]}
    </text>
    <text x="0" y="50" font-family="'Plus Jakarta Sans', system-ui, sans-serif" font-size="44" font-weight="800" fill="url(#accentGrad)">
      {c['title'][22:] if len(c['title']) > 22 else 'Guide'}
    </text>
    <text x="0" y="110" font-family="system-ui, sans-serif" font-size="18" font-weight="500" fill="#A0A3BD" width="480">
      {c['subtitle']}
    </text>
  </g>

  <!-- Central Graphic Icon Badge -->
  <g transform="translate(300, 480)" filter="url(#cardShadow)">
    <circle cx="0" cy="0" r="75" fill="#1B1D3B" stroke="rgba(255,255,255,0.15)" stroke-width="2"/>
    <circle cx="0" cy="0" r="62" fill="url(#accentGrad)" opacity="0.2"/>
    <text x="0" y="18" font-size="52" text-anchor="middle" dominant-baseline="middle">{c['icon']}</text>
  </g>

  <!-- Bottom Feature Strip -->
  <g transform="translate(60, 680)">
    <rect width="480" height="60" rx="12" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.1)" stroke-width="1"/>
    
    <!-- Pages info -->
    <text x="24" y="36" font-family="system-ui, sans-serif" font-size="14" font-weight="600" fill="#FFFFFF">📄 {c['pages']}</text>
    <circle cx="130" cy="32" r="3" fill="#74778D"/>
    <text x="145" y="36" font-family="system-ui, sans-serif" font-size="14" font-weight="500" fill="#A0A3BD">Instant PDF Delivery</text>

    <!-- Verified Badge -->
    <rect x="360" y="15" width="100" height="30" rx="15" fill="#10B981" opacity="0.2"/>
    <text x="410" y="35" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#10B981" text-anchor="middle">VERIFIED</text>
  </g>
</svg>"""

def main():
    conn = get_connection()
    cursor = conn.cursor()

    for i, c in enumerate(COVERS, start=1):
        svg_content = generate_svg_cover(c)
        target_path = PUBLIC_COVER_DIR / c['filename']
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(svg_content)
        print(f"Generated cover: {c['filename']}")

        # Update in DB
        cursor.execute("UPDATE products SET cover_image = ? WHERE id = ?", (c['filename'], i))

    conn.commit()
    conn.close()
    print("All 6 product covers successfully generated and mapped in database!")

if __name__ == "__main__":
    main()
