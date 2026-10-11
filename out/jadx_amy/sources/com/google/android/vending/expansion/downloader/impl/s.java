package com.google.android.vending.expansion.downloader.impl;

import android.app.PendingIntent;
import android.content.Context;
import android.provider.Settings;

/* compiled from: DownloaderService.java */
/* loaded from: classes.dex */
class s implements Runnable {
    final Context a;
    final /* synthetic */ DownloaderService b;

    s(DownloaderService downloaderService, Context context, PendingIntent pendingIntent) {
        this.b = downloaderService;
        this.a = context;
        downloaderService.y = pendingIntent;
    }

    @Override // java.lang.Runnable
    public void run() {
        i iVar;
        DownloaderService.b(true);
        iVar = this.b.x;
        iVar.a(2);
        com.google.android.vending.a.b bVar = new com.google.android.vending.a.b(this.a, new com.google.android.vending.a.a(this.b.i(), this.a.getPackageName(), Settings.Secure.getString(this.a.getContentResolver(), "android_id")));
        bVar.a();
        new com.google.android.vending.a.j(this.a, bVar, this.b.h()).a(new t(this, bVar));
    }
}
