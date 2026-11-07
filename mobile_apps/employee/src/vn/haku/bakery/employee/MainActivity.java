package vn.haku.bakery.employee;

import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;
import android.content.Context;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Build;
import android.webkit.CookieManager;

import java.io.InputStream;
import java.io.OutputStream;
import java.util.Set;
import java.util.UUID;
import android.util.Log;

public class MainActivity extends Activity {
    private WebView mWebView;
    private static final String DEFAULT_URL = "https://employee.example-trusted-bakery.org";
    private static final String FALLBACK_URL = "http://10.0.2.2:8009";
    private static final UUID SPP_UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");

    private BluetoothSocket mSocket;
    private OutputStream mOutputStream;
    private InputStream mInputStream;
    private Thread mRxThread;
    private volatile boolean mRxRunning = false;
    private String mPrinterName = "";
    private static final int REQ_PERMS = 1001;

    private boolean hasBtPermission() {
        if (Build.VERSION.SDK_INT < 31) return true;
        return checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
    }

    private void requestRuntimePermissions() {
        if (Build.VERSION.SDK_INT < 23) return;
        java.util.ArrayList<String> need = new java.util.ArrayList<>();
        if (Build.VERSION.SDK_INT >= 31) {
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) need.add(Manifest.permission.BLUETOOTH_CONNECT);
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) != PackageManager.PERMISSION_GRANTED) need.add(Manifest.permission.BLUETOOTH_SCAN);
        }
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) need.add(Manifest.permission.CAMERA);
        if (!need.isEmpty()) requestPermissions(need.toArray(new String[0]), REQ_PERMS);
    }

    private void startRxThread() {
        stopRxThread();
        mRxRunning = true;
        mRxThread = new Thread(() -> {
            byte[] buffer = new byte[512];
            while (mRxRunning && mSocket != null && mSocket.isConnected()) {
                try {
                    if (mInputStream == null) break;
                    int n = mInputStream.read(buffer);
                    if (n > 0) {
                        StringBuilder sb = new StringBuilder(n * 2);
                        for (int i = 0; i < n; i++) {
                            sb.append(String.format("%02x", buffer[i] & 0xFF));
                        }
                        final String hex = sb.toString();
                        Log.d("NiimbotBridge", "RX Raw Hex: " + hex);
                        runOnUiThread(() -> {
                            if (mWebView != null) {
                                mWebView.evaluateJavascript("if (typeof window.onNiimbotPacketReceived === 'function') window.onNiimbotPacketReceived('" + hex + "');", null);
                            }
                        });
                    } else if (n < 0) {
                        break;
                    }
                } catch (Exception e) {
                    Log.d("NiimbotBridge", "RxThread exception: " + e.getMessage());
                    break;
                }
            }
        });
        mRxThread.setDaemon(true);
        mRxThread.start();
    }

    private void stopRxThread() {
        mRxRunning = false;
        if (mRxThread != null) {
            try { mRxThread.interrupt(); } catch (Exception ignored) {}
            mRxThread = null;
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Keep Screen On for POS / Kitchen displays
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        setContentView(R.layout.activity_main);

        mWebView = findViewById(R.id.webview);
        mWebView.clearCache(true);
        WebSettings settings = mWebView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setUserAgentString(settings.getUserAgentString() + " ArtisanApp/1.0 (Employee-POS)");

        // Register Native Niimbot Bridge
        mWebView.addJavascriptInterface(new NiimbotBridge(), "AndroidNiimbot");

        CookieManager cm = CookieManager.getInstance();
        cm.setAcceptCookie(true);
        cm.setAcceptThirdPartyCookies(mWebView, true);

        mWebView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                // Let WebView handle http(s) itself so POST forms/cookies keep working
                return false;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                CookieManager.getInstance().flush();
            }
        });

        mWebView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                runOnUiThread(() -> {
                    if (Build.VERSION.SDK_INT >= 23 && checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
                        requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_PERMS);
                        request.deny();
                    } else {
                        request.grant(request.getResources());
                    }
                });
            }
        });

        requestRuntimePermissions();

        SharedPreferences prefs = getSharedPreferences("bakery_employee_prefs", Context.MODE_PRIVATE);
        String targetUrl = prefs.getString("server_url", DEFAULT_URL);
        mWebView.loadUrl(targetUrl);
    }

    public class NiimbotBridge {
        @JavascriptInterface
        public boolean connect() {
            if (!hasBtPermission()) {
                runOnUiThread(() -> {
                    Toast.makeText(MainActivity.this, "Cần cấp quyền Bluetooth cho app, sau đó bấm kết nối lại", Toast.LENGTH_LONG).show();
                    requestRuntimePermissions();
                });
                return false;
            }
            BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
            if (adapter == null || !adapter.isEnabled()) {
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "Vui lòng bật Bluetooth trên thiết bị", Toast.LENGTH_SHORT).show());
                return false;
            }

            try {
                Set<BluetoothDevice> bondedDevices = adapter.getBondedDevices();
                BluetoothDevice targetPrinter = null;
                for (BluetoothDevice device : bondedDevices) {
                    String name = device.getName();
                    if (name != null && (name.contains("Niimbot") || name.startsWith("B21") || name.startsWith("D11") || name.startsWith("B1") || name.startsWith("B3S") || name.startsWith("JC"))) {
                        targetPrinter = device;
                        break;
                    }
                }

                if (targetPrinter == null) {
                    runOnUiThread(() -> Toast.makeText(MainActivity.this, "Chưa ghép đôi máy in Niimbot qua Bluetooth cài đặt máy!", Toast.LENGTH_LONG).show());
                    return false;
                }

                disconnect();

                mSocket = targetPrinter.createRfcommSocketToServiceRecord(SPP_UUID);
                mSocket.connect();
                mOutputStream = mSocket.getOutputStream();
                mInputStream = mSocket.getInputStream();
                startRxThread();

                final String printerName = targetPrinter.getName();
                mPrinterName = (printerName != null) ? printerName : "Niimbot";

                runOnUiThread(() -> Toast.makeText(MainActivity.this, "Đã kết nối máy in Niimbot: " + mPrinterName, Toast.LENGTH_SHORT).show());
                return true;
            } catch (Exception e) {
                disconnect();
                final String msg = e.getMessage();
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "Lỗi kết nối máy in (hãy bật máy in): " + msg, Toast.LENGTH_SHORT).show());
                return false;
            }
        }

        @JavascriptInterface
        public boolean isConnected() {
            return mSocket != null && mSocket.isConnected();
        }

        @JavascriptInterface
        public String getDeviceName() {
            return (mSocket != null && mSocket.isConnected()) ? mPrinterName : "";
        }

        @JavascriptInterface
        public void disconnect() {
            stopRxThread();
            if (mOutputStream != null) {
                try { mOutputStream.close(); } catch (Exception ignored) {}
                mOutputStream = null;
            }
            if (mInputStream != null) {
                try { mInputStream.close(); } catch (Exception ignored) {}
                mInputStream = null;
            }
            if (mSocket != null) {
                try { mSocket.close(); } catch (Exception ignored) {}
                mSocket = null;
            }
            mPrinterName = "";
        }

        @JavascriptInterface
        public boolean sendRaw(int[] byteValues) {
            if (mOutputStream == null) return false;
            try {
                byte[] bytes = new byte[byteValues.length];
                for (int i = 0; i < byteValues.length; i++) {
                    bytes[i] = (byte) (byteValues[i] & 0xFF);
                }
                mOutputStream.write(bytes);
                mOutputStream.flush();
                return true;
            } catch (Exception e) {
                return false;
            }
        }

        @JavascriptInterface
        public boolean sendRawHex(String hex) {
            if (mOutputStream == null || hex == null || hex.isEmpty()) return false;
            try {
                int len = hex.length();
                byte[] bytes = new byte[len / 2];
                for (int i = 0; i < len; i += 2) {
                    bytes[i / 2] = (byte) ((Character.digit(hex.charAt(i), 16) << 4)
                                         + Character.digit(hex.charAt(i + 1), 16));
                }
                mOutputStream.write(bytes);
                mOutputStream.flush();
                return true;
            } catch (Exception e) {
                return false;
            }
        }

        @JavascriptInterface
        public void log(String tag, String msg) {
            Log.i("NiimbotBridge:" + (tag != null ? tag : "App"), msg != null ? msg : "");
        }

        @JavascriptInterface
        public void showToast(String message) {
            runOnUiThread(() -> Toast.makeText(MainActivity.this, message, Toast.LENGTH_SHORT).show());
        }
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && mWebView.canGoBack()) {
            mWebView.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        stopRxThread();
        if (mSocket != null) {
            try { mSocket.close(); } catch (Exception ignored) {}
        }
    }
}
