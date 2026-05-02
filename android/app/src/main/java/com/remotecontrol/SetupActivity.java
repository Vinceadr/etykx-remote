package com.remotecontrol;

import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import org.json.JSONObject;

public class SetupActivity extends AppCompatActivity {
    private static final String PREFS = "rc_prefs";
    private static final int DISCOVER_PORT = 5001;
    private static final int DISCOVER_TIMEOUT_MS = 10000;

    private EditText etIp, etPort;
    private Button btnConnect, btnDiscover;
    private TextView tvStatus;
    private volatile boolean discovering = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_setup);

        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        etIp      = findViewById(R.id.et_ip);
        etPort    = findViewById(R.id.et_port);
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
            Intent intent = new Intent(this, MainActivity.class);
            intent.putExtra("url", "http://" + ip + ":" + port);
            startActivity(intent);
        });

        btnDiscover.setOnClickListener(v -> startDiscovery());

        // Auto-launch discovery if no IP saved yet
        if (prefs.getString("ip", "").isEmpty()) {
            startDiscovery();
        }
    }

    private void startDiscovery() {
        if (discovering) return;
        discovering = true;
        btnDiscover.setEnabled(false);
        btnDiscover.setText("Scan...");
        tvStatus.setText("🔍 Recherche du PC sur le réseau...");

        new Thread(() -> {
            try (DatagramSocket socket = new DatagramSocket(DISCOVER_PORT)) {
                socket.setBroadcast(true);
                socket.setSoTimeout(DISCOVER_TIMEOUT_MS);

                byte[] buf = new byte[512];
                DatagramPacket packet = new DatagramPacket(buf, buf.length);
                socket.receive(packet);

                String json = new String(packet.getData(), 0, packet.getLength());
                JSONObject obj = new JSONObject(json);
                if (!"interception".equals(obj.optString("service"))) throw new Exception("wrong service");

                String ip   = packet.getAddress().getHostAddress();
                String port = String.valueOf(obj.optInt("port", 5000));

                new Handler(Looper.getMainLooper()).post(() -> {
                    discovering = false;
                    etIp.setText(ip);
                    etPort.setText(port);
                    btnDiscover.setEnabled(true);
                    btnDiscover.setText("🔍 Détecter");
                    tvStatus.setText("✅ PC trouvé : " + ip + ":" + port + "  — appuie sur Connecter");
                });

            } catch (Exception e) {
                new Handler(Looper.getMainLooper()).post(() -> {
                    discovering = false;
                    btnDiscover.setEnabled(true);
                    btnDiscover.setText("🔍 Détecter");
                    tvStatus.setText("❌ PC non trouvé. Lance start.ps1 sur le PC, puis réessaie.");
                });
            }
        }).start();
    }
}
