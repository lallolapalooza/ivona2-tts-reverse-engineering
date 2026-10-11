package com.google.android.vending.expansion.downloader.impl;

import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

/* compiled from: DownloaderService.java */
/* loaded from: classes.dex */
class r extends BroadcastReceiver {
    final Service a;
    final /* synthetic */ DownloaderService b;

    r(DownloaderService downloaderService, Service service) {
        this.b = downloaderService;
        this.a = service;
    }

    @Override // android.content.BroadcastReceiver
    public void onReceive(Context context, Intent intent) {
        boolean z;
        boolean n;
        PendingIntent pendingIntent;
        this.b.g();
        z = this.b.n;
        if (z) {
            n = DownloaderService.n();
            if (!n) {
                Log.d("LVLDL", "InnerBroadcastReceiver Called");
                Intent intent2 = new Intent(context, this.a.getClass());
                pendingIntent = this.b.y;
                intent2.putExtra("EPI", pendingIntent);
                context.startService(intent2);
            }
        }
    }
}
