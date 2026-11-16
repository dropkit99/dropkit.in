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
        "category": "BUSINESS &amp; SAAS",
        "tag_color": "#FF653D",
        "title_line1": "SaaS Growth Engine",
        "title_line2": "0 to ₹10 Lakhs MRR",
        "subtitle": "The definitive tactical scaling playbook used by solo founders to scale B2B micro-SaaS with predictable recurring revenue.",
        "pages": "48 Pages",
        "read_time": "45 Min Read",
        "accent": "#FF653D",
        "accent_secondary": "#FF8A65",
        "badge_text": "+₹10,00,000 MRR",
        "badge_sub": "SCALING ROADMAP",
        "graphic_type": "rocket"
    },
    {
        "filename": "cover_instagram_funnel.svg",
        "category": "MARKETING &amp; SALES",
        "tag_color": "#E1306C",
        "title_line1": "Instagram Reel Funnel",
        "title_line2": "&amp; DM Automation",
        "subtitle": "Turn casual reel viewers into paying digital buyers. Set up automated keyword triggers and dynamic DM checkout links.",
        "pages": "36 Pages",
        "read_time": "35 Min Read",
        "accent": "#E1306C",
        "accent_secondary": "#FF653D",
        "badge_text": "34% CONVERSION",
        "badge_sub": "VIRAL LEAD FUNNEL",
        "graphic_type": "funnel"
    },
    {
        "filename": "cover_system_architecture.svg",
        "category": "DEVELOPER PLAYBOOKS",
        "tag_color": "#3B82F6",
        "title_line1": "Full-Stack System",
        "title_line2": "Architecture 2026",
        "subtitle": "High-concurrency microservices, caching topologies, database sharding, and zero-trust authentication blueprints.",
        "pages": "72 Pages",
        "read_time": "90 Min Read",
        "accent": "#3B82F6",
        "accent_secondary": "#06B6D4",
        "badge_text": "99.999% UPTIME",
        "badge_sub": "ENTERPRISE CLOUD",
        "graphic_type": "architecture"
    },
    {
        "filename": "cover_cold_emails.svg",
        "category": "OUTREACH &amp; SALES",
        "tag_color": "#10B981",
        "title_line1": "50+ Micro-SaaS",
        "title_line2": "Cold Email Templates",
        "subtitle": "Battle-tested B2B outreach scripts that landed \\$50k+ contracts. High-deliverability subject lines and follow-up cadences.",
        "pages": "28 Pages",
        "read_time": "25 Min Read",
        "accent": "#10B981",
        "accent_secondary": "#34D399",
        "badge_text": "78% OPEN RATE",
        "badge_sub": "VERIFIED SCRIPTS",
        "graphic_type": "outreach"
    },
    {
        "filename": "cover_ui_ux_checklist.svg",
        "category": "DESIGN &amp; UI KITS",
        "tag_color": "#8B5CF6",
        "title_line1": "Modern UI/UX",
        "title_line2": "Design System 2026",
        "subtitle": "Comprehensive checklist for SaaS wireframes, responsive grids, dark-mode tokens, accessible contrast, and micro-interactions.",
        "pages": "54 Pages",
        "read_time": "50 Min Read",
        "accent": "#8B5CF6",
        "accent_secondary": "#EC4899",
        "badge_text": "200+ COMPONENTS",
        "badge_sub": "DESIGN TOKENS",
        "graphic_type": "design"
    },
    {
        "filename": "cover_tax_playbook.svg",
        "category": "FINANCE &amp; COMPLIANCE",
        "tag_color": "#F59E0B",
        "title_line1": "Indian Creator",
        "title_line2": "Tax Playbook",
        "subtitle": "Section 44ADA 50% presumptive taxation, GST LUT filing, international payment reconciliation, and solo accounting.",
        "pages": "62 Pages",
        "read_time": "60 Min Read",
        "accent": "#F59E0B",
        "accent_secondary": "#10B981",
        "badge_text": "SEC. 44ADA COMPLIANT",
        "badge_sub": "ZERO TAX PENALTIES",
        "graphic_type": "tax"
    }
]

def render_graphic(g_type, accent, sec_accent):
    if g_type == "rocket":
        return f"""
        <!-- Rocket 3D Graphic -->
        <g transform="translate(630, 240)">
          <!-- Orbital rings -->
          <circle cx="0" cy="0" r="140" fill="none" stroke="{accent}" stroke-width="1.5" stroke-dasharray="6,8" opacity="0.35"/>
          <circle cx="0" cy="0" r="110" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="1"/>
          
          <!-- Radial back aura -->
          <circle cx="0" cy="0" r="90" fill="{accent}" opacity="0.18" filter="url(#glowBlur)"/>
          
          <!-- Rocket Body -->
          <g transform="rotate(-35) translate(-15, -45)">
            <!-- Exhaust Glow -->
            <polygon points="15,90 28,140 2,140" fill="url(#fireGrad)" opacity="0.9" filter="url(#fireGlow)"/>
            <polygon points="15,90 22,125 8,125" fill="#FFFFFF" opacity="0.95"/>
            
            <!-- Wings -->
            <polygon points="0,60 -20,85 0,85" fill="{accent}"/>
            <polygon points="30,60 50,85 30,85" fill="{accent}"/>
            
            <!-- Fuselage -->
            <path d="M 15 0 C 35 30 35 80 30 90 L 0 90 C -5 80 -5 30 15 0 Z" fill="#FFFFFF"/>
            
            <!-- Glass Porthole -->
            <circle cx="15" cy="40" r="8" fill="#1B1D3B" stroke="{accent}" stroke-width="2.5"/>
            <circle cx="15" cy="40" r="4" fill="{accent}"/>
            
            <!-- Nose Cone Accent -->
            <path d="M 15 0 C 22 12 24 24 24 24 L 6 24 C 6 24 8 12 15 0 Z" fill="{accent}"/>
          </g>

          <!-- Floating Stat Badge -->
          <g transform="translate(-80, 75)" filter="url(#cardShadow)">
            <rect width="160" height="36" rx="18" fill="#1B1D3B" stroke="{accent}" stroke-width="1.5"/>
            <circle cx="18" cy="18" r="6" fill="#10B981"/>
            <text x="32" y="22" font-family="'Plus Jakarta Sans', sans-serif" font-size="11" font-weight="800" fill="#FFFFFF" letter-spacing="0.5">+₹10L MRR ROADMAP</text>
          </g>
        </g>
        """
    elif g_type == "funnel":
        return f"""
        <!-- Instagram Funnel 3D Graphic -->
        <g transform="translate(630, 240)">
          <!-- Concentric Aperture Rings -->
          <circle cx="0" cy="0" r="145" fill="none" stroke="{accent}" stroke-width="1.5" stroke-dasharray="10,6" opacity="0.4"/>
          <circle cx="0" cy="0" r="115" fill="none" stroke="{sec_accent}" stroke-width="2" stroke-dasharray="180,40" opacity="0.6"/>
          <circle cx="0" cy="0" r="88" fill="{accent}" opacity="0.16" filter="url(#glowBlur)"/>

          <!-- Camera Lens Iris Base -->
          <circle cx="0" cy="0" r="72" fill="#1B1D3B" stroke="rgba(255,255,255,0.2)" stroke-width="2"/>
          <circle cx="0" cy="0" r="54" fill="url(#igGrad)" opacity="0.9"/>
          
          <!-- Lens Glass Reflection -->
          <circle cx="-12" cy="-12" r="14" fill="#FFFFFF" opacity="0.35"/>
          <circle cx="0" cy="0" r="28" fill="#121327" stroke="rgba(255,255,255,0.4)" stroke-width="1.5"/>
          <circle cx="0" cy="0" r="12" fill="{accent}"/>

          <!-- Floating DM Notification Chips -->
          <g transform="translate(-105, -75)" filter="url(#cardShadow)">
            <rect width="110" height="32" rx="16" fill="#FFFFFF"/>
            <circle cx="16" cy="16" r="7" fill="{accent}"/>
            <text x="30" y="20" font-family="'Plus Jakarta Sans', sans-serif" font-size="11" font-weight="800" fill="#1B1D3B">"DROP" ⚡</text>
          </g>

          <g transform="translate(5, 75)" filter="url(#cardShadow)">
            <rect width="135" height="34" rx="17" fill="#1B1D3B" stroke="{accent}" stroke-width="1.5"/>
            <text x="16" y="21" font-family="'Plus Jakarta Sans', sans-serif" font-size="11" font-weight="800" fill="#FFFFFF">Direct UPI DM 🔗</text>
          </g>
        </g>
        """
    elif g_type == "architecture":
        return f"""
        <!-- System Architecture 3D Cloud Graphic -->
        <g transform="translate(630, 240)">
          <!-- Outer Network Ring -->
          <circle cx="0" cy="0" r="145" fill="none" stroke="{accent}" stroke-width="1.5" stroke-dasharray="8,8" opacity="0.4"/>
          <circle cx="0" cy="0" r="95" fill="{accent}" opacity="0.15" filter="url(#glowBlur)"/>

          <!-- 3D Isometric Microservice Cubes -->
          <!-- Top Cube -->
          <g transform="translate(0, -50)">
            <polygon points="0,-22 35,-2 0,18 -35,-2" fill="{sec_accent}"/>
            <polygon points="-35,-2 0,18 0,50 -35,30" fill="{accent}"/>
            <polygon points="0,18 35,-2 35,30 0,50" fill="#1E40AF"/>
          </g>

          <!-- Left Cube -->
          <g transform="translate(-55, 30)">
            <polygon points="0,-18 28,-2 0,14 -28,-2" fill="{sec_accent}" opacity="0.9"/>
            <polygon points="-28,-2 0,14 0,40 -28,24" fill="{accent}"/>
            <polygon points="0,14 28,-2 28,24 0,40" fill="#1E40AF"/>
          </g>

          <!-- Right Cube -->
          <g transform="translate(55, 30)">
            <polygon points="0,-18 28,-2 0,14 -28,-2" fill="{sec_accent}" opacity="0.9"/>
            <polygon points="-28,-2 0,14 0,40 -28,24" fill="{accent}"/>
            <polygon points="0,14 28,-2 28,24 0,40" fill="#1E40AF"/>
          </g>

          <!-- Interconnect Light Lines -->
          <line x1="0" y1="-2" x2="-55" y2="30" stroke="#38BDF8" stroke-width="2" stroke-dasharray="4,4"/>
          <line x1="0" y1="-2" x2="55" y2="30" stroke="#38BDF8" stroke-width="2" stroke-dasharray="4,4"/>
          <line x1="-55" y1="30" x2="55" y2="30" stroke="#38BDF8" stroke-width="1.5"/>

          <!-- Central Core Energy Glow -->
          <circle cx="0" cy="20" r="10" fill="#38BDF8" filter="url(#fireGlow)"/>

          <!-- Floating Architecture Badge -->
          <g transform="translate(-75, 95)" filter="url(#cardShadow)">
            <rect width="150" height="34" rx="17" fill="#0B1329" stroke="#38BDF8" stroke-width="1.5"/>
            <text x="18" y="21" font-family="'Plus Jakarta Sans', sans-serif" font-size="11" font-weight="800" fill="#38BDF8">99.999% HIGH AVAIL</text>
          </g>
        </g>
        """
    elif g_type == "outreach":
        return f"""
        <!-- Cold Emails & Outreach Graphic -->
        <g transform="translate(630, 240)">
          <circle cx="0" cy="0" r="145" fill="none" stroke="{accent}" stroke-width="1.5" stroke-dasharray="8,6" opacity="0.35"/>
          <circle cx="0" cy="0" r="90" fill="{accent}" opacity="0.16" filter="url(#glowBlur)"/>

          <!-- 3D Envelope Base -->
          <g transform="rotate(-15) translate(-60, -40)" filter="url(#cardShadow)">
            <rect width="120" height="85" rx="12" fill="#FFFFFF"/>
            <path d="M 0 10 L 60 55 L 120 10" fill="none" stroke="{accent}" stroke-width="3"/>
            <polygon points="0,10 60,55 120,10 120,0 0,0" fill="{sec_accent}" opacity="0.3"/>
            
            <!-- Outgoing Holographic Supersonic Jet -->
            <polygon points="80,-20 130,-45 95,-10 90,-5" fill="{accent}"/>
            <polygon points="90,-5 130,-45 105,5" fill="{sec_accent}"/>
          </g>

          <!-- Trajectory dotted stream -->
          <path d="M -90 90 Q 0 40 80 -40" fill="none" stroke="{accent}" stroke-width="2" stroke-dasharray="5,6"/>

          <!-- High Deliverability Pill -->
          <g transform="translate(-75, 80)" filter="url(#cardShadow)">
            <rect width="150" height="36" rx="18" fill="#1B1D3B" stroke="{accent}" stroke-width="1.5"/>
            <circle cx="20" cy="18" r="6" fill="{accent}"/>
            <text x="34" y="22" font-family="'Plus Jakarta Sans', sans-serif" font-size="11" font-weight="800" fill="#FFFFFF">78% B2B OPEN RATE</text>
          </g>
        </g>
        """
    elif g_type == "design":
        return f"""
        <!-- UI/UX Design System Graphic -->
        <g transform="translate(630, 240)">
          <circle cx="0" cy="0" r="145" fill="none" stroke="{accent}" stroke-width="1.5" stroke-dasharray="8,8" opacity="0.35"/>
          <circle cx="0" cy="0" r="90" fill="{accent}" opacity="0.18" filter="url(#glowBlur)"/>

          <!-- Layered Glassmorphic Component Cards -->
          <!-- Back Card -->
          <g transform="translate(-40, -65) rotate(-10)" filter="url(#cardShadow)">
            <rect width="130" height="85" rx="10" fill="rgba(255,255,255,0.12)" stroke="rgba(255,255,255,0.25)" stroke-width="1.5"/>
            <line x1="15" y1="20" x2="60" y2="20" stroke="{sec_accent}" stroke-width="3" stroke-linecap="round"/>
            <line x1="15" y1="35" x2="105" y2="35" stroke="rgba(255,255,255,0.3)" stroke-width="2" stroke-linecap="round"/>
            <line x1="15" y1="50" x2="85" y2="50" stroke="rgba(255,255,255,0.3)" stroke-width="2" stroke-linecap="round"/>
          </g>

          <!-- Front Card -->
          <g transform="translate(-15, -15) rotate(5)" filter="url(#cardShadow)">
            <rect width="140" height="95" rx="12" fill="#1B1D3B" stroke="{accent}" stroke-width="2"/>
            <!-- UI Header -->
            <circle cx="20" cy="20" r="4" fill="#EF4444"/>
            <circle cx="32" cy="20" r="4" fill="#F59E0B"/>
            <circle cx="44" cy="20" r="4" fill="#10B981"/>
            
            <!-- Swatches -->
            <rect x="20" y="38" width="22" height="22" rx="6" fill="{accent}"/>
            <rect x="48" y="38" width="22" height="22" rx="6" fill="{sec_accent}"/>
            <rect x="76" y="38" width="22" height="22" rx="6" fill="#3B82F6"/>
            <rect x="104" y="38" width="16" height="22" rx="6" fill="#10B981"/>

            <!-- Button Component -->
            <rect x="20" y="68" width="75" height="16" rx="8" fill="{accent}"/>
          </g>

          <!-- Design Tokens Pill -->
          <g transform="translate(-75, 95)" filter="url(#cardShadow)">
            <rect width="150" height="34" rx="17" fill="#FFFFFF" stroke="{accent}" stroke-width="1.5"/>
            <text x="18" y="21" font-family="'Plus Jakarta Sans', sans-serif" font-size="11" font-weight="800" fill="#1B1D3B">200+ FIGMA TOKENS</text>
          </g>
        </g>
        """
    elif g_type == "tax":
        return f"""
        <!-- Tax & Finance Playbook Graphic -->
        <g transform="translate(630, 240)">
          <circle cx="0" cy="0" r="145" fill="none" stroke="{accent}" stroke-width="1.5" stroke-dasharray="10,6" opacity="0.35"/>
          <circle cx="0" cy="0" r="90" fill="{accent}" opacity="0.16" filter="url(#glowBlur)"/>

          <!-- Holographic 3D Ledger Card -->
          <g transform="translate(-70, -60)" filter="url(#cardShadow)">
            <rect width="140" height="110" rx="14" fill="#1B1D3B" stroke="{accent}" stroke-width="2"/>
            
            <!-- Bar Chart Columns -->
            <rect x="22" y="60" width="18" height="35" rx="4" fill="rgba(255,255,255,0.2)"/>
            <rect x="46" y="45" width="18" height="50" rx="4" fill="{accent}"/>
            <rect x="70" y="30" width="18" height="65" rx="4" fill="{sec_accent}"/>
            <rect x="94" y="18" width="18" height="77" rx="4" fill="#10B981"/>

            <!-- Trendline arrow -->
            <path d="M 22 55 Q 60 25 110 10" fill="none" stroke="#10B981" stroke-width="3" stroke-linecap="round"/>
            <polygon points="112,6 112,18 100,12" fill="#10B981"/>
          </g>

          <!-- 44ADA Compliance Stamp -->
          <g transform="translate(-80, 85)" filter="url(#cardShadow)">
            <rect width="160" height="36" rx="18" fill="#1B1D3B" stroke="#10B981" stroke-width="1.5"/>
            <circle cx="20" cy="18" r="6" fill="#10B981"/>
            <text x="34" y="22" font-family="'Plus Jakarta Sans', sans-serif" font-size="11" font-weight="800" fill="#10B981">SEC. 44ADA COMPLIANT</text>
          </g>
        </g>
        """

def generate_widescreen_cover(c):
    graphic_svg = render_graphic(c['graphic_type'], c['accent'], c['accent_secondary'])

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" width="100%" height="100%">
  <defs>
    <!-- Deep Obsidian Studio Background -->
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0F1126"/>
      <stop offset="45%" stop-color="#151833"/>
      <stop offset="100%" stop-color="#0A0B1A"/>
    </linearGradient>

    <!-- Accent Title Gradient -->
    <linearGradient id="titleAccentGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{c['accent']}"/>
      <stop offset="100%" stop-color="{c['accent_secondary']}"/>
    </linearGradient>

    <!-- Glass Pill Gradient -->
    <linearGradient id="pillGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="rgba(255, 255, 255, 0.12)"/>
      <stop offset="100%" stop-color="rgba(255, 255, 255, 0.03)"/>
    </linearGradient>

    <!-- Fire / Engine Glow -->
    <linearGradient id="fireGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#FF653D"/>
      <stop offset="60%" stop-color="#F59E0B"/>
      <stop offset="100%" stop-color="#EF4444"/>
    </linearGradient>

    <!-- Instagram Gradient -->
    <linearGradient id="igGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#833AB4"/>
      <stop offset="50%" stop-color="#FD1D1D"/>
      <stop offset="100%" stop-color="#FCB045"/>
    </linearGradient>

    <!-- Glow & Shadow Filters -->
    <filter id="glowBlur" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="35" result="blur"/>
    </filter>
    <filter id="fireGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="6" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <filter id="cardShadow" x="-15%" y="-15%" width="130%" height="130%">
      <feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#000000" flood-opacity="0.5"/>
    </filter>
    <pattern id="dotGrid" x="0" y="0" width="24" height="24" patternUnits="userSpaceOnUse">
      <circle cx="2" cy="2" r="1.2" fill="rgba(255, 255, 255, 0.06)"/>
    </pattern>
  </defs>

  <!-- Background Base -->
  <rect width="800" height="500" fill="url(#bgGrad)"/>
  
  <!-- Subtle Dot Grid Overlay -->
  <rect width="800" height="500" fill="url(#dotGrid)"/>

  <!-- Dynamic Ambient Light Blooms -->
  <circle cx="680" cy="180" r="190" fill="{c['accent']}" opacity="0.14" filter="url(#glowBlur)"/>
  <circle cx="120" cy="420" r="160" fill="{c['accent_secondary']}" opacity="0.08" filter="url(#glowBlur)"/>

  <!-- Top Cyber Accent Border Line -->
  <rect x="0" y="0" width="800" height="4" fill="url(#titleAccentGrad)"/>

  <!-- Left Futuristic Framing Spine -->
  <rect x="0" y="0" width="12" height="500" fill="{c['accent']}" opacity="0.85"/>
  <line x1="12" y1="0" x2="12" y2="500" stroke="rgba(255,255,255,0.12)" stroke-width="1.5"/>

  <!-- ================= LEFT CONTENT AREA ================= -->
  
  <!-- Header Branding & Category Tag -->
  <g transform="translate(48, 45)">
    <!-- Official DropKit Droplet Brand Stamp -->
    <rect width="28" height="28" rx="8" fill="#1B1D3B" stroke="rgba(255,255,255,0.2)" stroke-width="1"/>
    <path d="M 14 6 C 18 13 18 17 14 20 C 10 17 10 13 14 6 Z" fill="#FF653D"/>
    
    <text x="38" y="19" font-family="'Plus Jakarta Sans', system-ui, sans-serif" font-size="14" font-weight="800" fill="#FFFFFF" letter-spacing="0.5">DropKit</text>
    <text x="96" y="19" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#74778D" letter-spacing="1.5">PUBLICATIONS // 2026 ARCHITECTURE</text>

    <!-- Category Pill Badge -->
    <g transform="translate(0, 42)">
      <rect width="180" height="26" rx="13" fill="url(#pillGrad)" stroke="{c['tag_color']}" stroke-width="1.2"/>
      <circle cx="14" cy="13" r="4" fill="{c['tag_color']}"/>
      <text x="26" y="17" font-family="system-ui, sans-serif" font-size="10" font-weight="800" fill="{c['tag_color']}" letter-spacing="1">{c['category']}</text>
    </g>
  </g>

  <!-- Main Publication Title (2 Carefully Balanced Lines) -->
  <g transform="translate(48, 175)">
    <text x="0" y="0" font-family="'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" font-size="38" font-weight="800" fill="#FFFFFF" letter-spacing="-0.8">
      {c['title_line1']}
    </text>
    <text x="0" y="46" font-family="'Plus Jakarta Sans', system-ui, -apple-system, sans-serif" font-size="38" font-weight="800" fill="url(#titleAccentGrad)" letter-spacing="-0.8">
      {c['title_line2']}
    </text>
  </g>

  <!-- Editorial Value Subtitle -->
  <g transform="translate(48, 290)">
    <text x="0" y="0" font-family="system-ui, -apple-system, sans-serif" font-size="14" font-weight="400" fill="#9CA3AF" width="420">
      <tspan x="0" dy="0">{c['subtitle'][:62]}</tspan>
      <tspan x="0" dy="22">{c['subtitle'][62:]}</tspan>
    </text>
  </g>

  <!-- 3-Pill Feature Badges -->
  <g transform="translate(48, 375)">
    <!-- Pill 1: Verified PDF -->
    <rect width="105" height="28" rx="8" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.12)" stroke-width="1"/>
    <text x="12" y="18" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#E5E7EB">📄 {c['pages']}</text>

    <!-- Pill 2: Reading Time -->
    <g transform="translate(115, 0)">
      <rect width="115" height="28" rx="8" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.12)" stroke-width="1"/>
      <text x="12" y="18" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#E5E7EB">⏱️ {c['read_time']}</text>
    </g>

    <!-- Pill 3: Instant Dynamic UPI -->
    <g transform="translate(240, 0)">
      <rect width="145" height="28" rx="8" fill="rgba(16, 185, 129, 0.12)" stroke="rgba(16, 185, 129, 0.4)" stroke-width="1"/>
      <circle cx="14" cy="14" r="3.5" fill="#10B981"/>
      <text x="24" y="18" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#10B981">UPI QR VERIFIED</text>
    </g>
  </g>

  <!-- ================= RIGHT 3D VECTOR GRAPHIC ================= -->
  {graphic_svg}

  <!-- ================= BOTTOM SPECIFICATION STRIP ================= -->
  <g transform="translate(48, 455)">
    <line x1="0" y1="0" x2="704" y2="0" stroke="rgba(255,255,255,0.08)" stroke-width="1"/>
    <text x="0" y="24" font-family="monospace" font-size="9" fill="#6B7280" letter-spacing="1">
      AUTHENTICATED DIGITAL PUBLICATION // SPEC: 256-BIT ENCRYPTED PDF // DYNAMIC UPI RECONCILIATION // 2026 EDITION
    </text>
    <text x="704" y="24" font-family="monospace" font-size="9" font-weight="700" fill="{c['accent']}" text-anchor="end" letter-spacing="1">
      SECURE TOKEN FULFILLMENT ✓
    </text>
  </g>
</svg>"""

def main():
    conn = get_connection()
    cursor = conn.cursor()

    for i, c in enumerate(COVERS, start=1):
        svg_content = generate_widescreen_cover(c)
        target_path = PUBLIC_COVER_DIR / c['filename']
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(svg_content)
        print(f"Generated ultra-professional cover: {c['filename']}")

        # Ensure filename is synced in DB
        cursor.execute("UPDATE products SET cover_image = ? WHERE id = ?", (c['filename'], i))

    conn.commit()
    conn.close()
    print("All 6 covers upgraded to ultra-professional 16:10 widescreen studio designs!")

if __name__ == "__main__":
    main()
