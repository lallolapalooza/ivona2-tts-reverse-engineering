package com.google.android.vending.expansion.downloader.impl;

import android.app.Service;
import android.content.Intent;
import android.os.HandlerThread;
import android.os.IBinder;
import android.os.Looper;
import android.os.Message;
import android.util.Log;

/* loaded from: classes.dex */
public abstract class CustomIntentService extends Service {
    private String a;
    private boolean b;
    private volatile f c;
    private volatile Looper d;

    protected abstract void a(Intent intent);

    protected abstract boolean e();

    public CustomIntentService(String str) {
        this.a = str;
    }

    @Override // android.app.Service
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override // android.app.Service
    public void onCreate() {
        super.onCreate();
        HandlerThread handlerThread = new HandlerThread("IntentService[" + this.a + "]");
        handlerThread.start();
        this.d = handlerThread.getLooper();
        this.c = new f(this, this.d);
    }

    @Override // android.app.Service
    public void onDestroy() {
        Thread thread = this.d.getThread();
        if (thread != null && thread.isAlive()) {
            thread.interrupt();
        }
        this.d.quit();
        Log.d("CancellableIntentService", "onDestroy");
    }

    @Override // android.app.Service
    public void onStart(Intent intent, int i) {
        if (!this.c.hasMessages(-10)) {
            Message obtainMessage = this.c.obtainMessage();
            obtainMessage.arg1 = i;
            obtainMessage.obj = intent;
            obtainMessage.what = -10;
            this.c.sendMessage(obtainMessage);
        }
    }

    @Override // android.app.Service
    public int onStartCommand(Intent intent, int i, int i2) {
        onStart(intent, i2);
        return this.b ? 3 : 2;
    }
}
