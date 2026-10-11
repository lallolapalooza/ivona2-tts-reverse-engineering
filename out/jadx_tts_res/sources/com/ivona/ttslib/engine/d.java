package com.ivona.ttslib.engine;

import android.content.Context;
import android.net.LocalSocket;
import android.net.LocalSocketAddress;
import android.os.AsyncTask;
import android.os.Build;
import android.util.Log;
import java.io.IOException;
import java.io.OutputStream;
import java.util.Observable;

/* compiled from: TTSEngineConnector.java */
/* loaded from: classes.dex */
public class d extends Observable {
    private static boolean a = true;
    private static f b = null;
    private static d d = null;
    private Context c = null;

    private d() {
    }

    public static d a() {
        if (d == null) {
            d = new d();
        }
        return d;
    }

    public void a(Context context) {
        if (b == null || b.getStatus() == AsyncTask.Status.FINISHED) {
            if (com.ivona.tts.commonlib.a.c) {
                Log.d("TTSEngineConnector", "elisten init, socket address:" + b(context));
            }
            a = true;
            b = new f(this);
            this.c = context;
            if (Build.VERSION.SDK_INT <= 12) {
                b.execute(b(context));
            } else {
                b.executeOnExecutor(AsyncTask.THREAD_POOL_EXECUTOR, b(context));
            }
        }
    }

    public void b() {
        if (b != null && b.a()) {
            if (com.ivona.tts.commonlib.a.c) {
                Log.d("TTSEngineConnector", "elisten stop");
            }
            a = false;
            LocalSocket localSocket = new LocalSocket();
            try {
                try {
                    localSocket.connect(new LocalSocketAddress(b(this.c)));
                    OutputStream outputStream = localSocket.getOutputStream();
                    outputStream.write("close".getBytes());
                    outputStream.close();
                    if (localSocket != null) {
                        try {
                            localSocket.close();
                        } catch (IOException e) {
                            if (com.ivona.tts.commonlib.a.c) {
                                e.printStackTrace();
                            }
                        }
                    }
                } catch (IOException e2) {
                    if (com.ivona.tts.commonlib.a.c) {
                        e2.printStackTrace();
                    }
                    if (localSocket != null) {
                        try {
                            localSocket.close();
                        } catch (IOException e3) {
                            if (com.ivona.tts.commonlib.a.c) {
                                e3.printStackTrace();
                            }
                        }
                    }
                }
                b = null;
            } catch (Throwable th) {
                if (localSocket != null) {
                    try {
                        localSocket.close();
                    } catch (IOException e4) {
                        if (com.ivona.tts.commonlib.a.c) {
                            e4.printStackTrace();
                        }
                    }
                }
                throw th;
            }
        }
    }

    public static String b(Context context) {
        return com.ivona.tts.commonlib.b.e() ? context.getPackageName() + "." + context.getApplicationInfo().uid + ".log" : context.getPackageName() + ".log";
    }
}
