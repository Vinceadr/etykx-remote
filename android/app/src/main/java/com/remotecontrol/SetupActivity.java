package com.remotecontrol;

import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import androidx.appcompat.app.AppCompatActivity;

public class SetupActivity extends AppCompatActivity {
    private static final String PREFS = "rc_prefs";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_setup);

        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        EditText etIp   = findViewById(R.id.et_ip);
        EditText etPort = findViewById(R.id.et_port);
        Button   btnOk  = findViewById(R.id.btn_connect);

        // Restore saved values
        etIp.setText(prefs.getString("ip", ""));
        etPort.setText(prefs.getString("port", "5000"));

        btnOk.setOnClickListener(v -> {
            String ip   = etIp.getText().toString().trim();
            String port = etPort.getText().toString().trim();
            if (ip.isEmpty()) { etIp.setError("Requis"); return; }
            if (port.isEmpty()) port = "5000";

            prefs.edit().putString("ip", ip).putString("port", port).apply();

            Intent intent = new Intent(this, MainActivity.class);
            intent.putExtra("url", "http://" + ip + ":" + port);
            startActivity(intent);
        });

        // Auto-connect if IP already saved
        String savedIp = prefs.getString("ip", "");
        if (!savedIp.isEmpty()) {
            String savedPort = prefs.getString("port", "5000");
            Intent intent = new Intent(this, MainActivity.class);
            intent.putExtra("url", "http://" + savedIp + ":" + savedPort);
            startActivity(intent);
        }
    }
}
