package org.flowseal.tgws.android;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.view.*;
import android.widget.*;

public class MainActivity extends Activity {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private TextView status, traffic, endpoint, network;
    private Button toggle, telegram, reconnect;
    private final int ink = Color.rgb(231,240,248), mint = Color.rgb(105,224,186);
    private final Runnable refresh = new Runnable() { public void run() { render(); handler.postDelayed(this, 500); } };
    private int dp(int n) { return (int)(getResources().getDisplayMetrics().density * n); }

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        ScrollView scroll = new ScrollView(this); scroll.setFillViewport(true);
        LinearLayout page = new LinearLayout(this); page.setOrientation(LinearLayout.VERTICAL); page.setPadding(dp(24),dp(24),dp(24),dp(28));
        scroll.addView(page); setContentView(scroll);
        page.setOnApplyWindowInsetsListener((v, insets) -> { v.setPadding(dp(24),dp(24)+insets.getSystemWindowInsetTop(),dp(24),dp(28)+insets.getSystemWindowInsetBottom()); return insets; });
        addText(page,"FLOWSEAL  /  ANDROID",12,mint, false);
        addText(page,"TG WS Proxy",34,ink,true);
        addText(page,"Локальный прокси для Telegram",16,Color.rgb(156,176,194),false);
        LinearLayout card = new LinearLayout(this); card.setOrientation(LinearLayout.VERTICAL); card.setPadding(dp(20),dp(22),dp(20),dp(22));
        GradientDrawable bg = new GradientDrawable(); bg.setColor(Color.rgb(26,41,55)); bg.setCornerRadius(dp(20)); card.setBackground(bg);
        LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(-1,-2); cp.topMargin = dp(32); cp.bottomMargin = dp(20); page.addView(card, cp);
        status = addText(card,"Остановлен",22,mint,true); status.setContentDescription("Статус прокси");
        endpoint = addText(card,"",15,ink,false);
        traffic = addText(card,"",13,Color.rgb(156,176,194),false);
        network = addText(card,"",13,Color.rgb(156,176,194),false);
        toggle = button(page,"Запустить прокси", v -> {
            if (ProxyService.busy) { stopService(new Intent(this,ProxyService.class)); return; }
            if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},1);
            Intent i = new Intent(this,ProxyService.class);
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(i); else startService(i);
        });
        telegram = button(page,"Подключить Telegram", v -> {
            try { startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(ProxySettings.link(this)))); }
            catch (ActivityNotFoundException e) { new AlertDialog.Builder(this).setMessage("Установите Telegram или скопируйте ссылку и откройте её в своём клиенте.").setPositiveButton("Понятно",null).show(); }
        });
        reconnect = button(page,"Переподключить", v -> startService(new Intent(this,ProxyService.class).setAction("reconnect")));
        button(page,"Скопировать ссылку",v -> {
            ((android.content.ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("Telegram proxy",ProxySettings.link(this)));
            Toast.makeText(this,"Ссылка скопирована",Toast.LENGTH_SHORT).show();
        });
        button(page,"Настройки",v -> settings());
        button(page,"Журнал",v -> {
            TextView text = new TextView(this); text.setText(ProxyService.logs().isEmpty()?"Журнал пуст. Запустите прокси.":ProxyService.logs()); text.setTextSize(12); text.setTextIsSelectable(true); text.setPadding(dp(16),dp(12),dp(16),dp(12));
            ScrollView sv = new ScrollView(this); sv.addView(text);
            new AlertDialog.Builder(this).setTitle("Журнал прокси").setView(sv).setPositiveButton("Закрыть",null).show();
        });
        addText(page,"1. Запустите прокси\n2. Нажмите «Подключить Telegram»\n3. Подтвердите прокси в Telegram",15,ink,false).setPadding(0,dp(24),0,dp(12));
        addText(page,"Прокси работает на этом телефоне по адресу 127.0.0.1. Пока он нужен Telegram, оставляйте службу включённой. После остановки отключите прокси в Telegram.",13,Color.rgb(156,176,194),false);
        button(page,"Фоновая работа",v -> startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+getPackageName()))));
        addText(page,"Неофициальный Android-порт · 1.11.4-android.2\nFlowseal/tg-ws-proxy · MIT",12,Color.rgb(156,176,194),false);
        render();
    }
    private TextView addText(LinearLayout parent,String text,int size,int color,boolean bold) {
        TextView t = new TextView(this); t.setText(text); t.setTextSize(size); t.setTextColor(color); t.setPadding(0,dp(5),0,dp(5));
        if(bold)t.setTypeface(null,Typeface.BOLD); parent.addView(t,new LinearLayout.LayoutParams(-1,-2)); return t;
    }
    private Button button(LinearLayout parent,String label,View.OnClickListener click) {
        Button b = new Button(this); b.setText(label); b.setAllCaps(false); b.setTextSize(16); b.setOnClickListener(click);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1,dp(54)); p.topMargin=dp(5); parent.addView(b,p); return b;
    }
    private void render() {
        status.setText(ProxyService.state); traffic.setText(ProxyService.traffic); endpoint.setText("127.0.0.1 : " + ProxySettings.port(this));
        network.setText(ProxyService.networkStatus); reconnect.setEnabled(ProxyService.busy && ProxyService.running);
        toggle.setText(ProxyService.busy ? "Остановить прокси" : "Запустить прокси");
        toggle.setEnabled(!ProxyService.state.equals("Останавливается…")); telegram.setEnabled(ProxyService.running);
    }
    private void settings() {
        if(ProxyService.busy){Toast.makeText(this,"Сначала остановите прокси",Toast.LENGTH_SHORT).show();return;}
        LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);box.setPadding(dp(20),dp(8),dp(20),dp(8));
        addText(box,"Порт (1024–65535)",14,ink,false);
        EditText port = new EditText(this);port.setInputType(2);port.setText(String.valueOf(ProxySettings.port(this)));box.addView(port);
        addText(box,"Свой CF-домен (необязательно, без https://)",14,ink,false);
        EditText domain=new EditText(this);domain.setSingleLine(true);domain.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_URI);domain.setText(ProxySettings.prefs(this).getString("domains",""));box.addView(domain);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Настройки").setView(box).setNegativeButton("Отмена",null).setPositiveButton("Сохранить",null).create();
        dialog.setOnShowListener(d -> dialog.getButton(-1).setOnClickListener(v -> {
            try {
                int n=Integer.parseInt(port.getText().toString().trim());if(n<1024||n>65535)throw new IllegalArgumentException();
                String host=domain.getText().toString().trim().toLowerCase(java.util.Locale.ROOT);
                if(!host.isEmpty() && (!host.matches("[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\\.[a-z]{2,63}")||host.contains(".."))) {domain.setError("Введите домен без пути и протокола");return;}
                ProxySettings.prefs(this).edit().putInt("port",n).putString("domains",host).apply();dialog.dismiss();render();
            }catch(IllegalArgumentException e){port.setError("Порт от 1024 до 65535");}
        }));dialog.show();
    }
    @Override public void onResume(){super.onResume();handler.post(refresh);}
    @Override public void onPause(){handler.removeCallbacks(refresh);super.onPause();}
}
