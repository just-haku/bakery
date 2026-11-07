/**
 * Artisan Bakery - QR Code Scanner & Stock-In Module (Nhập Hàng Bằng QR Code)
 * Powered by Html5Qrcode & Web Audio API
 */
(function() {
  let html5QrCode = null;
  let isScanning = false;
  let currentScannedItem = null;

  // Synthesize pleasant scan beep using Web Audio API (Offline & Instant)
  function playBeep(freq = 880, duration = 0.12, type = 'sine') {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
      gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + duration);
    } catch (e) {
      console.warn('AudioContext not allowed or not supported', e);
    }
  }

  function getCsrfToken() {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, 10) === ('csrftoken=')) {
          cookieValue = decodeURIComponent(cookie.substring(10));
          break;
        }
      }
    }
    return cookieValue || '';
  }

  function ensureModal() {
    let modal = document.getElementById('qr-stockin-modal');
    if (modal) return modal;

    modal = document.createElement('div');
    modal.id = 'qr-stockin-modal';
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/75 backdrop-blur-sm hidden';
    modal.innerHTML = `
      <div class="bg-white rounded-3xl max-w-md w-full p-5 sm:p-6 shadow-2xl border border-amber-200 space-y-4 my-auto overflow-hidden animate-scale-up">
        <!-- Header -->
        <div class="flex items-center justify-between pb-3 border-b border-amber-100">
          <div class="flex items-center gap-2.5">
            <div class="w-10 h-10 rounded-2xl bg-amber-500 text-white flex items-center justify-center text-xl shadow-sm">
              📷
            </div>
            <div>
              <h3 class="font-black text-base text-amber-950">Quét QR Code Nhập Hàng</h3>
              <p class="text-[11px] text-amber-700 font-semibold" id="qr-scanner-hint">Hướng camera về phía mã QR hoặc Barcode</p>
            </div>
          </div>
          <button type="button" onclick="window.closeQrStockInModal()" class="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-500 hover:text-gray-800 flex items-center justify-center text-lg font-bold transition">&times;</button>
        </div>

        <!-- Scanner Viewfinder Box -->
        <div id="qr-camera-container" class="relative rounded-2xl overflow-hidden bg-black flex flex-col items-center justify-center min-h-[260px] border border-amber-300">
          <div id="qr-reader" class="w-full"></div>
          <div id="qr-scan-overlay" class="absolute inset-0 pointer-events-none flex items-center justify-center">
            <div class="w-48 h-48 border-2 border-amber-400 rounded-2xl relative shadow-lg">
              <span class="absolute top-0 left-0 w-4 h-4 border-t-4 border-l-4 border-amber-500 -mt-1 -ml-1"></span>
              <span class="absolute top-0 right-0 w-4 h-4 border-t-4 border-r-4 border-amber-500 -mt-1 -mr-1"></span>
              <span class="absolute bottom-0 left-0 w-4 h-4 border-b-4 border-l-4 border-amber-500 -mb-1 -ml-1"></span>
              <span class="absolute bottom-0 right-0 w-4 h-4 border-b-4 border-r-4 border-amber-500 -mb-1 -mr-1"></span>
              <div class="w-full h-0.5 bg-gradient-to-r from-transparent via-amber-400 to-transparent absolute top-1/2 -translate-y-1/2 animate-pulse"></div>
            </div>
          </div>
          <div id="qr-camera-loading" class="absolute inset-0 bg-gray-900/90 text-white flex flex-col items-center justify-center gap-2 text-xs font-bold">
            <div class="w-7 h-7 border-3 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
            <span>Đang kích hoạt camera...</span>
          </div>
        </div>

        <!-- Scanned Item Card (Hidden until scan match) -->
        <div id="qr-scanned-card" class="hidden bg-amber-50/80 rounded-2xl p-4 border border-amber-200 space-y-3">
          <div class="flex items-start justify-between gap-2">
            <div>
              <span id="qr-item-badge" class="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-amber-600 text-white">Sản Phẩm</span>
              <h4 id="qr-item-name" class="font-black text-sm text-amber-950 mt-1 leading-tight">Bánh Mì Nghệ Nhân</h4>
              <p class="text-xs font-mono text-gray-500 mt-0.5">Mã: <b id="qr-item-code" class="text-amber-800">BK01</b></p>
            </div>
            <div class="text-right flex-shrink-0">
              <span class="text-[10px] text-gray-500 font-bold block">Tồn hiện tại:</span>
              <span id="qr-item-stock" class="text-base font-black text-amber-900">0</span>
              <span id="qr-item-unit" class="text-xs font-bold text-gray-600">cái</span>
            </div>
          </div>

          <!-- Quantity Input & Quick Chips -->
          <div>
            <label class="block text-xs font-bold text-amber-950 mb-1.5">Số Lượng Nhập Thêm:</label>
            <div class="flex items-center gap-2">
              <button type="button" onclick="window.stepQrQty(-1)" class="w-10 h-10 rounded-xl bg-white border border-amber-300 font-black text-base text-amber-950 hover:bg-amber-100 flex items-center justify-center btn-tactile">-</button>
              <input type="number" id="qr-input-quantity" value="10" min="1" max="99999" class="flex-1 h-10 text-center font-black text-lg bg-white border border-amber-300 rounded-xl focus:ring-2 focus:ring-amber-500 focus:outline-none">
              <button type="button" onclick="window.stepQrQty(1)" class="w-10 h-10 rounded-xl bg-white border border-amber-300 font-black text-base text-amber-950 hover:bg-amber-100 flex items-center justify-center btn-tactile">+</button>
            </div>
            <div class="grid grid-cols-4 gap-1.5 mt-2">
              <button type="button" onclick="window.setQrQty(5)" class="py-1 rounded-lg bg-white border border-amber-200 text-xs font-bold text-amber-900 hover:bg-amber-100">+5</button>
              <button type="button" onclick="window.setQrQty(10)" class="py-1 rounded-lg bg-white border border-amber-200 text-xs font-bold text-amber-900 hover:bg-amber-100">+10</button>
              <button type="button" onclick="window.setQrQty(20)" class="py-1 rounded-lg bg-white border border-amber-200 text-xs font-bold text-amber-900 hover:bg-amber-100">+20</button>
              <button type="button" onclick="window.setQrQty(50)" class="py-1 rounded-lg bg-white border border-amber-200 text-xs font-bold text-amber-900 hover:bg-amber-100">+50</button>
            </div>
          </div>

          <!-- Confirm Restock Button -->
          <div class="flex gap-2 pt-1">
            <button type="button" onclick="window.resumeQrScanning()" class="w-1/3 py-2.5 rounded-xl border border-gray-300 bg-white hover:bg-gray-50 text-gray-700 text-xs font-bold transition">
              Quét Lại
            </button>
            <button type="button" id="qr-btn-submit-stock" onclick="window.submitQrStockIn()" class="flex-1 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-black shadow-md shadow-emerald-600/30 transition btn-tactile">
              ✓ Xác Nhận Nhập Kho
            </button>
          </div>
        </div>

        <!-- Manual SKU input fallback -->
        <div class="pt-2 border-t border-amber-100 flex gap-2">
          <input type="text" id="qr-manual-code" placeholder="Hoặc nhập mã SKU tay..." class="flex-1 px-3 py-2 text-xs border border-gray-300 rounded-xl font-bold uppercase focus:ring-1 focus:ring-amber-500 focus:outline-none">
          <button type="button" onclick="window.searchManualSku()" class="px-3 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-bold btn-tactile">
            Tra Cứu
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    return modal;
  }

  window.openQrStockInModal = async function() {
    const modal = ensureModal();
    modal.classList.remove('hidden');

    const loadingEl = document.getElementById('qr-camera-loading');
    if (loadingEl) loadingEl.style.display = 'flex';

    document.getElementById('qr-scanned-card')?.classList.add('hidden');
    document.getElementById('qr-camera-container')?.classList.remove('hidden');

    if (typeof Html5Qrcode === 'undefined') {
      alert('Thư viện quét mã chưa được tải. Vui lòng tải lại trang.');
      return;
    }

    try {
      if (!html5QrCode) {
        html5QrCode = new Html5Qrcode("qr-reader");
      }

      const config = {
        fps: 10,
        qrbox: { width: 220, height: 220 },
        aspectRatio: 1.0
      };

      await html5QrCode.start(
        { facingMode: "environment" },
        config,
        onScanSuccess,
        onScanError
      );
      isScanning = true;
      if (loadingEl) loadingEl.style.display = 'none';
    } catch (err) {
      console.warn('Camera start error:', err);
      if (loadingEl) {
        loadingEl.innerHTML = `
          <span class="text-rose-400 font-bold">Không thể mở Camera</span>
          <span class="text-[11px] text-gray-300 text-center px-4">Hãy kiểm tra quyền cấp Camera hoặc dùng ô nhập mã tay bên dưới.</span>
        `;
      }
    }
  };

  window.closeQrStockInModal = async function() {
    const modal = document.getElementById('qr-stockin-modal');
    if (modal) modal.classList.add('hidden');
    if (html5QrCode && isScanning) {
      try {
        await html5QrCode.stop();
      } catch (e) {}
      isScanning = false;
    }
  };

  let scanCooldown = false;
  async function onScanSuccess(decodedText) {
    if (scanCooldown) return;
    scanCooldown = true;
    setTimeout(() => { scanCooldown = false; }, 2000);

    playBeep(987, 0.15, 'sine');
    await lookupItem(decodedText);
  }

  function onScanError(errorMessage) {
    // Normal frame noise, do nothing
  }

  async function lookupItem(code) {
    if (!code) return;
    code = code.trim();

    const hint = document.getElementById('qr-scanner-hint');
    if (hint) hint.textContent = `Đang tìm thông tin mã: ${code}...`;

    try {
      const res = await fetch(`/inventory/api/qr-stock-in/?code=${encodeURIComponent(code)}`);
      const data = await res.json();

      if (data.success && data.found) {
        currentScannedItem = data;
        playBeep(1318, 0.12, 'triangle');

        // Populate Scanned Card
        document.getElementById('qr-item-badge').textContent = data.item_type === 'product' ? 'Bánh Thành Phẩm' : 'Nguyên Vật Liệu';
        document.getElementById('qr-item-name').textContent = data.name;
        document.getElementById('qr-item-code').textContent = data.code;
        document.getElementById('qr-item-stock').textContent = data.current_stock;
        document.getElementById('qr-item-unit').textContent = data.unit;
        document.getElementById('qr-input-quantity').value = (data.item_type === 'product' ? 10 : 5);

        // Pause camera preview
        if (html5QrCode && isScanning) {
          try { html5QrCode.pause(); } catch (e) {}
        }

        document.getElementById('qr-scanned-card').classList.remove('hidden');
        if (hint) hint.textContent = 'Đã nhận diện mã! Nhập số lượng và xác nhận nhập kho.';
      } else {
        playBeep(440, 0.2, 'sawtooth');
        if (hint) hint.textContent = `❌ ${data.message || 'Không tìm thấy sản phẩm'}`;
        if (typeof showToast === 'function') {
          showToast(`Không tìm thấy hàng khớp mã ${code}`, 'error');
        }
      }
    } catch (e) {
      console.error('Lookup error:', e);
      if (hint) hint.textContent = 'Lỗi kết nối máy chủ khi tra cứu mã.';
    }
  }

  window.resumeQrScanning = function() {
    currentScannedItem = null;
    document.getElementById('qr-scanned-card')?.classList.add('hidden');
    const hint = document.getElementById('qr-scanner-hint');
    if (hint) hint.textContent = 'Hướng camera về phía mã QR hoặc Barcode';

    if (html5QrCode) {
      try { html5QrCode.resume(); } catch (e) {}
    }
  };

  window.stepQrQty = function(delta) {
    const input = document.getElementById('qr-input-quantity');
    if (!input) return;
    let val = parseFloat(input.value) || 0;
    val = Math.max(1, val + delta);
    input.value = val;
  };

  window.setQrQty = function(val) {
    const input = document.getElementById('qr-input-quantity');
    if (input) input.value = val;
  };

  window.searchManualSku = function() {
    const input = document.getElementById('qr-manual-code');
    if (input && input.value.trim()) {
      lookupItem(input.value.trim());
    }
  };

  window.submitQrStockIn = async function() {
    if (!currentScannedItem) return;

    const qtyInput = document.getElementById('qr-input-quantity');
    const qty = parseFloat(qtyInput ? qtyInput.value : 10) || 0;
    if (qty <= 0) {
      alert('Vui lòng nhập số lượng lớn hơn 0');
      return;
    }

    const submitBtn = document.getElementById('qr-btn-submit-stock');
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Đang lưu...';
    }

    try {
      const res = await fetch('/inventory/api/qr-stock-in/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
          code: currentScannedItem.code,
          item_type: currentScannedItem.item_type,
          id: currentScannedItem.id,
          quantity: qty
        })
      });

      const result = await res.json();
      if (result.success) {
        playBeep(1046, 0.1, 'sine');
        setTimeout(() => playBeep(1318, 0.18, 'sine'), 100);

        if (typeof showToast === 'function') {
          showToast(result.message, 'success');
        } else {
          alert(result.message);
        }

        // Update card with new stock
        document.getElementById('qr-item-stock').textContent = result.new_stock;

        // Button to scan next
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = '✓ Đã Nhập! Bấm để Quét Tiếp';
          submitBtn.onclick = function() {
            submitBtn.innerHTML = '✓ Xác Nhận Nhập Kho';
            submitBtn.onclick = window.submitQrStockIn;
            window.resumeQrScanning();
          };
        }
      } else {
        alert(result.message || 'Lỗi khi nhập kho');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = '✓ Xác Nhận Nhập Kho';
        }
      }
    } catch (err) {
      console.error('Submit stock error:', err);
      alert('Không thể kết nối máy chủ để nhập kho.');
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = '✓ Xác Nhận Nhập Kho';
      }
    }
  };

})();
