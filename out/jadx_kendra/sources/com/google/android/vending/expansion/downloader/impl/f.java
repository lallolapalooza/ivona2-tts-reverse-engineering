package com.google.android.vending.expansion.downloader.impl;

import android.content.Intent;
import android.os.Handler;
import android.os.Looper;
import android.os.Message;
import android.util.Log;

/* compiled from: CustomIntentService.java */
/* loaded from: classes.dex */
final class f extends Handler {
    final /* synthetic */ CustomIntentService a;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    public f(CustomIntentService customIntentService, Looper looper) {
        super(looper);
        this.a = customIntentService;
    }

    @Override // android.os.Handler
    public void handleMessage(Message message) {
        this.a.a((Intent) message.obj);
        if (this.a.e()) {
            Log.d("CancellableIntentService", "stopSelf");
            this.a.stopSelf(message.arg1);
            Log.d("CancellableIntentService", "afterStopSelf");
        }
    }
}
