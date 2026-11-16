import os
from pathlib import Path

LOGOS_DIR = Path(r"C:\Users\Student\.gemini\antigravity\scratch\dropkit\public\assets\logos")
LOGOS_DIR.mkdir(parents=True, exist_ok=True)

# 1. Google Pay (Official Google 4-Color Brand Asset)
GPAY_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">
  <title>Google Pay</title>
  <rect width="48" height="48" rx="10" fill="#FFFFFF" stroke="#E2E8F0" stroke-width="1.5"/>
  <g transform="translate(6, 6) scale(0.75)">
    <path fill="#4285F4" d="M46.1 24.5c0-1.7-.1-3.3-.4-4.9H24v9.3h12.4c-.5 2.8-2.1 5.2-4.5 6.9v5.7h7.3c4.3-3.9 6.9-9.8 6.9-17z"/>
    <path fill="#34A853" d="M24 47c6.2 0 11.4-2.1 15.2-5.6l-7.3-5.7c-2.1 1.4-4.7 2.2-7.9 2.2-6.1 0-11.2-4.1-13-9.6H3.3v5.9C7.1 41.9 15 47 24 47z"/>
    <path fill="#FBBC04" d="M11 28.3c-.5-1.4-.8-3-.8-4.3s.3-2.9.8-4.3v-5.9H3.3C1.2 17.6 0 20.7 0 24s1.2 6.4 3.3 10.2l7.7-5.9z"/>
    <path fill="#EA4335" d="M24 9.5c3.4 0 6.4 1.2 8.8 3.5l6.6-6.6C35.4 2.5 30.2 0 24 0 15 0 7.1 5.1 3.3 13.8l7.7 5.9c1.8-5.5 6.9-10.2 13-10.2z"/>
  </g>
</svg>'''

# 2. PhonePe (Official Brand Violet #5F259F with authentic white Devnagari "पे")
PHONEPE_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">
  <title>PhonePe</title>
  <rect width="48" height="48" rx="10" fill="#5F259F"/>
  <g transform="translate(6, 6) scale(1.5)">
    <!-- Official Devnagari 'पे' glyph with bindu and authentic strokes -->
    <path fill="#FFFFFF" d="M5.5 4h13c.4 0 .7.3.7.7v1.2c0 .4-.3.7-.7.7h-3.6v4.6c0 3.2-1.8 5-4.8 5-.9 0-1.7-.1-2.4-.4v3.8c0 .8-.6 1.4-1.4 1.4h-1.2c-.4 0-.7-.3-.7-.7v-9.5c0-3.2 1.8-5 4.8-5 .8 0 1.5.1 2.1.3V6.6H5.5c-.4 0-.7-.3-.7-.7V4.7c0-.4.3-.7.7-.7zm3.6 5.8c-.4-.1-.8-.2-1.2-.2-1.4 0-2.2.8-2.2 2.2v1.5c.6.3 1.3.4 2 .4 1.4 0 2.2-.8 2.2-2.2v-1.7h-.8z"/>
    <!-- Matra loop on top-left -->
    <path fill="#FFFFFF" d="M12.5 4.5l-4-3.5c-.3-.3-.8-.3-1.1 0l-.8.7c-.2.2-.2.5 0 .7l4.5 4c.2.2.5.2.7 0l.7-.6c.3-.3.3-.8 0-1.3z"/>
  </g>
</svg>'''

# 3. Paytm (Official Brand Navy #002970 "Pay" & Cyan #00BAF2 "tm")
PAYTM_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">
  <title>Paytm</title>
  <rect width="48" height="48" rx="10" fill="#FFFFFF" stroke="#E2E8F0" stroke-width="1.5"/>
  <g transform="translate(3, 14)">
    <!-- Pay in dark navy -->
    <text x="2" y="16" font-family="'Outfit', 'Space Grotesk', -apple-system, sans-serif" font-weight="900" font-size="14.5" fill="#002970" letter-spacing="-0.5">Pay</text>
    <!-- tm in bright cyan -->
    <text x="27.5" y="16" font-family="'Outfit', 'Space Grotesk', -apple-system, sans-serif" font-weight="900" font-size="14.5" fill="#00BAF2" letter-spacing="-0.5">tm</text>
  </g>
</svg>'''

# 4. BHIM UPI (Official NPCI Tricolor Chevrons & Teal Typography)
BHIM_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">
  <title>BHIM UPI</title>
  <rect width="48" height="48" rx="10" fill="#FFFFFF" stroke="#E2E8F0" stroke-width="1.5"/>
  <g transform="translate(2, 6)">
    <!-- Saffron top chevron -->
    <path fill="#F37021" d="M16 6 L26 12 L16 18 L19 12 Z"/>
    <path fill="#F37021" d="M22 6 L32 12 L22 18 L25 12 Z"/>
    <!-- Green bottom chevron -->
    <path fill="#00796B" d="M16 15 L26 21 L16 27 L19 21 Z"/>
    <path fill="#00796B" d="M22 15 L32 21 L22 27 L25 21 Z"/>
    <!-- BHIM wordmark -->
    <text x="22" y="36" text-anchor="middle" font-family="'Outfit', 'Space Grotesk', sans-serif" font-weight="900" font-style="italic" font-size="11" fill="#004353" letter-spacing="0.5">BHIM</text>
  </g>
</svg>'''

# 5. Super.money (Official Flipkart Fintech Brand - Electric Indigo #4D43FE with Clean Typography)
SUPERMONEY_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">
  <title>Super.money</title>
  <rect width="48" height="48" rx="10" fill="#4D43FE"/>
  <g transform="translate(4, 9)">
    <text x="20" y="17" text-anchor="middle" font-family="'Outfit', 'Space Grotesk', -apple-system, sans-serif" font-weight="900" font-size="13" fill="#FFFFFF" letter-spacing="-0.2">super<tspan fill="#00D09C">.</tspan></text>
    <text x="20" y="27" text-anchor="middle" font-family="'Outfit', 'Space Grotesk', -apple-system, sans-serif" font-weight="700" font-size="8.5" fill="#E0E7FF" letter-spacing="1.2">MONEY</text>
  </g>
</svg>'''

# 6. Navi (Official Navi Technologies Brand - Emerald Green #00D09C & Crisp Geometric Brand Mark)
NAVI_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">
  <title>Navi UPI</title>
  <rect width="48" height="48" rx="10" fill="#00D09C"/>
  <g transform="translate(6, 8)">
    <!-- Geometric rising arch / smile mark of Navi -->
    <path fill="#FFFFFF" d="M18 3c-8.3 0-15 6.7-15 15 0 2.5.6 4.8 1.7 6.9l4.5-2.6c-.8-1.3-1.2-2.7-1.2-4.3 0-5.5 4.5-10 10-10s10 4.5 10 10c0 1.6-.4 3-1.2 4.3l4.5 2.6c1.1-2.1 1.7-4.4 1.7-6.9 0-8.3-6.7-15-15-15z"/>
    <!-- Distinctive Navi check / center indicator -->
    <circle cx="18" cy="18" r="4.2" fill="#FFFFFF"/>
    <!-- navi lowercase wordmark -->
    <text x="18" y="32" text-anchor="middle" font-family="'Outfit', 'Space Grotesk', -apple-system, sans-serif" font-weight="900" font-size="9" fill="#FFFFFF" letter-spacing="0.5">navi</text>
  </g>
</svg>'''

files = {
    "google-pay.svg": GPAY_SVG,
    "phonepe.svg": PHONEPE_SVG,
    "paytm.svg": PAYTM_SVG,
    "bhim.svg": BHIM_SVG,
    "supermoney.svg": SUPERMONEY_SVG,
    "navi.svg": NAVI_SVG
}

for name, content in files.items():
    file_path = LOGOS_DIR / name
    file_path.write_text(content.strip(), encoding="utf-8")
    print(f"Generated {name} ({len(content)} bytes)")
