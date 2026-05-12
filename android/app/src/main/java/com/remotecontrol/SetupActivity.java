package com.remotecontrol;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.wifi.WifiManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public class SetupActivity extends AppCompatActivity {
    private static final String PREFS    = "rc_prefs";
    private static final int    PORT     = 5000;
    private static final int    TIMEOUT  = 600; // ms per host

    private EditText      etIp, etPort;
    private Button        btnConnect, btnDiscover;
    private TextView      tvStatus;
    private final AtomicBoolean found = new AtomicBoolean(false);
    private ExecutorService scanPool;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_setup);

        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        etIp        = findViewById(R.id.et_ip);
        etPort      = findViewById(R.id.et_port);
        btnConnect  = findViewById(R.id.btn_connect);
        btnDiscover = findViewById(R.id.btn_discover);
        tvStatus    = findViewById(R.id.tv_status);

        etIp.setText(prefs.getString("ip", ""));
        etPort.setText(prefs.getString("port", "5000"));

        btnConnect.setOnClickListener(v -> {
            String ip   = etIp.getText().toString().trim();
            String port = etPort.getText().toString().trim();
            if (ip.isEmpty()) { etIp.setError("Requis"); return; }
            if (port.isEmpty()) port = "5000";
            prefs.edit().putString("ip", ip).putString("port", port).apply();
            startActivity(new Intent(this, MainActivity.class)
                    .putExtra("url", "http://" + ip + ":" + port));
        });

        btnDiscover.setOnClickListener(v -> startScan());

        if (prefs.getString("ip", "").isEmpty()) startScan();
    }

    private void startScan() {
        if (scanPool != null && !scanPool.isShutdown()) scanPool.shutdownNow();
        found.set(false);
        btnDiscover.setEnabled(false);
        btnDiscover.setText("Scan...");
        tvStatus.setText("Scan du reseau en cours...");

        // Determine subnet from phone Wi-Fi IP
        String subnet = getSubnet();
        if (subnet == null) {
            tvStatus.setText("Wi-Fi non connecte. Connecte-toi au Wi-Fi du PC.");
            btnDiscover.setEnabled(true);
            btnDiscover.setText("Detecter");
            return;
        }

        final String sub = subnet;
        scanPool = Executors.newFixedThreadPool(50);
        final int total = 254;
        final java.util.concurrent.atomic.AtomicInteger done = new java.util.concurrent.atomic.AtomicInteger(0);

        for (int i = 1; i <= total; i++) {
            final String ip = sub + i;
            scanPool.submit(() -> {
                if (!found.get()) {
                    try {
                        URL url = new URL("http://" + ip + ":" + PORT + "/ping");
                        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                        conn.setConnectTimeout(TIMEOUT);
                        conn.setReadTimeout(TIMEOUT);
                        conn.setRequestMethod("GET");
                        int code = conn.getResponseCode();
                        if (code == 200) {
                            // Verify it's the Interception server (not just any HTTP server)
                            java.io.InputStream is = conn.getInputStream();
                            byte[] buf = new byte[256];
                            int len = is.read(buf);
                            String body = len > 0 ? new String(buf, 0, len) : "";
                            conn.disconnect();
                            if (body.contains("interception")) onPcFound(ip, String.valueOf(PORT));
                        } else {
                            conn.disconnect();
                        }
                    } catch (Exception ignored) {}
                }
                int d = done.incrementAndGet();
                if (d == total && !found.get()) {
                    onScanFailed();
                }
            });
        }
    }

    private String getSubnet() {
        try {
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {
                // API 31+ (Android 12+): WifiManager.getConnectionInfo() is deprecated
                android.net.ConnectivityManager cm = (android.net.ConnectivityManager)
                        getApplicationContext().getSystemService(Context.CONNECTIVITY_SERVICE);
                android.net.Network network = cm.getActiveNetwork();
                if (network == null) return null;
                android.net.LinkProperties lp = cm.getLinkProperties(network);
                if (lp == null) return null;
                for (android.net.LinkAddress la : lp.getLinkAddresses()) {
                    java.net.InetAddress addr = la.getAddress();
                    if (addr instanceof java.net.Inet4Address && !addr.isLoopbackAddress()) {
                        String[] parts = addr.getHostAddress().split("\\.");
                        if (parts.length == 4)
                            return parts[0] + "." + parts[1] + "." + parts[2] + ".";
                    }
                }
                return null;
            } else {
                WifiManager wm = (WifiManager) getApplicationContext()
                        .getSystemService(Context.WIFI_SERVICE);
                @SuppressWarnings("deprecation")
                int ip = wm.getConnectionInfo().getIpAddress();
                if (ip == 0) return null;
                return String.format("%d.%d.%d.",
                        ip & 0xFF, (ip >> 8) & 0xFF, (ip >> 16) & 0xFF);
            }
        } catch (Exception e) { return null; }
    }

    private void onPcFound(String ip, String port) {
        if (!found.compareAndSet(false, true)) return;
        if (scanPool != null) scanPool.shutdownNow();
        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
            .putString("ip", ip).putString("port", port).apply();
        new Handler(Looper.getMainLooper()).post(() -> {
            etIp.setText(ip);
            etPort.setText(port);
            btnDiscover.setEnabled(true);
            btnDiscover.setText("Detecter");
            tvStatus.setText("PC trouve : " + ip + ":" + port + " - appuie sur Connecter");
        });
    }

    private void onScanFailed() {
        new Handler(Looper.getMainLooper()).post(() -> {
            btnDiscover.setEnabled(true);
            btnDiscover.setText("Detecter");
            if (!found.get())
                tvStatus.setText("PC non trouve. Verifie que le serveur tourne sur le PC.");
        });
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (scanPool != null) scanPool.shutdownNow();
    }
}