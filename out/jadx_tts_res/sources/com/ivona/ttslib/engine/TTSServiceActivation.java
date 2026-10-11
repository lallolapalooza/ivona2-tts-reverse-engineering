package com.ivona.ttslib.engine;

import android.app.Service;
import android.content.Intent;
import android.os.IBinder;
import android.util.Log;

/* loaded from: classes.dex */
public class TTSServiceActivation extends Service {
    private d a = null;
    private final IBinder b = new j(this);

    public d a() {
        return this.a;
    }

    @Override // android.app.Service
    public IBinder onBind(Intent intent) {
        return this.b;
    }

    @Override // android.app.Service
    public void onCreate() {
        super.onCreate();
        Log.i("TTSServiceActivation", "start");
        if (this.a == null) {
            this.a = d.a();
        }
        new com.ivona.ttslib.e(this).start();
    }

    @Override // android.app.Service
    public void onStart(Intent intent, int i) {
        super.onStart(intent, i);
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("TTSServiceActivation", "onStart");
        }
        if (this.a != null) {
            this.a.a(this);
            return;
        }
        throw new RuntimeException("Connector not created!");
    }

    @Override // android.app.Service
    public void onDestroy() {
        super.onDestroy();
        Log.i("TTSServiceActivation", "stop");
        if (this.a != null) {
            this.a.b();
        }
    }
}
