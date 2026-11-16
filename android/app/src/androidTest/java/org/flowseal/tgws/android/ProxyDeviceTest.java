package org.flowseal.tgws.android;

import android.content.Context;
import android.content.Intent;
import android.os.Build;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.net.Socket;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class ProxyDeviceTest {
    @Test public void cryptoAndServiceLifecycle() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        if(!Python.isStarted())Python.start(new AndroidPlatform(context));
        assertEquals("NIST AES-CTR streaming: OK",Python.getInstance().getModule("android_bridge").callAttr("crypto_selftest").toString());
        for(int cycle=0;cycle<2;cycle++) {
            Intent i=new Intent(context,ProxyService.class);
            if(Build.VERSION.SDK_INT>=26)context.startForegroundService(i);else context.startService(i);
            long deadline=System.currentTimeMillis()+30000;
            while(!ProxyService.running&&System.currentTimeMillis()<deadline)Thread.sleep(100);
            assertTrue(ProxyService.logs(),ProxyService.running);
            try(Socket s=new Socket("127.0.0.1",ProxySettings.port(context))) { assertTrue(s.isConnected()); }
            context.stopService(i);
            deadline=System.currentTimeMillis()+15000;
            while(ProxyService.busy&&System.currentTimeMillis()<deadline)Thread.sleep(100);
            assertFalse("Service failed to stop",ProxyService.busy);
            try { new Socket("127.0.0.1",ProxySettings.port(context)).close(); fail("Listener still open"); }
            catch(java.io.IOException expected) { }
        }
    }
}
