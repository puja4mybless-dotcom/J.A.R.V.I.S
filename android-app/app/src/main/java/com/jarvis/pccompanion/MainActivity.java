package com.jarvis.pccompanion;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.speech.RecognizerIntent;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;

public class MainActivity extends Activity {
    private static final int REQUEST_AUDIO = 91;
    private static final int REQUEST_SPEECH = 92;
    private static final String PREFS = "companion_settings";
    private static final int BG = Color.rgb(0, 8, 12);
    private static final int PANEL = Color.rgb(0, 18, 27);
    private static final int CYAN = Color.rgb(0, 235, 245);
    private WebView webView;
    private ProgressBar progress;
    private String serverUrl = "";
    private boolean webVisible = false;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        Window window = getWindow();
        window.setStatusBarColor(BG);
        window.setNavigationBarColor(BG);
        window.getDecorView().setSystemUiVisibility(0);

        SharedPreferences saved = getSharedPreferences(PREFS, MODE_PRIVATE);
        String host = saved.getString("host", "");
        String token = saved.getString("token", "");
        int port = saved.getInt("port", 8000);
        if (isPrivateIpv4(host) && token.length() >= 24) {
            connect(host, port, token);
        } else {
            showConnectionScreen(host, port, "");
        }
    }

    private void showConnectionScreen(String lastHost, int lastPort, String message) {
        webVisible = false;
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
            webView = null;
        }

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BG);
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setGravity(Gravity.CENTER_HORIZONTAL);
        page.setPadding(dp(24), dp(42), dp(24), dp(30));
        scroll.addView(page);

        TextView emblem = new TextView(this);
        emblem.setText("◉");
        emblem.setTextSize(56);
        emblem.setTextColor(CYAN);
        emblem.setGravity(Gravity.CENTER);
        page.addView(emblem, matchWrap());

        TextView title = new TextView(this);
        title.setText("J.A.R.V.I.S.");
        title.setTextColor(CYAN);
        title.setTextSize(27);
        title.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        title.setGravity(Gravity.CENTER);
        title.setLetterSpacing(0.16f);
        page.addView(title, matchWrap());

        TextView subtitle = new TextView(this);
        subtitle.setText("PC COMPANION  //  MARK VII");
        subtitle.setTextColor(Color.rgb(109, 176, 191));
        subtitle.setTextSize(12);
        subtitle.setGravity(Gravity.CENTER);
        subtitle.setPadding(0, dp(6), 0, dp(28));
        page.addView(subtitle, matchWrap());

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(18), dp(20), dp(18), dp(20));
        card.setBackgroundColor(PANEL);
        page.addView(card, new LinearLayout.LayoutParams(-1, -2));

        TextView heading = new TextView(this);
        heading.setText("CONNECT TO YOUR WINDOWS PC");
        heading.setTextColor(CYAN);
        heading.setTextSize(13);
        heading.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        card.addView(heading, matchWrap());

        TextView instructions = new TextView(this);
        instructions.setText("Keep your phone and PC on the same Wi‑Fi network. Start J.A.R.V.I.S. on the PC with start_jarvis_wifi.bat, then enter the PC address and pairing token shown in its console.");
        instructions.setTextColor(Color.rgb(164, 197, 207));
        instructions.setTextSize(14);
        instructions.setLineSpacing(dp(3), 1f);
        instructions.setPadding(0, dp(10), 0, dp(18));
        card.addView(instructions, matchWrap());

        EditText hostInput = field("PC IPv4 address, e.g. 192.168.1.20", lastHost, false);
        hostInput.setInputType(0x00000011);
        card.addView(hostInput, fieldParams());

        EditText portInput = field("Port", String.valueOf(lastPort), false);
        portInput.setInputType(0x00000002);
        LinearLayout.LayoutParams portParams = fieldParams();
        portParams.topMargin = dp(10);
        card.addView(portInput, portParams);

        EditText tokenInput = field("Pairing token", "", true);
        LinearLayout.LayoutParams tokenParams = fieldParams();
        tokenParams.topMargin = dp(10);
        card.addView(tokenInput, tokenParams);

        if (!message.isEmpty()) {
            TextView error = new TextView(this);
            error.setText(message);
            error.setTextColor(Color.rgb(255, 168, 86));
            error.setTextSize(13);
            error.setPadding(0, dp(12), 0, 0);
            card.addView(error, matchWrap());
        }

        Button connect = new Button(this);
        connect.setText("CONNECT TO PC");
        connect.setTextColor(Color.BLACK);
        connect.setBackgroundTintList(android.content.res.ColorStateList.valueOf(CYAN));
        connect.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(-1, dp(52));
        buttonParams.topMargin = dp(20);
        card.addView(connect, buttonParams);
        connect.setOnClickListener(v -> {
            String host = hostInput.getText().toString().trim();
            String token = tokenInput.getText().toString().trim();
            int port;
            try {
                port = Integer.parseInt(portInput.getText().toString().trim());
            } catch (Exception e) {
                showConnectionScreen(host, 8000, "Enter a port number from 1 to 65535.");
                return;
            }
            if (!isPrivateIpv4(host)) {
                showConnectionScreen(host, port, "Use the private IPv4 address shown on your PC (10.x, 172.16–31.x, or 192.168.x). Keep both devices on the same Wi‑Fi.");
                return;
            }
            if (port < 1 || port > 65535 || token.length() < 24) {
                showConnectionScreen(host, port, "Check the port and enter the full pairing token from the PC console.");
                return;
            }
            connect(host, port, token);
        });

        TextView privacy = new TextView(this);
        privacy.setText("This companion connects only to a private-network PC address. The shared token protects PC commands. Use a trusted Wi‑Fi network; local HTTP is not encrypted.");
        privacy.setTextColor(Color.rgb(112, 143, 153));
        privacy.setTextSize(12);
        privacy.setGravity(Gravity.CENTER);
        privacy.setPadding(dp(6), dp(20), dp(6), 0);
        page.addView(privacy, matchWrap());
        setContentView(scroll);
    }

    private void connect(String host, int port, String token) {
        serverUrl = "http://" + host + ":" + port + "/";
        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putString("host", host).putInt("port", port).putString("token", token).apply();
        webVisible = true;

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);
        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(8), 0, dp(8), 0);
        toolbar.setBackgroundColor(BG);
        root.addView(toolbar, new LinearLayout.LayoutParams(-1, dp(46)));

        Button back = new Button(this);
        back.setText("‹");
        back.setTextSize(26);
        back.setTextColor(CYAN);
        back.setBackgroundColor(Color.TRANSPARENT);
        toolbar.addView(back, new LinearLayout.LayoutParams(dp(48), -1));
        back.setOnClickListener(v -> showConnectionScreen(host, port, ""));

        TextView label = new TextView(this);
        label.setText("J.A.R.V.I.S.  //  PC LINK");
        label.setTextColor(CYAN);
        label.setTextSize(12);
        label.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        toolbar.addView(label, new LinearLayout.LayoutParams(0, -2, 1));

        Button disconnect = new Button(this);
        disconnect.setText("LINK");
        disconnect.setTextColor(CYAN);
        disconnect.setTextSize(10);
        disconnect.setBackgroundColor(Color.TRANSPARENT);
        toolbar.addView(disconnect, new LinearLayout.LayoutParams(dp(60), -1));
        disconnect.setOnClickListener(v -> showConnectionScreen(host, port, ""));

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        progress.setProgressTintList(android.content.res.ColorStateList.valueOf(CYAN));
        progress.setIndeterminateTintList(android.content.res.ColorStateList.valueOf(CYAN));
        root.addView(progress, new LinearLayout.LayoutParams(-1, dp(2)));

        webView = new WebView(this);
        webView.setBackgroundColor(BG);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setAllowFileAccess(false);
        webView.getSettings().setAllowContentAccess(false);
        webView.getSettings().setMixedContentMode(android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        webView.addJavascriptInterface(new SpeechBridge(), "AndroidSpeechBridge");
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public void onProgressChanged(WebView view, int value) {
                progress.setProgress(value);
                progress.setVisibility(value >= 100 ? View.GONE : View.VISIBLE);
            }
        });
        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String scheme = request.getUrl().getScheme();
                return !"http".equals(scheme) && !"https".equals(scheme);
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, android.webkit.WebResourceError error) {
                if (request.isForMainFrame()) {
                    runOnUiThread(() -> new AlertDialog.Builder(MainActivity.this)
                            .setTitle("PC connection lost")
                            .setMessage("Check that J.A.R.V.I.S. is running and both devices are on the same Wi‑Fi.")
                            .setPositiveButton("Reconnect", (d, w) -> view.reload())
                            .setNegativeButton("Connection settings", (d, w) -> showConnectionScreen(host, port, ""))
                            .show());
                }
            }
        });
        root.addView(webView, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
        String fragment = "#access_token=" + Uri.encode(token);
        webView.loadUrl(serverUrl + fragment);
    }

    private final class SpeechBridge {
        @JavascriptInterface public void startSpeechInput() {
            runOnUiThread(() -> {
                if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                    requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQUEST_AUDIO);
                } else startSpeechRecognizer();
            });
        }
    }

    private void startSpeechRecognizer() {
        try {
            Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "hi-IN");
            intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak your J.A.R.V.I.S. command");
            startActivityForResult(intent, REQUEST_SPEECH);
        } catch (Exception e) {
            Toast.makeText(this, "Speech recognition is not available on this phone.", Toast.LENGTH_LONG).show();
        }
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        if (requestCode == REQUEST_AUDIO && results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) startSpeechRecognizer();
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_SPEECH && resultCode == RESULT_OK && data != null && webView != null) {
            ArrayList<String> results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
            if (results != null && !results.isEmpty()) {
                String safeText = org.json.JSONObject.quote(results.get(0));
                webView.evaluateJavascript("window.jarvisApp && window.jarvisApp.handleUserInput(" + safeText + ")", null);
            }
        }
    }

    @Override public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else if (webVisible) showConnectionScreen("", 8000, "");
        else super.onBackPressed();
    }

    private EditText field(String hint, String value, boolean secret) {
        EditText edit = new EditText(this);
        edit.setSingleLine(true);
        edit.setText(value);
        edit.setHint(hint);
        edit.setHintTextColor(Color.rgb(93, 132, 145));
        edit.setTextColor(Color.WHITE);
        edit.setTextSize(14);
        edit.setPadding(dp(12), 0, dp(12), 0);
        edit.setBackgroundTintList(android.content.res.ColorStateList.valueOf(CYAN));
        if (secret) edit.setInputType(0x00000081);
        return edit;
    }

    private boolean isPrivateIpv4(String value) {
        String[] parts = value.split("\\.");
        if (parts.length != 4) return false;
        int[] ip = new int[4];
        try { for (int i = 0; i < 4; i++) { ip[i] = Integer.parseInt(parts[i]); if (ip[i] < 0 || ip[i] > 255) return false; } }
        catch (NumberFormatException e) { return false; }
        return ip[0] == 10 || (ip[0] == 192 && ip[1] == 168) || (ip[0] == 172 && ip[1] >= 16 && ip[1] <= 31);
    }

    private LinearLayout.LayoutParams fieldParams() { return new LinearLayout.LayoutParams(-1, dp(50)); }
    private LinearLayout.LayoutParams matchWrap() { return new LinearLayout.LayoutParams(-1, -2); }
    private int dp(int value) { return (int) (value * getResources().getDisplayMetrics().density + 0.5f); }
}
