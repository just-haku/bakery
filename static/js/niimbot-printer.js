/**
 * Niimbot Bluetooth Thermal Label Printer Driver & Bakery Label Generator
 * Reverse-engineered from Niimbot Official App & Protocol Specifications
 * 
 * Protocol Details:
 * - Framing: [0x55, 0x55, <type>, <len>, <data...>, <xor_checksum>, 0xAA, 0xAA]
 * - BLE Service UUID: e7810a71-73ae-499d-8c15-faa9aef0c3f2
 * - BLE Characteristic: bef8d6c9-9c21-4c9e-b632-bd58c1009f9f
 * - SPP UUID: 00001101-0000-1000-8000-00805f9b34fb
 * - Models supported: Niimbot B21, D11, D110, B1, B3S, B24, JC series
 * - Resolution: 203 DPI (8 dots/mm)
 */

const NiimbotProtocol = {
  SERVICE_UUID: 'e7810a71-73ae-499d-8c15-faa9aef0c3f2',
  CHAR_UUID: 'bef8d6c9-9c21-4c9e-b632-bd58c1009f9f',
  SPP_UUID: '00001101-0000-1000-8000-00805f9b34fb',

  // Official Niimbot Protocol Command IDs (Reverse-Engineered & Wireshark-Verified)
  CMD_START_PRINT: 0x01,     // Start print job
  CMD_START_PAGE: 0x03,      // Start page print
  CMD_SET_DIMENSION: 0x13,   // Set page height & width (big-endian)
  CMD_SET_QUANTITY: 0x15,    // Set quantity / copy count
  CMD_ALLOW_PRINT_CLEAR: 0x20,// Arm/clear thermal printhead latch
  CMD_SET_DENSITY: 0x21,     // Density 1-5 (2=Medium, 3=Dark)
  CMD_SET_LABEL_TYPE: 0x23,  // 1=Gap (giấy có khe hở), 2=Black mark, 3=Continuous
  CMD_BITMAP_ROW: 0x85,      // Bitmap line transmission
  CMD_HEARTBEAT: 0xDC,       // Heartbeat / status query
  CMD_END_PAGE: 0xE3,        // Page printing end / triggers motor feed & thermal burn
  CMD_END_PRINT: 0xF3,       // Print job finish
  CMD_PAPER_FEED: 0xD4,
  CMD_QUERY_STATUS: 0x0E,

  // Build Packet with 0x55 0x55 ... checksum ... 0xAA 0xAA
  buildPacket(type, payload = []) {
    const len = payload.length;
    let checksum = type ^ len;
    for (let i = 0; i < len; i++) {
      checksum ^= payload[i];
    }
    checksum = checksum & 0xFF;

    const packet = new Uint8Array(2 + 1 + 1 + len + 1 + 2);
    packet[0] = 0x55;
    packet[1] = 0x55;
    packet[2] = type;
    packet[3] = len;
    for (let i = 0; i < len; i++) {
      packet[4 + i] = payload[i];
    }
    packet[4 + len] = checksum;
    packet[4 + len + 1] = 0xAA;
    packet[4 + len + 2] = 0xAA;
    return packet;
  }
};

/**
 * Standard Niimbot Label Presets (203 DPI = 8 dots/mm)
 */
const NIIMBOT_LABEL_PRESETS = [
  { id: '50x30', name: '50 × 30 mm (Chuẩn Tiệm Bánh - Niimbot B21/B1)', widthMm: 50, heightMm: 30, widthPx: 384, heightPx: 240, isDefault: true },
  { id: '40x30', name: '40 × 30 mm (Tem Nhãn Trung Bình)', widthMm: 40, heightMm: 30, widthPx: 320, heightPx: 240 },
  { id: '50x25', name: '50 × 25 mm (Tem Bánh Dẹp)', widthMm: 50, heightMm: 25, widthPx: 384, heightPx: 200 },
  { id: '40x20', name: '40 × 20 mm (Tem Nhỏ Dán Hộp)', widthMm: 40, heightMm: 20, widthPx: 320, heightPx: 160 },
  { id: '30x20', name: '30 × 20 mm (Tem Mini Macaron / Cupcake)', widthMm: 30, heightMm: 20, widthPx: 240, heightPx: 160 },
  { id: 'custom', name: '⚙️ Tùy Chỉnh Kích Thước (Ngang × Dọc mm)...', widthMm: 50, heightMm: 30, widthPx: 384, heightPx: 240 }
];

class NiimbotPrinter {
  constructor() {
    this.device = null;
    this.server = null;
    this.characteristic = null;
    this.isConnected = false;
    this.deviceName = '';
    this.statusListeners = [];
    this.rxBuffer = [];
    this.pendingResolvers = [];

    // Global listener for native Android bridge
    window.onNiimbotPacketReceived = (hex) => {
      this.handleIncomingHex(hex);
    };
  }

  onStatusChange(fn) {
    this.statusListeners.push(fn);
  }

  notifyStatus(status, detail = '') {
    this.statusListeners.forEach(fn => fn(status, detail));
  }

  handleIncomingHex(hex) {
    if (!hex) return;
    for (let i = 0; i < hex.length; i += 2) {
      this.rxBuffer.push(parseInt(hex.substr(i, 2), 16));
    }
    this.processRxBuffer();
  }

  processRxBuffer() {
    while (this.rxBuffer.length >= 7) {
      const hIdx = this.rxBuffer.findIndex((b, i) => b === 0x55 && this.rxBuffer[i + 1] === 0x55);
      if (hIdx === -1) {
        this.rxBuffer = [];
        break;
      }
      if (hIdx > 0) {
        this.rxBuffer.splice(0, hIdx);
      }
      if (this.rxBuffer.length < 4) break;

      const cmd = this.rxBuffer[2];
      const len = this.rxBuffer[3];
      const packetLen = 2 + 1 + 1 + len + 1 + 2;
      if (this.rxBuffer.length < packetLen) break;

      const raw = this.rxBuffer.slice(0, packetLen);
      this.rxBuffer.splice(0, packetLen);

      if (raw[packetLen - 2] === 0xAA && raw[packetLen - 1] === 0xAA) {
        const data = raw.slice(4, 4 + len);
        const checksum = raw[4 + len];
        let calcXor = cmd ^ len;
        for (let i = 0; i < len; i++) calcXor ^= data[i];
        if ((calcXor & 0xFF) === checksum) {
          this.onPacket(cmd, data);
        }
      }
    }
  }

  onPacket(cmd, data) {
    const hexCmd = '0x' + cmd.toString(16).padStart(2, '0').toUpperCase();
    console.log(`[Niimbot RX] CMD=${hexCmd} data=[${Array.from(data).map(d => '0x' + d.toString(16)).join(',')}]`);
    if (window.AndroidNiimbot && typeof window.AndroidNiimbot.log === 'function') {
      window.AndroidNiimbot.log('RX', `CMD=${hexCmd} len=${data.length}`);
    }

    for (let i = this.pendingResolvers.length - 1; i >= 0; i--) {
      const p = this.pendingResolvers[i];
      if (p.filter(cmd, data)) {
        this.pendingResolvers.splice(i, 1);
        p.resolve({ cmd, data });
      }
    }
  }

  waitForPacket(filterFn, timeoutMs = 800) {
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        const idx = this.pendingResolvers.findIndex(p => p.timer === timer);
        if (idx !== -1) this.pendingResolvers.splice(idx, 1);
        resolve(null);
      }, timeoutMs);

      this.pendingResolvers.push({
        filter: filterFn,
        resolve: (pkt) => {
          clearTimeout(timer);
          resolve(pkt);
        },
        timer
      });
    });
  }

  async sendPacketWithAck(type, payload = [], expectedRespCmd = null, timeoutMs = 800) {
    const waitPromise = expectedRespCmd ? this.waitForPacket((cmd) => {
      return cmd === expectedRespCmd || cmd === 0xDB;
    }, timeoutMs) : null;

    await this.sendPacket(type, payload);

    if (waitPromise) {
      const resp = await waitPromise;
      if (resp) {
        if (resp.cmd === 0xDB) {
          const errCode = resp.data && resp.data.length > 0 ? resp.data[0] : 0;
          const errMap = {
            1: 'Hết giấy in tem (Out of paper)',
            2: 'Nắp máy in đang mở (Cover open)',
            3: 'Pin quá yếu (Low battery)',
            4: 'Đầu in quá nhiệt (Overheat)',
            5: 'Chưa căn chỉnh / không nhận giấy (Paper not detected)',
            6: 'Sai tham số / Dữ liệu khổ tem không hợp lệ (Data error)'
          };
          const msg = errMap[errCode] || `Mã lỗi máy in: ${errCode}`;
          throw new Error(`Máy in từ chối lệnh (0xDB): ${msg}`);
        }
        return resp;
      }
    }
    return null;
  }

  // Connect via Web Bluetooth API or Native Android Bridge
  async connectBLE() {
    if (window.AndroidNiimbot && typeof window.AndroidNiimbot.connect === 'function') {
      let ok = false;
      try {
        ok = window.AndroidNiimbot.connect() === true;
        if (ok && typeof window.AndroidNiimbot.isConnected === 'function') {
          ok = window.AndroidNiimbot.isConnected() === true;
        }
      } catch (err) {
        console.error('Native Niimbot connect error:', err);
        ok = false;
      }
      if (!ok) {
        this.isConnected = false;
        const msg = 'Không kết nối được máy in. Hãy bật máy in Niimbot, ghép đôi Bluetooth trong Cài đặt và cấp quyền Bluetooth cho app.';
        this.notifyStatus('error', msg);
        throw new Error(msg);
      }
      let name = 'Niimbot';
      try { name = window.AndroidNiimbot.getDeviceName() || name; } catch (e) {}
      this.isConnected = true;
      this.deviceName = name;
      this.notifyStatus('connected', this.deviceName);
      return true;
    }

    if (!navigator.bluetooth) {
      throw new Error('Trình duyệt hiện tại chưa hỗ trợ Web Bluetooth. Hãy dùng Google Chrome trên Android hoặc Bluefy trên iOS.');
    }

    try {
      this.notifyStatus('scanning', 'Đang quét thiết bị máy in Niimbot...');
      const device = await navigator.bluetooth.requestDevice({
        filters: [
          { namePrefix: 'B21' },
          { namePrefix: 'D11' },
          { namePrefix: 'D110' },
          { namePrefix: 'B1' },
          { namePrefix: 'B3S' },
          { namePrefix: 'JC' },
          { namePrefix: 'Niimbot' }
        ],
        optionalServices: [NiimbotProtocol.SERVICE_UUID, 'generic_access']
      });

      this.device = device;
      this.deviceName = device.name || 'Niimbot Printer';
      device.addEventListener('gattserverdisconnected', () => {
        this.isConnected = false;
        this.notifyStatus('disconnected', this.deviceName);
      });

      this.notifyStatus('connecting', `Đang kết nối tới ${this.deviceName}...`);
      const server = await device.gatt.connect();
      this.server = server;

      const service = await server.getPrimaryService(NiimbotProtocol.SERVICE_UUID);
      const characteristic = await service.getCharacteristic(NiimbotProtocol.CHAR_UUID);
      this.characteristic = characteristic;

      // Enable notifications to receive responses if supported
      try {
        await characteristic.startNotifications();
        characteristic.addEventListener('characteristicvaluechanged', (evt) => {
          const val = evt.target.value;
          const bytes = [];
          for (let i = 0; i < val.byteLength; i++) bytes.push(val.getUint8(i));
          let hex = bytes.map(b => b.toString(16).padStart(2, '0')).join('');
          this.handleIncomingHex(hex);
        });
      } catch (e) {
        console.warn('BLE notifications not supported or failed', e);
      }

      this.isConnected = true;
      this.notifyStatus('connected', this.deviceName);
      return true;
    } catch (err) {
      this.isConnected = false;
      this.notifyStatus('error', err.message);
      throw err;
    }
  }

  async sendPacket(type, payload = []) {
    const packet = NiimbotProtocol.buildPacket(type, payload);
    if (window.AndroidNiimbot) {
      if (typeof window.AndroidNiimbot.sendRawHex === 'function') {
        let hex = '';
        for (let i = 0; i < packet.length; i++) {
          hex += packet[i].toString(16).padStart(2, '0');
        }
        window.AndroidNiimbot.sendRawHex(hex);
        return;
      }
      if (typeof window.AndroidNiimbot.sendRaw === 'function') {
        window.AndroidNiimbot.sendRaw(Array.from(packet));
        return;
      }
    }

    if (!this.characteristic) throw new Error('Chưa kết nối máy in Niimbot qua Bluetooth');

    const CHUNK_SIZE = 64;
    for (let i = 0; i < packet.length; i += CHUNK_SIZE) {
      const chunk = packet.slice(i, i + CHUNK_SIZE);
      await this.characteristic.writeValueWithoutResponse(chunk);
      await this.sleep(10);
    }
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Feed / Calibrate label position (Kéo giấy căn lề)
   */
  async feedPaper() {
    if (!this.isConnected) await this.connectBLE();
    this.notifyStatus('printing', 'Đang gửi lệnh kéo giấy...');
    // Send Paper Feed 0xD4
    await this.sendPacket(NiimbotProtocol.CMD_PAPER_FEED, [0x01]);
    await this.sleep(400);
    this.notifyStatus('completed', 'Đã kéo giấy');
  }

  /**
   * Test Print a small label to verify hardware motor & thermal head
   */
  async testPrint(density = 3) {
    if (!this.isConnected) await this.connectBLE();
    const canvas = document.createElement('canvas');
    canvas.width = 384;
    canvas.height = 240;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, 384, 240);

    // 1. Heavy solid black band (Rows 10-50, 40px tall) - unquestionable thermal burn proof
    ctx.fillStyle = '#000000';
    ctx.fillRect(16, 10, 352, 40);

    // Inverted text inside solid black band
    ctx.fillStyle = '#FFFFFF';
    ctx.font = 'bold 20px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('🥖 ARTISAN BAKERY TEST', 192, 37);

    // 2. Bold black text in middle
    ctx.fillStyle = '#000000';
    ctx.font = 'bold 18px sans-serif';
    ctx.fillText('MÁY IN NIIMBOT B21S HOẠT ĐỘNG', 192, 82);

    ctx.font = 'bold 13px monospace';
    ctx.fillText('Khổ tem: 50 × 30 mm (203 DPI)', 192, 110);

    // 3. Test alternating barcode lines
    for (let i = 0; i < 32; i++) {
      ctx.fillRect(32 + i * 10, 126, (i % 2 === 0 ? 5 : 3), 34);
    }

    const now = new Date();
    ctx.font = '12px sans-serif';
    ctx.fillText(`Thời gian in: ${now.toLocaleTimeString('vi-VN')} - Độ đậm: ${density}`, 192, 185);

    // 4. Solid black bar at bottom
    ctx.fillRect(16, 204, 352, 24);

    await this.printCanvas(canvas, 1, density);
  }

  /**
   * Convert an HTML5 Canvas to 1-bit monochrome bitmap packet rows
   * Width is divisible by 8 (e.g. 384px for 48-50mm / 203 DPI)
   */
  async printCanvas(canvas, copies = 1, density = 3) {
    if (!this.isConnected) {
      throw new Error('Máy in chưa kết nối. Vui lòng bật Bluetooth và kết nối máy in trước.');
    }

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const imgData = ctx.getImageData(0, 0, width, height);
    const data = imgData.data;

    const rowBytes = Math.ceil(width / 8);

    this.notifyStatus('printing', `Đang chuẩn bị in ${copies} tem (${width}×${height}px)...`);

    // 1. Set Print Density (1 to 5, standard default for B21S is 3)
    const densVal = Math.min(5, Math.max(1, density));
    await this.sendPacketWithAck(NiimbotProtocol.CMD_SET_DENSITY, [densVal], 0x31, 500);
    await this.sleep(40);

    // 2. Set Label Type (0x01: gap label - giấy có khe hở)
    await this.sendPacketWithAck(NiimbotProtocol.CMD_SET_LABEL_TYPE, [0x01], 0x33, 500);
    await this.sleep(40);

    // 3. Start Print Session (Official niimbluelib / niimprint sends 1 byte [0x01], ACK 0x02)
    await this.sendPacketWithAck(NiimbotProtocol.CMD_START_PRINT, [0x01], 0x02, 500);
    await this.sleep(40);

    // Pre-calculate monochrome bitmap rows and total black pixel count per row
    const bitmapRows = [];
    const rowTotalBlack = [];

    for (let y = 0; y < height; y++) {
      const row = new Uint8Array(rowBytes);
      let totalBlack = 0;

      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * 4;
        const r = data[idx];
        const g = data[idx + 1];
        const b = data[idx + 2];
        const a = data[idx + 3];

        const luminance = 0.299 * r + 0.587 * g + 0.114 * b;
        const isBlack = (a > 128) && (luminance < 165);

        if (isBlack) {
          const byteIdx = Math.floor(x / 8);
          const bitIdx = 7 - (x % 8);
          row[byteIdx] |= (1 << bitIdx);
          totalBlack++;
        }
      }
      bitmapRows.push(row);
      rowTotalBlack.push(totalBlack);
    }

    // Print each copy
    for (let c = 0; c < copies; c++) {
      this.notifyStatus('printing', `Đang in tem ${c + 1}/${copies}...`);

      // 4. Start Page Print (0x03 -> ACK 0x04)
      await this.sendPacketWithAck(NiimbotProtocol.CMD_START_PAGE, [0x01], 0x04, 500);
      await this.sleep(40);

      // 5. Set Dimension (Official B21/B21S sends 6 bytes: [heightHi, heightLo, widthHi, widthLo, copiesHi, copiesLo])
      const dimPayload = [
        (height >> 8) & 0xFF,
        height & 0xFF,
        (width >> 8) & 0xFF,
        width & 0xFF,
        0x00,
        0x01
      ];
      await this.sendPacketWithAck(NiimbotProtocol.CMD_SET_DIMENSION, dimPayload, 0x14, 500);
      await this.sleep(40);

      // 6. Send Bitmap Rows (Command 0x85)
      // Header for B21/B21S (countsMode: "total"):
      // [rowHi, rowLo, 0x00, totalBlackLo, totalBlackHi, repeat=1] followed by rowBytes
      for (let y = 0; y < height; y++) {
        const row = bitmapRows[y];
        const total = rowTotalBlack[y];
        const payload = new Uint8Array(6 + rowBytes);
        payload[0] = (y >> 8) & 0xFF;
        payload[1] = y & 0xFF;
        payload[2] = 0x00;                          // Mode 0: parts[0] is 0x00 for B21 total counts
        payload[3] = total & 0xFF;                  // total black pixels (low byte)
        payload[4] = (total >> 8) & 0xFF;           // total black pixels (high byte)
        payload[5] = 0x01;                          // repeat = 1
        payload.set(row, 6);

        await this.sendPacket(NiimbotProtocol.CMD_BITMAP_ROW, payload);
        // Inter-packet throttling: 8ms delay between packets prevents microcontroller UART buffer overflow
        await this.sleep(8);
      }

      this.notifyStatus('printing', `Đang hoàn tất in và kéo giấy tem ${c + 1}...`);

      // 7. End Page Print (Triggers printer motor feed & thermal burn)
      await this.sendPacketWithAck(NiimbotProtocol.CMD_END_PAGE, [0x01], 0xE4, 1500);

      // Wait for mechanical motor feed before proceeding to next page
      await this.sleep(1000);
    }

    // 8. End Print Session
    await this.sendPacketWithAck(NiimbotProtocol.CMD_END_PRINT, [0x01], 0xF4, 600);
    await this.sleep(200);

    this.notifyStatus('completed', 'In hoàn tất thành công!');
  }
}

// Global instance
window.niimbotPrinter = new NiimbotPrinter();

/**
 * Dynamic Bakery Label Generator
 * Adapts to any label dimensions (50x30, 40x30, 50x25, custom mm)
 * Generates crisp 203 DPI typography, NSX/HSD, price, and barcode
 */
const BakeryLabelGenerator = {
  createLabelCanvas(productData, dimensions = { widthMm: 50, heightMm: 30 }) {
    const widthMm = Math.max(20, Math.min(60, Number(dimensions.widthMm) || 50));
    const heightMm = Math.max(15, Math.min(100, Number(dimensions.heightMm) || 30));

    // 203 DPI = 8 dots/mm. Width must be a multiple of 8 dots for byte-alignment.
    // 50mm -> 384 dots (48mm printable width on Niimbot B21)
    let widthPx = Math.floor((widthMm * 8) / 8) * 8;
    if (widthMm >= 48) widthPx = 384; // Standard Niimbot 50mm head width
    const heightPx = Math.round(heightMm * 8);

    const canvas = document.createElement('canvas');
    canvas.width = widthPx;
    canvas.height = heightPx;
    const ctx = canvas.getContext('2d');

    // Clean white background
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, widthPx, heightPx);

    ctx.fillStyle = '#000000';
    ctx.textBaseline = 'top';

    // Scale factor relative to 50x30mm (384x240)
    const scaleX = widthPx / 384;
    const scaleY = heightPx / 240;
    const scale = Math.min(scaleX, scaleY);

    const padX = Math.round(14 * scaleX);
    const topPad = Math.round(10 * scaleY);

    // 1. Top Header: Brand Name & Hotline
    const headerFont = Math.max(11, Math.round(15 * scale));
    ctx.font = `bold ${headerFont}px "Plus Jakarta Sans", sans-serif`;
    ctx.fillText('🥖 ARTISAN BAKERY', padX, topPad);

    if (widthPx >= 300) {
      const hotlineFont = Math.max(9, Math.round(11 * scale));
      ctx.font = `bold ${hotlineFont}px monospace`;
      ctx.textAlign = 'right';
      ctx.fillText('HOTLINE: 1900-BAKERY', widthPx - padX, topPad + 2);
      ctx.textAlign = 'left';
    }

    // Separator line
    const sepY = topPad + headerFont + 6;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padX, sepY);
    ctx.lineTo(widthPx - padX, sepY);
    ctx.stroke();

    const sku = productData.sku || productData.sku_code || 'SKU-BAKE-001';

    // 2D QR Code (right column) - encodes SKU for scanning at goods receipt
    const showQR = heightPx >= 180 && widthPx >= 300 && typeof window.qrcode === 'function';
    const qrSize = showQR ? Math.round(88 * scale) : 0;
    const qrX = widthPx - padX - qrSize;
    const qrY = sepY + 6;
    if (showQR) {
      try {
        const qr = window.qrcode(0, 'M');
        qr.addData(String(sku));
        qr.make();
        const n = qr.getModuleCount();
        const cell = Math.floor(qrSize / (n + 2)); // +2 = quiet zone
        const qrReal = cell * (n + 2);
        const ox = widthPx - padX - qrReal;
        ctx.fillStyle = '#FFFFFF';
        ctx.fillRect(ox, qrY, qrReal, qrReal);
        ctx.fillStyle = '#000000';
        for (let r = 0; r < n; r++) {
          for (let c = 0; c < n; c++) {
            if (qr.isDark(r, c)) ctx.fillRect(ox + (c + 1) * cell, qrY + (r + 1) * cell, cell, cell);
          }
        }
        ctx.font = `bold ${Math.max(8, Math.round(9 * scale))}px monospace`;
        ctx.textAlign = 'center';
        ctx.fillText('QUÉT QR', ox + qrReal / 2, qrY + qrReal + 1);
        ctx.textAlign = 'left';
      } catch (e) { console.warn('QR render failed', e); }
    }

    // Left column width (text area)
    const textW = (showQR ? qrX - 8 : widthPx - padX) - padX;

    // Word wrap helper (measures real pixel width)
    const wrapText = (text, maxW) => {
      const words = String(text).split(/\s+/);
      const lines = [];
      let cur = '';
      for (const w of words) {
        const test = cur ? cur + ' ' + w : w;
        if (ctx.measureText(test).width <= maxW || !cur) cur = test;
        else { lines.push(cur); cur = w; }
      }
      if (cur) lines.push(cur);
      return lines;
    };

    // 3. Product Name - FULL name, auto-fit: shrink font until it fits in <= 2 lines
    const nameY = sepY + 6;
    const productName = productData.name || 'Bánh Mì Nghệ Nhân';
    let nameFont = Math.max(13, Math.round(20 * scale));
    const minNameFont = Math.max(10, Math.round(13 * scale));
    let nameLines;
    while (true) {
      ctx.font = `bold ${nameFont}px "Plus Jakarta Sans", sans-serif`;
      nameLines = wrapText(productName, textW);
      const widest = Math.max(...nameLines.map(l => ctx.measureText(l).width));
      if ((nameLines.length <= 2 && widest <= textW) || nameFont <= minNameFont) break;
      nameFont -= 1;
    }
    nameLines = nameLines.slice(0, 3);
    nameLines.forEach((line, i) => ctx.fillText(line, padX, nameY + i * (nameFont + 2)));
    const nameBottom = nameY + nameLines.length * (nameFont + 2);

    // 4. Price
    const priceY = nameBottom + 2;
    const priceFont = Math.max(15, Math.round(22 * scale));
    ctx.font = `900 ${priceFont}px "Plus Jakarta Sans", sans-serif`;
    const priceText = productData.price ? `${Number(productData.price).toLocaleString('vi-VN')}₫` : '35.000₫';
    ctx.fillText(priceText, padX, priceY);

    // 5. Dates, shelf life, SKU
    const infoY = priceY + priceFont + 4;
    const infoFont = Math.max(9, Math.round(12 * scale));
    ctx.font = `600 ${infoFont}px "Plus Jakarta Sans", sans-serif`;

    const now = new Date();
    const nsx = `${String(now.getDate()).padStart(2, '0')}/${String(now.getMonth() + 1).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    ctx.fillText(`NSX: ${nsx}`, padX, infoY);

    const shelfLife = productData.shelf_life_hours ? `${productData.shelf_life_hours}h` : '24h';
    ctx.fillText(`HSD: ${shelfLife} sau khi nướng`, padX, infoY + infoFont + 2);

    const skuY = infoY + (infoFont + 2) * 2;
    ctx.font = `bold ${Math.max(8, Math.round(11 * scale))}px monospace`;
    ctx.fillText(`MÃ: ${sku}`, padX, skuY);

    // 6. 1D Barcode - Code 128 (type B), real encoding, module width 2px (scanner friendly)
    const barcodeH = Math.max(24, Math.round(40 * scaleY));
    const barcodeY = heightPx - barcodeH - Math.round(16 * scaleY);
    const bars = BakeryLabelGenerator.code128Pattern(String(sku));
    const totalModules = bars.reduce((a, b) => a + b, 0);
    const maxBarW = widthPx - padX * 2;
    let moduleW = Math.max(1, Math.min(3, Math.floor(maxBarW / totalModules)));
    const barPx = totalModules * moduleW;
    let bx = Math.round((widthPx - barPx) / 2);
    ctx.fillStyle = '#000000';
    bars.forEach((w, i) => {
      if (i % 2 === 0) ctx.fillRect(bx, barcodeY, w * moduleW, barcodeH);
      bx += w * moduleW;
    });

    // SKU text under barcode
    if (heightPx >= 180) {
      ctx.font = `bold ${Math.max(8, Math.round(10 * scale))}px monospace`;
      ctx.textAlign = 'center';
      ctx.fillText(sku, widthPx / 2, barcodeY + barcodeH + 2);
      ctx.textAlign = 'left';
    }

    return canvas;
  }
,

  // Real Code 128-B encoder. Returns alternating bar/space module widths (starts with bar).
  code128Pattern(text) {
    const P = ['212222','222122','222221','121223','121322','131222','122213','122312','132212','221213','221312','231212','112232','122132','122231','113222','123122','123221','223211','221132','221231','213212','223112','312131','311222','321122','321221','312212','322112','322211','212123','212321','232121','111323','131123','131321','112313','132113','132311','211313','231113','231311','112133','112331','132131','113123','113321','133121','313121','211331','231131','213113','213311','213131','311123','311321','331121','312113','312311','332111','314111','221411','431111','111224','111422','121124','121421','141122','141221','112214','112412','122114','122411','142112','142211','241211','221114','413111','241112','134111','111242','121142','121241','114212','124112','124211','411212','421112','421211','212141','214121','412121','111143','111341','131141','114113','114311','411113','411311','113141','114131','311141','411131','211412','211214','211232','2331112'];
    const codes = [104]; // Start B
    for (const ch of text) {
      const v = ch.charCodeAt(0) - 32;
      codes.push(v >= 0 && v < 95 ? v : 0);
    }
    let sum = codes[0];
    for (let i = 1; i < codes.length; i++) sum += codes[i] * i;
    codes.push(sum % 103);
    codes.push(106); // Stop
    const out = [];
    codes.forEach(c => P[c].split('').forEach(d => out.push(parseInt(d, 10))));
    return out;
  }
};

window.BakeryLabelGenerator = BakeryLabelGenerator;

/**
 * Interactive Niimbot Print Modal with Dimension Selector
 */
function openNiimbotPrintModal(productData) {
  let modal = document.getElementById('niimbot-printer-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'niimbot-printer-modal';
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/60 backdrop-blur-xs overflow-y-auto';
    modal.innerHTML = `
      <div class="bg-white rounded-3xl max-w-md w-full p-5 sm:p-6 shadow-2xl border border-amber-200 space-y-4 my-auto">
        <!-- Header -->
        <div class="flex items-center justify-between pb-3 border-b border-amber-100">
          <div class="flex items-center gap-2.5">
            <div class="w-10 h-10 rounded-2xl bg-amber-100 text-amber-900 flex items-center justify-center text-xl shadow-xs">
              🏷️
            </div>
            <div>
              <h3 class="font-black text-base text-amber-950">In Tem Nhiệt Niimbot</h3>
              <p class="text-[11px] text-amber-800 font-semibold flex items-center gap-1" id="niimbot-device-status">
                <span class="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
                <span>Chưa kết nối máy in Bluetooth</span>
              </p>
            </div>
          </div>
          <button onclick="document.getElementById('niimbot-printer-modal').classList.add('hidden')" class="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-500 hover:text-gray-800 flex items-center justify-center text-lg font-bold transition">&times;</button>
        </div>

        <!-- Dimension & Paper Selector -->
        <div class="bg-amber-50/70 rounded-2xl p-3.5 border border-amber-200/80 space-y-2.5">
          <div class="flex items-center justify-between">
            <label for="niimbot-size-select" class="text-xs font-black text-amber-950 flex items-center gap-1.5">
              <span>📐</span>
              <span>Kích Thước Khổ Tem:</span>
            </label>
            <span class="text-[10px] text-emerald-800 font-bold bg-emerald-100 px-2 py-0.5 rounded-md border border-emerald-300">
              ✓ Chuẩn Niimbot 203 DPI
            </span>
          </div>

          <select id="niimbot-size-select" onchange="handleNiimbotSizeChange()" 
                  class="w-full text-xs font-bold text-gray-800 bg-white border border-amber-300 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-amber-500">
            ${NIIMBOT_LABEL_PRESETS.map(p => `
              <option value="${p.id}" ${p.isDefault ? 'selected' : ''}>${p.name}</option>
            `).join('')}
          </select>

          <!-- Custom Dimensions Input (Hidden by default) -->
          <div id="niimbot-custom-size-row" class="hidden grid grid-cols-2 gap-2 pt-1">
            <div>
              <label class="text-[10px] font-bold text-gray-600 block mb-0.5">Chiều Ngang (mm):</label>
              <input type="number" id="custom-width-mm" value="50" min="20" max="60" onchange="updateCustomDimensions()" 
                     class="w-full px-2.5 py-1.5 text-xs border border-gray-300 rounded-lg font-bold text-center">
            </div>
            <div>
              <label class="text-[10px] font-bold text-gray-600 block mb-0.5">Chiều Dọc (mm):</label>
              <input type="number" id="custom-height-mm" value="30" min="15" max="100" onchange="updateCustomDimensions()" 
                     class="w-full px-2.5 py-1.5 text-xs border border-gray-300 rounded-lg font-bold text-center">
            </div>
          </div>

          <!-- Specs Info Badge -->
          <div class="flex items-center justify-between text-[11px] text-amber-900 bg-white/80 p-2 rounded-xl border border-amber-200">
            <span>Thông số in: <b id="niimbot-current-size-label" class="font-mono">50 × 30 mm</b></span>
            <span class="font-mono text-gray-500" id="niimbot-current-pixel-label">384 × 240 px</span>
          </div>
        </div>

        <!-- Label Live Preview -->
        <div class="p-3 bg-gray-50 rounded-2xl border border-gray-200 flex flex-col items-center">
          <div class="flex items-center justify-between w-full mb-2 px-1">
            <span class="text-[10px] text-gray-500 font-bold uppercase tracking-wider">Bản Xem Trước Thực Tế (Live Preview)</span>
            <span class="text-[10px] font-bold text-amber-700">Tỷ lệ 1:1 chuẩn giấy</span>
          </div>
          <div id="niimbot-preview-box" class="shadow-md rounded-xl overflow-hidden border border-gray-300 bg-white max-w-full flex items-center justify-center p-1"></div>
        </div>

        <!-- Print Options (Copies & Density) -->
        <div class="grid grid-cols-2 gap-3 text-xs">
          <!-- Copies -->
          <div class="bg-gray-50 p-2.5 rounded-xl border border-gray-200 flex items-center justify-between">
            <span class="font-bold text-gray-700">Số bản in:</span>
            <div class="flex items-center gap-1.5">
              <button type="button" onclick="changePrintCopies(-1)" class="w-6 h-6 rounded-lg bg-white border border-gray-300 hover:bg-gray-100 font-black text-gray-700 flex items-center justify-center">-</button>
              <input type="number" id="niimbot-copies-val" value="1" min="1" max="100" class="w-10 text-center font-bold text-amber-950 bg-transparent border-0 focus:outline-none">
              <button type="button" onclick="changePrintCopies(1)" class="w-6 h-6 rounded-lg bg-white border border-gray-300 hover:bg-gray-100 font-black text-gray-700 flex items-center justify-center">+</button>
            </div>
          </div>

          <!-- Density -->
          <div class="bg-gray-50 p-2.5 rounded-xl border border-gray-200 flex items-center justify-between">
            <span class="font-bold text-gray-700">Độ đậm nhiệt:</span>
            <select id="niimbot-density-val" class="bg-white border border-gray-300 rounded-lg px-2 py-0.5 font-bold text-gray-800 focus:outline-none">
              <option value="1">1 (Nhẹ)</option>
              <option value="2">2 (Vừa)</option>
              <option value="3" selected>3 (Đậm nét - Chuẩn B21S)</option>
              <option value="4">4 (Rất đậm)</option>
              <option value="5">5 (Tối đa)</option>
            </select>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="space-y-2 pt-1">
          <div class="grid grid-cols-2 gap-2">
            <button id="niimbot-feed-btn" type="button" onclick="feedNiimbotPaper()" class="py-2.5 px-2 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-800 font-bold text-xs flex items-center justify-center gap-1.5 transition btn-tactile">
              <span>📄</span>
              <span>Căn / Kéo Giấy</span>
            </button>
            <button id="niimbot-test-btn" type="button" onclick="testNiimbotPrint()" class="py-2.5 px-2 rounded-xl bg-amber-100 hover:bg-amber-200 text-amber-900 font-bold text-xs flex items-center justify-center gap-1.5 transition btn-tactile">
              <span>⚡</span>
              <span>In Thử 1 Tem</span>
            </button>
          </div>

          <button id="niimbot-connect-btn" onclick="connectNiimbotDevice()" class="w-full py-2.5 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-950 border border-amber-300 font-bold text-xs flex items-center justify-center gap-2 transition btn-tactile">
            <span>📡</span>
            <span id="niimbot-connect-label">Tìm & Kết Nối Máy In Niimbot (Bluetooth)</span>
          </button>
          
          <button id="niimbot-print-action-btn" onclick="executeNiimbotPrint()" class="w-full py-3.5 rounded-2xl bg-gradient-to-r from-amber-600 to-amber-700 hover:from-amber-700 hover:to-amber-800 text-white font-black text-sm flex items-center justify-center gap-2 shadow-lg shadow-amber-600/30 transition btn-tactile">
            <span>🖨️</span>
            <span>Xác Nhận In Tem Niimbot</span>
          </button>

          <!-- Live diagnostic line -->
          <div class="bg-gray-50 rounded-xl px-2.5 py-1.5 border border-gray-200 flex items-center justify-between text-[10px] text-gray-500 font-mono">
            <span class="truncate" id="niimbot-diag-log">Trạng thái: Sẵn sàng</span>
            <span class="text-amber-800 font-bold shrink-0">B21S Driver v4.0 (Live)</span>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    window.niimbotPrinter.onStatusChange((status, detail) => {
      const statusEl = document.getElementById('niimbot-device-status');
      const connBtnLabel = document.getElementById('niimbot-connect-label');
      const diagLog = document.getElementById('niimbot-diag-log');

      if (diagLog) diagLog.textContent = detail ? `${detail}` : status;

      if (status === 'connected') {
        if (statusEl) statusEl.innerHTML = `<span class="text-emerald-700 font-bold">● Đã kết nối: ${detail}</span>`;
        if (connBtnLabel) connBtnLabel.textContent = `Đã kết nối: ${detail}`;
        if (typeof showToast === 'function') showToast(`Đã kết nối thành công máy in ${detail}`, 'success');
      } else if (status === 'disconnected') {
        if (statusEl) statusEl.innerHTML = `<span class="text-gray-500">Mất kết nối máy in</span>`;
        if (connBtnLabel) connBtnLabel.textContent = 'Tìm & Kết Nối Máy In Niimbot (Bluetooth)';
      } else if (status === 'error') {
        if (statusEl) statusEl.innerHTML = `<span class="text-rose-600">Lỗi: ${detail}</span>`;
        if (typeof showToast === 'function') showToast(detail, 'error');
      } else if (status === 'printing') {
        if (statusEl) statusEl.innerHTML = `<span class="text-amber-700 animate-pulse">${detail}</span>`;
      } else if (status === 'completed') {
        if (statusEl) statusEl.innerHTML = `<span class="text-emerald-700 font-bold">● Sẵn sàng in</span>`;
        if (typeof showToast === 'function') showToast('In tem nhãn Niimbot thành công!', 'success');
      }
    });
  }

  // Restore saved size if available
  const savedSize = localStorage.getItem('artisan_niimbot_label_size') || '50x30';
  const sizeSelect = document.getElementById('niimbot-size-select');
  if (sizeSelect) sizeSelect.value = savedSize;

  // Set copies if passed from caller
  if (productData.copies) {
    const copiesInput = document.getElementById('niimbot-copies-val');
    if (copiesInput) copiesInput.value = Math.max(1, Number(productData.copies));
  }

  window.currentPrintProduct = productData;
  renderCurrentLabelPreview();
  modal.classList.remove('hidden');
}

function handleNiimbotSizeChange() {
  const select = document.getElementById('niimbot-size-select');
  const customRow = document.getElementById('niimbot-custom-size-row');
  if (!select) return;

  const val = select.value;
  localStorage.setItem('artisan_niimbot_label_size', val);

  if (val === 'custom') {
    if (customRow) customRow.classList.remove('hidden');
  } else {
    if (customRow) customRow.classList.add('hidden');
  }

  renderCurrentLabelPreview();
}

function updateCustomDimensions() {
  renderCurrentLabelPreview();
}

function changePrintCopies(delta) {
  const input = document.getElementById('niimbot-copies-val');
  if (!input) return;
  let val = parseInt(input.value) || 1;
  val = Math.max(1, Math.min(100, val + delta));
  input.value = val;
}

function getActiveDimensions() {
  const select = document.getElementById('niimbot-size-select');
  const sizeId = select ? select.value : '50x30';

  if (sizeId === 'custom') {
    const w = Number(document.getElementById('custom-width-mm')?.value) || 50;
    const h = Number(document.getElementById('custom-height-mm')?.value) || 30;
    return { widthMm: w, heightMm: h };
  }

  const preset = NIIMBOT_LABEL_PRESETS.find(p => p.id === sizeId) || NIIMBOT_LABEL_PRESETS[0];
  return { widthMm: preset.widthMm, heightMm: preset.heightMm };
}

function renderCurrentLabelPreview() {
  const productData = window.currentPrintProduct;
  if (!productData) return;

  const dims = getActiveDimensions();
  const canvas = BakeryLabelGenerator.createLabelCanvas(productData, dims);
  window.currentLabelCanvas = canvas;

  canvas.style.maxWidth = '100%';
  canvas.style.height = 'auto';
  canvas.style.display = 'block';

  const previewBox = document.getElementById('niimbot-preview-box');
  if (previewBox) {
    previewBox.innerHTML = '';
    previewBox.appendChild(canvas);
  }

  const sizeLabel = document.getElementById('niimbot-current-size-label');
  const pixelLabel = document.getElementById('niimbot-current-pixel-label');
  if (sizeLabel) sizeLabel.textContent = `${dims.widthMm} × ${dims.heightMm} mm`;
  if (pixelLabel) pixelLabel.textContent = `${canvas.width} × ${canvas.height} px`;
}

async function connectNiimbotDevice() {
  try {
    await window.niimbotPrinter.connectBLE();
  } catch (err) {
    console.error('BLE connection failed:', err);
  }
}

async function executeNiimbotPrint() {
  if (!window.niimbotPrinter.isConnected) {
    try {
      await window.niimbotPrinter.connectBLE();
    } catch (e) {
      return;
    }
  }

  const copiesInput = document.getElementById('niimbot-copies-val');
  const copies = copiesInput ? parseInt(copiesInput.value) || 1 : 1;

  const densitySelect = document.getElementById('niimbot-density-val');
  const density = densitySelect ? parseInt(densitySelect.value) || 3 : 3;

  if (window.currentLabelCanvas) {
    try {
      await window.niimbotPrinter.printCanvas(window.currentLabelCanvas, copies, density);
    } catch (err) {
      if (typeof showToast === 'function') {
        showToast(err.message, 'error');
      } else {
        alert(err.message);
      }
    }
  }
}

async function feedNiimbotPaper() {
  try {
    const btn = document.getElementById('niimbot-feed-btn');
    if (btn) btn.disabled = true;
    await window.niimbotPrinter.feedPaper();
    if (typeof showToast === 'function') showToast('Đã gửi lệnh căn/kéo giấy', 'info');
  } catch (err) {
    if (typeof showToast === 'function') {
      showToast(err.message, 'error');
    } else {
      alert(err.message);
    }
  } finally {
    const btn = document.getElementById('niimbot-feed-btn');
    if (btn) btn.disabled = false;
  }
}

async function testNiimbotPrint() {
  try {
    const btn = document.getElementById('niimbot-test-btn');
    if (btn) btn.disabled = true;
    const densitySelect = document.getElementById('niimbot-density-val');
    const density = densitySelect ? parseInt(densitySelect.value) || 3 : 3;
    await window.niimbotPrinter.testPrint(density);
  } catch (err) {
    if (typeof showToast === 'function') {
      showToast(err.message, 'error');
    } else {
      alert(err.message);
    }
  } finally {
    const btn = document.getElementById('niimbot-test-btn');
    if (btn) btn.disabled = false;
  }
}

window.openNiimbotPrintModal = openNiimbotPrintModal;
window.connectNiimbotDevice = connectNiimbotDevice;
window.executeNiimbotPrint = executeNiimbotPrint;
window.feedNiimbotPaper = feedNiimbotPaper;
window.testNiimbotPrint = testNiimbotPrint;
window.handleNiimbotSizeChange = handleNiimbotSizeChange;
window.updateCustomDimensions = updateCustomDimensions;
window.changePrintCopies = changePrintCopies;

