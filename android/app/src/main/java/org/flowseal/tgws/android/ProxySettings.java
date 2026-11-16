package org.flowseal.tgws.android;

import android.content.Context;
import android.content.SharedPreferences;
import java.security.SecureRandom;

final class ProxySettings {
    static SharedPreferences prefs(Context c) { return c.getSharedPreferences("proxy", Context.MODE_PRIVATE); }
    static synchronized String secret(Context c) {
        String value = prefs(c).getString("secret", null);
        if (value == null) {
            byte[] bytes = new byte[16]; new SecureRandom().nextBytes(bytes);
            StringBuilder s = new StringBuilder();
            for (byte b : bytes) s.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
            value = s.toString(); prefs(c).edit().putString("secret", value).commit();
        }
        return value;
    }
    static int port(Context c) { return prefs(c).getInt("port", 1443); }
    static String link(Context c) { return "tg://proxy?server=127.0.0.1&port=" + port(c) + "&secret=dd" + secret(c); }
}
