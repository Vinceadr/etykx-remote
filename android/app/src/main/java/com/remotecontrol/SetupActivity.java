package com.remotecontrol;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.nsd.NsdManager;
import android.net.nsd.NsdServiceInfo;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.JSONObject;

public class SetupActivity extends AppCompatActivity {
    private static final String PREFS         = "rc_prefs";
    private static final int    DISCOVER_PORT = 5001;
    private static final String NSD_SERVICE   = "_interception._tcp";
    private static final int    TIMEOUT_MS    = 12000;

    private EditText  etIp, etPort;
    private Button    btnConnect, btnDiscover;
    private TextView  tvStatus;
    private final AtomicBoolean found = new AtomicBoolean(false);

    private NsdManager                   nsdManager;
    private NsdManager.DiscoveryListener nsdListener;

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

        btnDiscover.setOnClickListener(v -> startDiscovery());

        if (prefs.getString("ip", "").isEmpty()) startDiscovery();
    }

    private void startDiscovery() {
        found.set(false);
        btnDiscover.setEnabled(false);
        btnDiscover.setText("Scan...");
        tvStatus.setText("Recherche du PC sur le reseau...");

        // Method 1: mDNS via NsdManager
        startNsdDiscovery();

        // Method 2: UDP broadcast listener (fallback)
        new Thread(() -> {
            try (DatagramSocket socket = new DatagramSocket(DISCOVER_PORT)) {
                socket.setBroadcast(true);
                socket.setSoTimeout(TIMEOUT_MS);
                byte[] buf = new byte[512];
                DatagramPacket pkt = new DatagramPacket(buf, buf.length);
                socket.receive(pkt);
                String json = new String(pkt.getData(), 0, pkt.getLength());
                JSONObject obj = new JSONObject(json);
                if ("interception".equals(obj.optString("service"))) {
                    onPcFound(pkt.getAddress().getHostAddress(),
                              String.valueOf(obj.optInt("port", 5000)));
                }
            } catch (Exception ignored) { }
            if (!found.get()) onDiscoveryFailed();
        }).start();

        new Handler(Looper.getMainLooper()).postDelayed(() -> {
            if (!found.get()) onDiscoveryFailed();
        }, TIMEOUT_MS + 1000);
    }

    private void startNsdDiscovery() {
        nsdManager = (NsdManager) getSystemService(Context.NSD_SERVICE);
        nsdListener = new NsdManager.DiscoveryListener() {
            @Override public void onDiscoveryStarted(String type) {}
            @Override public void onDiscoveryStopped(String type) {}
            @Override public void onStartDiscoveryFailed(String t, int e) {}
            @Override public void onStopDiscoveryFailed(String t, int e)  {}

            @Override
            public void onServiceFound(NsdServiceInfo info) {
                nsdManager.resolveService(info, new NsdManager.ResolveListener() {
                    @Override public void onResolveFailed(NsdServiceInfo i, int e) {}
                    @Override
                    public void onServiceResolved(NsdServiceInfo resolved) {
                        InetAddress addr = resolved.getHost();
                        int port = resolved.getPort();
                        if (addr != null) onPcFound(addr.getHostAddress(), String.valueOf(port));
                    }
                });
            }
            @Override public void onServiceLost(NsdServiceInfo info) {}
        };
        try {
            nsdManager.discoverServices(NSD_SERVICE, NsdManager.PROTOCOL_DNS_SD, nsdListener);
        } catch (Exception ignored) {}
    }

    private void onPcFound(String ip, String port) {
        if (!found.compareAndSet(false, true)) return;
        stopNsd();
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

    private void onDiscoveryFailed() {
        stopNsd();
        new Handler(Looper.getMainLooper()).post(() -> {
            btnDiscover.setEnabled(true);
            btnDiscover.setText("Detecter");
            if (!found.get())
                tvStatus.setText("PC non trouve. Verifie que le serveur tourne, puis reessaie.");
        });
    }

    private void stopNsd() {
        try {
            if (nsdManager != null && nsdListener != null)
                nsdManager.stopServiceDiscovery(nsdListener);
        } catch (Exception ignored) {}
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        stopNsd();
    }
}