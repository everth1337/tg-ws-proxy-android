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
import java.io.FileInputStream;
import org.junit.Assume;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class ProxyDeviceTest {
    private static void shell(String command) throws Exception {
        try(android.os.ParcelFileDescriptor fd=InstrumentationRegistry.getInstrumentation().getUiAutomation().executeShellCommand(command);
            FileInputStream input=new FileInputStream(fd.getFileDescriptor())) {
            byte[] buffer=new byte[1024]; while(input.read(buffer)!=-1) { }
        }
    }

    @Test public void defaultNetworkHandover() throws Exception {
        // Opt in only on the dedicated emulator (or a USB-attached test phone).
        Assume.assumeTrue("true".equals(InstrumentationRegistry.getArguments().getString("network_handover")));
        Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        Intent service=new Intent(context,ProxyService.class);
        if(Build.VERSION.SDK_INT>=26)context.startForegroundService(service);else context.startService(service);
        try {
            long deadline=System.currentTimeMillis()+30000;
            while((!ProxyService.running || !ProxyService.networkStatus.equals("Сеть: Wi-Fi")) && System.currentTimeMillis()<deadline)Thread.sleep(100);
            assertTrue("Start the handover test on Wi-Fi",ProxyService.running && ProxyService.networkStatus.equals("Сеть: Wi-Fi"));
            try(Socket old=new Socket("127.0.0.1",ProxySettings.port(context))) {
                int before=ProxyService.listenerStarts;
                shell("svc wifi disable");
                deadline=System.currentTimeMillis()+30000;
                while((!ProxyService.running || ProxyService.listenerStarts<=before || !ProxyService.networkStatus.contains("мобильная")) && System.currentTimeMillis()<deadline)Thread.sleep(100);
                assertTrue(ProxyService.networkStatus,ProxyService.networkStatus.contains("мобильная"));
                assertTrue("Network callback did not recreate the listener",ProxyService.listenerStarts>before && ProxyService.running);
                old.setSoTimeout(5000);
                assertEquals(-1,old.getInputStream().read());
                try(Socket fresh=new Socket("127.0.0.1",ProxySettings.port(context))) { assertTrue(fresh.isConnected()); }
                before=ProxyService.listenerStarts;
                shell("svc wifi enable");
                deadline=System.currentTimeMillis()+30000;
                while((!ProxyService.running || ProxyService.listenerStarts<=before || !ProxyService.networkStatus.equals("Сеть: Wi-Fi")) && System.currentTimeMillis()<deadline)Thread.sleep(100);
                assertTrue(ProxyService.networkStatus,ProxyService.networkStatus.equals("Сеть: Wi-Fi"));
                assertTrue("Wi-Fi recovery did not recreate the listener",ProxyService.listenerStarts>before && ProxyService.running);
            }
        } finally {
            shell("svc wifi enable");
            context.stopService(service);
            long deadline=System.currentTimeMillis()+15000;
            while(ProxyService.busy && System.currentTimeMillis()<deadline)Thread.sleep(100);
        }
    }

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
            try(Socket s=new Socket("127.0.0.1",ProxySettings.port(context))) {
                assertTrue(s.isConnected());
                int previousStarts = ProxyService.listenerStarts;
                context.startService(new Intent(context,ProxyService.class).setAction("reconnect"));
                deadline=System.currentTimeMillis()+15000;
                while((ProxyService.listenerStarts<=previousStarts || !ProxyService.running) && System.currentTimeMillis()<deadline)Thread.sleep(100);
                assertTrue("Listener was not recreated",ProxyService.listenerStarts>previousStarts);
                assertTrue(ProxyService.running);
                s.setSoTimeout(5000);
                assertEquals("Old connection survived reconnect",-1,s.getInputStream().read());
                try(Socket fresh=new Socket("127.0.0.1",ProxySettings.port(context))) { assertTrue(fresh.isConnected()); }
            }
            context.stopService(i);
            deadline=System.currentTimeMillis()+15000;
            while(ProxyService.busy&&System.currentTimeMillis()<deadline)Thread.sleep(100);
            assertFalse("Service failed to stop",ProxyService.busy);
            try { new Socket("127.0.0.1",ProxySettings.port(context)).close(); fail("Listener still open"); }
            catch(java.io.IOException expected) { }
        }
    }
}
