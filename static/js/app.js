/**
 * Bakery Management System - Core Client Utilities & Audio FX
 */

// Web Audio API Sound Synthesizer for tactile feedback
const SoundFX = {
  ctx: null,
  init() {
    if (!this.ctx && (window.AudioContext || window.webkitAudioContext)) {
      this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    }
  },
  playClick() {
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(800, this.ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(400, this.ctx.currentTime + 0.05);
      gain.gain.setValueAtTime(0.15, this.ctx.currentTime);
      gain.gain.linearRampToValueAtTime(0.01, this.ctx.currentTime + 0.05);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + 0.05);
    } catch(e) {}
  },
  playSuccess() {
    try {
      this.init();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;
      // Chime note 1
      const osc1 = this.ctx.createOscillator();
      const gain1 = this.ctx.createGain();
      osc1.frequency.setValueAtTime(523.25, now); // C5
      gain1.gain.setValueAtTime(0.2, now);
      gain1.gain.linearRampToValueAtTime(0.01, now + 0.2);
      osc1.connect(gain1);
      gain1.connect(this.ctx.destination);
      osc1.start(now);
      osc1.stop(now + 0.2);

      // Chime note 2
      const osc2 = this.ctx.createOscillator();
      const gain2 = this.ctx.createGain();
      osc2.frequency.setValueAtTime(659.25, now + 0.1); // E5
      gain2.gain.setValueAtTime(0.2, now + 0.1);
      gain2.gain.linearRampToValueAtTime(0.01, now + 0.35);
      osc2.connect(gain2);
      gain2.connect(this.ctx.destination);
      osc2.start(now + 0.1);
      osc2.stop(now + 0.35);
    } catch(e) {}
  },
  playBeep() {
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'square';
      osc.frequency.setValueAtTime(1200, this.ctx.currentTime);
      gain.gain.setValueAtTime(0.1, this.ctx.currentTime);
      gain.gain.linearRampToValueAtTime(0.01, this.ctx.currentTime + 0.08);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + 0.08);
    } catch(e) {}
  }
};

// Multi-Currency Configuration & Conversion Helpers
const CURRENCY_CONFIG = {
  VND: { symbol: '₫', rate: 1.0, locale: 'vi-VN', decimals: 0, prefix: false, label: 'VND (₫)' },
  USD: { symbol: '$', rate: 1 / 25400, locale: 'en-US', decimals: 2, prefix: true, label: 'USD ($)' },
  EUR: { symbol: '€', rate: 1 / 27500, locale: 'de-DE', decimals: 2, prefix: false, label: 'EUR (€)' },
  GBP: { symbol: '£', rate: 1 / 32500, locale: 'en-GB', decimals: 2, prefix: true, label: 'GBP (£)' },
  JPY: { symbol: '¥', rate: 1 / 165, locale: 'ja-JP', decimals: 0, prefix: true, label: 'JPY (¥)' },
  CNY: { symbol: '¥', rate: 1 / 3550, locale: 'zh-CN', decimals: 1, prefix: true, label: 'CNY (¥)' },
};

function getActiveCurrency() {
  return localStorage.getItem('bakery_currency') || 'VND';
}

function setActiveCurrency(curr) {
  if (CURRENCY_CONFIG[curr]) {
    localStorage.setItem('bakery_currency', curr);
    window.dispatchEvent(new CustomEvent('currencyChanged', { detail: { currency: curr } }));
    updatePageCurrencies();
  }
}

function formatCurrency(amountVND, curr) {
  const c = curr || getActiveCurrency();
  const cfg = CURRENCY_CONFIG[c] || CURRENCY_CONFIG.VND;
  const num = parseFloat(amountVND) || 0;
  const converted = num * cfg.rate;
  const numStr = new Intl.NumberFormat(cfg.locale, {
    minimumFractionDigits: cfg.decimals,
    maximumFractionDigits: cfg.decimals,
  }).format(converted);

  if (cfg.prefix) {
    return `${cfg.symbol}${numStr}`;
  }
  return `${numStr} ${cfg.symbol}`;
}

// Backward-compatible formatVND that respects the active selected currency
function formatVND(amount) {
  return formatCurrency(amount);
}

function updatePageCurrencies() {
  document.querySelectorAll('[data-vnd]').forEach(el => {
    const raw = el.getAttribute('data-vnd');
    const vnd = parseFloat(raw);
    if (!isNaN(vnd)) {
      el.textContent = formatCurrency(vnd);
    }
  });
  document.querySelectorAll('.currency-selector').forEach(sel => {
    sel.value = getActiveCurrency();
  });
}

document.addEventListener('DOMContentLoaded', () => {
  updatePageCurrencies();
});

// Global Toast notification
function showToast(message, type = 'success') {
  let toastContainer = document.getElementById('toast-container');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toast-container';
    toastContainer.className = 'fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-sm pointer-events-none';
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement('div');
  const bgColors = {
    success: 'bg-emerald-600 text-white border-emerald-500',
    error: 'bg-rose-600 text-white border-rose-500',
    warning: 'bg-amber-500 text-white border-amber-400',
    info: 'bg-amber-900 text-white border-amber-800',
  };

  toast.className = `${bgColors[type] || bgColors.info} border px-4 py-3 rounded-2xl shadow-xl flex items-center gap-3 text-sm font-medium transition-all duration-300 transform translate-y-4 opacity-0 pointer-events-auto`;
  toast.innerHTML = `
    <span class="text-base">${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span>
    <span class="flex-1">${message}</span>
  `;

  toastContainer.appendChild(toast);

  // Trigger sound
  if (type === 'success') SoundFX.playSuccess();
  else if (type === 'error') SoundFX.playBeep();
  else SoundFX.playClick();

  requestAnimationFrame(() => {
    toast.classList.remove('translate-y-4', 'opacity-0');
  });

  setTimeout(() => {
    toast.classList.add('opacity-0', 'translate-y-2');
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// CSRF helper for Django fetch
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta && meta.content && meta.content.length > 10) return meta.content;
  return getCookie('csrftoken') || '';
}

window.getCsrfToken = getCsrfToken;
window.CSRF_TOKEN = getCsrfToken();

// Dropdown menu click-persistence & outside-click dismiss
document.addEventListener('DOMContentLoaded', () => {
  const catalogBtn = document.getElementById('admin-catalog-btn');
  const catalogDropdown = document.getElementById('admin-catalog-dropdown');
  if (catalogBtn && catalogDropdown) {
    catalogBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      catalogDropdown.classList.toggle('!block');
    });
    document.addEventListener('click', (e) => {
      if (!catalogDropdown.contains(e.target) && !catalogBtn.contains(e.target)) {
        catalogDropdown.classList.remove('!block');
      }
    });
  }

  // ==========================================
  // MOBILE OFFCANVAS DRAWER CONTROLS
  // ==========================================
  window.openMobileDrawer = function() {
    const drawer = document.getElementById('mobile-drawer');
    if (!drawer) return;
    drawer.classList.remove('drawer-closed');
    drawer.classList.add('drawer-open');
    document.body.style.overflow = 'hidden';
    if (typeof SoundFX !== 'undefined' && SoundFX.playClick) {
      SoundFX.playClick();
    }
  };

  window.closeMobileDrawer = function() {
    const drawer = document.getElementById('mobile-drawer');
    if (!drawer) return;
    drawer.classList.remove('drawer-open');
    drawer.classList.add('drawer-closed');
    document.body.style.overflow = '';
  };

  window.toggleMobileDrawer = function() {
    const drawer = document.getElementById('mobile-drawer');
    if (!drawer) return;
    if (drawer.classList.contains('drawer-open')) {
      window.closeMobileDrawer();
    } else {
      window.openMobileDrawer();
    }
  };

  window.setAppLanguage = function(langCode) {
    if (!langCode) return;
    const nextPath = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = '/set-language/' + encodeURIComponent(langCode) + '/?next=' + nextPath;
  };

  // NOTE: toggle/close/backdrop use inline onclick handlers in base.html.
  // Adding listeners here too would double-fire the toggle (open then close).

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      window.closeMobileDrawer();
    }
  });

  // ==========================================
  // PWA SERVICE WORKER REGISTRATION & INSTALLATION
  // ==========================================
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .then((reg) => {
        console.log('✅ Artisan Bakery PWA Service Worker registered:', reg.scope);
      })
      .catch((err) => {
        console.warn('⚠️ Service Worker registration skipped:', err);
      });
  }

  let deferredInstallPrompt = null;
  const pwaBanner = document.getElementById('pwa-install-banner');
  const pwaConfirm = document.getElementById('pwa-install-confirm');
  const pwaDismiss = document.getElementById('pwa-install-dismiss');
  const drawerInstallBtn = document.getElementById('drawer-pwa-install-btn');

  // Check if running in standalone app mode
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

  if (isStandalone) {
    console.log('🚀 Artisan Bakery running in Standalone PWA App Mode');
    if (drawerInstallBtn) drawerInstallBtn.style.display = 'none';
  } else {
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      deferredInstallPrompt = e;
      const dismissed = sessionStorage.getItem('pwa_banner_dismissed');
      if (!dismissed && pwaBanner) {
        setTimeout(() => {
          pwaBanner.classList.remove('hidden');
        }, 1500);
      }
    });

    async function triggerPwaInstall() {
      if (deferredInstallPrompt) {
        deferredInstallPrompt.prompt();
        const { outcome } = await deferredInstallPrompt.userChoice;
        console.log(`PWA install prompt outcome: ${outcome}`);
        deferredInstallPrompt = null;
        if (pwaBanner) pwaBanner.classList.add('hidden');
      } else {
        showToast('Để cài đặt ứng dụng: Bấm biểu tượng Chia Sẻ (iOS) hoặc Menu 3 chấm (Android) và chọn "Thêm vào màn hình chính"', 'info');
      }
    }

    if (pwaConfirm) pwaConfirm.addEventListener('click', triggerPwaInstall);
    if (drawerInstallBtn) drawerInstallBtn.addEventListener('click', triggerPwaInstall);

    if (pwaDismiss) {
      pwaDismiss.addEventListener('click', () => {
        if (pwaBanner) pwaBanner.classList.add('hidden');
        sessionStorage.setItem('pwa_banner_dismissed', 'true');
      });
    }
  }

  // Update mobile cart badge if exists
  function syncMobileCartBadge() {
    const desktopCartCount = document.getElementById('online-cart-count');
    const mobileCartBadge = document.getElementById('mobile-cart-badge');
    if (desktopCartCount && mobileCartBadge) {
      const count = parseInt(desktopCartCount.innerText) || 0;
      mobileCartBadge.innerText = count;
      if (count > 0) mobileCartBadge.classList.remove('hidden');
      else mobileCartBadge.classList.add('hidden');
    }
  }
  syncMobileCartBadge();
  window.addEventListener('cartUpdated', syncMobileCartBadge);
});

