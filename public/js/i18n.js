/**
 * DropKit Internationalization (Malayalam <-> English) & Dark/Light Theme System
 */
(function(window) {
  'use strict';

  const translations = {
    en: {
      "nav_home": "Home",
      "nav_products": "All Products",
      "nav_my_downloads": "My Downloads",
      "nav_admin": "Admin Portal",
      "nav_contact": "Support",
      "theme_dark": "Dark Mode",
      "theme_light": "Light Mode",
      "lang_label": "മലയാളം",
      "hero_title": "Sell Digital PDF Guides & Software With Direct UPI",
      "hero_subtitle": "Instant automated delivery of digital products. No high gateway cuts, no complex KYC. Direct payment straight to your merchant UPI ID.",
      "featured_products": "Featured Digital Guides",
      "view_all": "View All Products &rarr;",
      "buy_now": "Buy Now &rarr;",
      "instant_download": "Instant PDF Delivery",
      "pages": "Pages",
      "checkout_title": "Complete Your Order",
      "checkout_sub": "Instant verified delivery to your email address",
      "step_details": "1. Buyer Details & Edition",
      "step_pay": "2. UPI Payment & Screenshot",
      "step_download": "3. Authorized Download",
      "select_pdf_edition": "Select PDF Language Edition:",
      "edition_en": "English Edition",
      "edition_ml": "Malayalam Edition (മലയാളം)",
      "edition_hi": "Hindi Edition (हिन्दी)",
      "full_name": "Full Name *",
      "email_addr": "Email Address (for PDF Delivery) *",
      "phone_number": "Mobile Number (Optional for UPI SMS)",
      "proceed_upi": "Proceed to UPI Payment &rarr;",
      "order_summary": "Order Summary",
      "item_subtotal": "Item Subtotal",
      "upi_fee": "UPI Convenience Fee",
      "free": "Free (₹0.00)",
      "total_payable": "Total Payable:",
      "payee_name": "Payee Name:",
      "payee_upi": "Payee UPI ID:",
      "order_ref": "Order Reference:",
      "copy_upi": "📋 Copy UPI ID",
      "open_upi": "📱 Open in UPI App",
      "select_upi_app": "📱 Select Your UPI Payment App:",
      "tap_app": "Tap an app below",
      "upload_receipt_title": "Upload Original Payment Receipt",
      "share_instruction_1": "Payment Success ആയാൽ നിങ്ങളുടെ UPI App-ലെ Share Receipt / Share Screenshot option ഉപയോഗിച്ച് original payment receipt upload ചെയ്യുക.",
      "share_instruction_2": "Payment വിജയിച്ച ശേഷം UPI ആപ്പിൽ വരുന്ന Share Receipt option വഴി യഥാർത്ഥ payment receipt ഇവിടെ upload ചെയ്യുക.",
      "dropzone_prompt": "Tap to choose from Gallery or drag receipt image here",
      "dropzone_hint": "Original UPI receipt from Google Pay, PhonePe, Paytm, BHIM, Super.money, or Navi (Max 25 MB)",
      "replace_receipt": "🔄 Replace Receipt",
      "upload_btn": "📤 Upload Original Payment Receipt &rarr;",
      "alt_upi_title": "Facing payment failure or bank downtime?",
      "alt_upi_sub": "പേയ്‌മെന്റിൽ എന്തെങ്കിലും പ്രശ്നമോ പരാജയമോ നേരിടുന്നുണ്ടോ? മറ്റൊരു ബാങ്ക് UPI ഐഡിയിലേക്ക് മാറുക.",
      "alt_upi_btn": "🔄 Try Alternative UPI / മറ്റൊരു UPI ഉപയോഗിക്കുക",
      "admin_header_title": "Admin Dashboard",
      "admin_upi_mgmt": "UPI Account Management",
      "admin_analytics": "Sales Analytics",
      "admin_products_mgmt": "Products",
      "admin_orders_mgmt": "Orders",
      "admin_settlements": "Settlements",
      "admin_customers": "Customers",
      "mobile_preview_btn": "📱 Mobile Preview QR"
    },
    ml: {
      "nav_home": "ഹോം",
      "nav_products": "ഉൽപ്പന്നങ്ങൾ",
      "nav_my_downloads": "എന്റെ ഡൗൺലോഡുകൾ",
      "nav_admin": "അഡ്മിൻ പോർട്ടൽ",
      "nav_contact": "സഹായം",
      "theme_dark": "ഡാർക്ക് മോഡ്",
      "theme_light": "ലൈറ്റ് മോഡ്",
      "lang_label": "English",
      "hero_title": "തത്സമയ UPI വഴി ഡിജിറ്റൽ PDF പുസ്തകങ്ങൾ സ്വന്തമാക്കൂ",
      "hero_subtitle": "ഏറ്റവും വേഗത്തിൽ ഡിജിറ്റൽ ഗൈഡുകൾ ലഭ്യമാക്കാം. കമ്മീഷനുകളില്ല, തടസ്സങ്ങളില്ല. നിങ്ങളുടെ വ്യാപാരി UPI ഐഡിയിലേക്ക് നേരിട്ട് പണം.",
      "featured_products": "പ്രത്യേക ഡിജിറ്റൽ ഗൈഡുകൾ",
      "view_all": "എല്ലാ ഉൽപ്പന്നങ്ങളും കാണുക &rarr;",
      "buy_now": "ഇപ്പോൾ വാങ്ങൂ &rarr;",
      "instant_download": "തത്സമയ PDF ഡൗൺലോഡ്",
      "pages": "പേജുകൾ",
      "checkout_title": "ഓർഡർ പൂർത്തിയാക്കുക",
      "checkout_sub": "നിങ്ങളുടെ ഇമെയിലിലേക്ക് തത്സമയം പരിശോധിച്ചു ലഭ്യമാക്കുന്നു",
      "step_details": "1. ഉപഭോക്തൃ വിവരങ്ങളും പതിപ്പും",
      "step_pay": "2. UPI പേയ്‌മെന്റും രസീതും",
      "step_download": "3. സുരക്ഷിത ഡൗൺലോഡ്",
      "select_pdf_edition": "PDF ഭാഷാ പതിപ്പ് തിരഞ്ഞെടുക്കുക:",
      "edition_en": "ഇംഗ്ലീഷ് പതിപ്പ് (English)",
      "edition_ml": "മലയാളം പതിപ്പ് (Original)",
      "edition_hi": "ഹിന്ദി പതിപ്പ് (हिन्दी)",
      "full_name": "പൂർണ്ണ പേര് *",
      "email_addr": "ഇമെയിൽ വിലാസം (PDF ലഭിക്കുന്നതിനായി) *",
      "phone_number": "മൊബൈൽ നമ്പർ (ഓപ്ഷണൽ)",
      "proceed_upi": "UPI പേയ്‌മെന്റിലേക്ക് പോകുക &rarr;",
      "order_summary": "ഓർഡർ വിവരങ്ങൾ",
      "item_subtotal": "ഉൽപ്പന്ന വില",
      "upi_fee": "UPI ചാർജ്ജ്",
      "free": "സൗജന്യം (₹0.00)",
      "total_payable": "ആകെ നൽകേണ്ട തുക:",
      "payee_name": "സ്വീകർത്താവിന്റെ പേര്:",
      "payee_upi": "വ്യാപാരി UPI ഐഡി:",
      "order_ref": "ഓർഡർ നമ്പർ:",
      "copy_upi": "📋 UPI കോപ്പി ചെയ്യുക",
      "open_upi": "📱 UPI ആപ്പിൽ തുറക്കുക",
      "select_upi_app": "📱 നിങ്ങളുടെ UPI ആപ്പ് തിരഞ്ഞെടുക്കുക:",
      "tap_app": "താഴെ കാണുന്ന ആപ്പിൽ ക്ലിക്ക് ചെയ്യുക",
      "upload_receipt_title": "യഥാർത്ഥ പേയ്‌മെന്റ് രസീത് അപ്‌ലോഡ് ചെയ്യുക",
      "share_instruction_1": "Payment Success ആയാൽ നിങ്ങളുടെ UPI App-ലെ Share Receipt / Share Screenshot option ഉപയോഗിച്ച് original payment receipt upload ചെയ്യുക.",
      "share_instruction_2": "Payment വിജയിച്ച ശേഷം UPI ആപ്പിൽ വരുന്ന Share Receipt option വഴി യഥാർത്ഥ payment receipt ഇവിടെ upload ചെയ്യുക.",
      "dropzone_prompt": "ഗാലറിയിൽ നിന്ന് തിരഞ്ഞെടുക്കാൻ ക്ലിക്ക് ചെയ്യുക അല്ലെങ്കിൽ ഡ്രാഗ് ചെയ്യുക",
      "dropzone_hint": "Google Pay, PhonePe, Paytm, BHIM, Super.money, Navi എന്നിവയിലെ ഒറിജിനൽ രസീത് (പരമാവധി 25 MB)",
      "replace_receipt": "🔄 രസീത് മാറ്റുക",
      "upload_btn": "📤 ഒറിജിനൽ പേയ്‌മെന്റ് രസീത് അപ്‌ലോഡ് ചെയ്യുക &rarr;",
      "alt_upi_title": "പേയ്‌മെന്റിൽ തടസ്സം നേരിടുന്നുണ്ടോ?",
      "alt_upi_sub": "ബാങ്ക് സെർവർ പ്രശ്നമുണ്ടെങ്കിൽ മറ്റൊരു സ്ഥിരീകരിച്ച UPI ഐഡി ഉപയോഗിക്കാം.",
      "alt_upi_btn": "🔄 മറ്റൊരു UPI ഐഡി ഉപയോഗിക്കുക",
      "admin_header_title": "അഡ്മിൻ ഡാഷ്‌ബോർഡ്",
      "admin_upi_mgmt": "UPI അക്കൗണ്ട് മാനേജ്‌മെന്റ്",
      "admin_analytics": "വിൽപ്പന അവലോകനം",
      "admin_products_mgmt": "ഉൽപ്പന്നങ്ങൾ",
      "admin_orders_mgmt": "ഓർഡറുകൾ",
      "admin_settlements": "സെറ്റിൽമെന്റുകൾ",
      "admin_customers": "ഉപഭോക്താക്കൾ",
      "mobile_preview_btn": "📱 ഫോണിൽ തുറക്കാനുള്ള QR"
    }
  };

  const DropKitI18n = {
    getLanguage: function() {
      return localStorage.getItem('dropkit_lang') || 'en';
    },

    setLanguage: function(lang) {
      if (!translations[lang]) lang = 'en';
      localStorage.setItem('dropkit_lang', lang);
      document.documentElement.setAttribute('data-lang', lang);
      this.applyTranslations();
      this.updateSwitcherUI();
    },

    toggleLanguage: function() {
      const current = this.getLanguage();
      const next = current === 'en' ? 'ml' : 'en';
      this.setLanguage(next);
    },

    getTheme: function() {
      return localStorage.getItem('dropkit_theme') || 'light';
    },

    setTheme: function(theme) {
      if (theme !== 'dark' && theme !== 'light') theme = 'light';
      localStorage.setItem('dropkit_theme', theme);
      document.documentElement.setAttribute('data-theme', theme);
      this.updateSwitcherUI();
    },

    toggleTheme: function() {
      const current = this.getTheme();
      const next = current === 'dark' ? 'light' : 'dark';
      this.setTheme(next);
    },

    t: function(key) {
      const lang = this.getLanguage();
      return (translations[lang] && translations[lang][key]) || (translations.en && translations.en[key]) || key;
    },

    applyTranslations: function() {
      const lang = this.getLanguage();
      const dict = translations[lang] || translations.en;

      document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (dict[key]) {
          if (el.tagName === 'INPUT' && (el.type === 'button' || el.type === 'submit')) {
            el.value = dict[key];
          } else {
            el.innerHTML = dict[key];
          }
        }
      });
    },

    updateSwitcherUI: function() {
      const lang = this.getLanguage();
      const theme = this.getTheme();

      document.querySelectorAll('.lang-toggle-btn').forEach(btn => {
        btn.innerHTML = lang === 'en' ? '🌐 മലയാളം' : '🌐 English';
        btn.title = lang === 'en' ? 'Switch to Malayalam' : 'Switch to English';
      });

      document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
        btn.innerHTML = theme === 'dark' ? '☀️ Light' : '🌙 Dark';
        btn.title = theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode';
      });
    },

    mountSwitchers: function(targetContainer) {
      if (!targetContainer) return;
      const wrap = document.createElement('div');
      wrap.className = 'switchers-wrap';
      wrap.innerHTML = `
        <button type="button" class="switch-pill-btn lang-toggle-btn" onclick="DropKitI18n.toggleLanguage()" title="Change Language">
          🌐 മലയാളം
        </button>
        <button type="button" class="switch-pill-btn theme-toggle-btn" onclick="DropKitI18n.toggleTheme()" title="Toggle Dark/Light Mode">
          🌙 Dark
        </button>
      `;
      targetContainer.appendChild(wrap);
      this.updateSwitcherUI();
    },

    init: function() {
      const savedTheme = this.getTheme();
      document.documentElement.setAttribute('data-theme', savedTheme);

      const savedLang = this.getLanguage();
      document.documentElement.setAttribute('data-lang', savedLang);

      // Apply translations after DOM is ready
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
          this.applyTranslations();
          this.updateSwitcherUI();
        });
      } else {
        this.applyTranslations();
        this.updateSwitcherUI();
      }
    }
  };

  DropKitI18n.init();
  window.DropKitI18n = DropKitI18n;
})(window);
