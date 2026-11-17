package org.flowseal.tgws.android;

import android.content.Context;
import android.os.Bundle;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import com.chaquo.python.Python;
import com.chaquo.python.PyObject;
import com.chaquo.python.android.AndroidPlatform;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import org.junit.Test;
import org.junit.Assume;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class NetworkDiagnosticTest {
    @Test public void routesOnCurrentNetwork() throws Exception {
        Assume.assumeTrue("true".equals(InstrumentationRegistry.getArguments().getString("network_diagnostics")));
        Context target=InstrumentationRegistry.getInstrumentation().getTargetContext();
        if(!Python.isStarted())Python.start(new AndroidPlatform(target));
        String script;
        try(InputStream input=InstrumentationRegistry.getInstrumentation().getContext().getAssets().open("network_diagnostics.py")) {
            ByteArrayOutputStream output=new ByteArrayOutputStream();
            byte[] buffer=new byte[8192]; int count;
            while((count=input.read(buffer))!=-1)output.write(buffer,0,count);
            script=output.toString(StandardCharsets.UTF_8.name());
        }
        PyObject builtins=Python.getInstance().getBuiltins();
        PyObject globals=builtins.callAttr("dict");
        globals.callAttr("__setitem__","diagnostic_mode",InstrumentationRegistry.getArguments().getString("diagnostic_mode","all"));
        builtins.callAttr("exec",script,globals);
        Bundle result=new Bundle();
        result.putString("network_diagnostics",globals.callAttr("get","report_json").toString());
        InstrumentationRegistry.getInstrumentation().sendStatus(0,result);
    }
}
