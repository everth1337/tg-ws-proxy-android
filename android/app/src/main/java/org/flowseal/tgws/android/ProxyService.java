package org.flowseal.tgws.android;

import android.app.*;
import android.content.*;
import android.os.*;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class ProxyService extends Service {
    public static volatile String state = "Остановлен";
    public static volatile String traffic = "↑ 0 B    ↓ 0 B";
    public static volatile boolean running = false;
    public static volatile boolean busy = false;
    private static final StringBuilder logs = new StringBuilder();
    private static final ExecutorService worker = Executors.newSingleThreadExecutor();
    private volatile boolean stopping = false;
    private PowerManager.WakeLock wakeLock;
    private final Handler main = new Handler(Looper.getMainLooper());
    private static final String CHANNEL = "proxy";

    @Override public void onCreate() {
        super.onCreate();
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(CHANNEL, "Работа прокси", NotificationManager.IMPORTANCE_LOW);
            getSystemService(NotificationManager.class).createNotificationChannel(ch);
        }
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && "stop".equals(intent.getAction())) { stopSelf(); return START_NOT_STICKY; }
        if (busy) return START_NOT_STICKY;
        stopping = false; busy = true; running = false; state = "Запускается…";
        startForeground(1, notification(state));
        wakeLock = ((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, getPackageName() + ":proxy");
        wakeLock.acquire();
        String secret = ProxySettings.secret(this);
        int port = ProxySettings.port(this);
        String domains = ProxySettings.prefs(this).getString("domains", "");
        worker.execute(() -> {
            try {
                if (!Python.isStarted()) Python.start(new AndroidPlatform(getApplicationContext()));
                Python.getInstance().getModule("android_bridge").callAttr("run", secret, port, domains, this);
            } catch (Exception e) {
                if (!stopping) { state = "Ошибка запуска — смотрите журнал"; onLog(e.toString()); }
            } finally {
                running = false; busy = false;
                if (stopping) state = "Остановлен";
                main.post(this::stopSelf);
            }
        });
        return START_NOT_STICKY;
    }

    public boolean isStopping() { return stopping; }
    public void onProxyReady() {
        if (stopping) return;
        running = true; state = "Прокси работает";
        main.post(() -> { if (!stopping) getSystemService(NotificationManager.class).notify(1, notification("127.0.0.1:" + ProxySettings.port(this))); });
    }
    public void onStats(int active, String up, String down) { traffic = "↑ " + up + "    ↓ " + down + "    ·    " + active + " подключений"; }
    public void onLog(String message) {
        synchronized (logs) {
            logs.append(message).append('\n');
            if (logs.length() > 16000) logs.delete(0, logs.length() - 12000);
        }
    }
    public static String logs() { synchronized (logs) { return logs.toString(); } }

    private Notification notification(String text) {
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop = PendingIntent.getService(this, 1, new Intent(this, ProxyService.class).setAction("stop"), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(this, CHANNEL) : new Notification.Builder(this);
        return b.setSmallIcon(org.flowseal.tgws.android.R.drawable.ic_proxy).setContentTitle("TG WS Proxy").setContentText(text).setContentIntent(open).setOngoing(true).addAction(new Notification.Action.Builder(null, "Остановить", stop).build()).build();
    }
    @Override public void onDestroy() {
        stopping = true; running = false;
        if (busy) {
            state = "Останавливается…";
            new Thread(() -> {
                if (Python.isStarted()) {
                    try { Python.getInstance().getModule("android_bridge").callAttr("stop"); }
                    catch (Exception e) { onLog(e.toString()); }
                }
            }, "proxy-stop").start();
        }
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        stopForeground(STOP_FOREGROUND_REMOVE);
        super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent) { return null; }
}
