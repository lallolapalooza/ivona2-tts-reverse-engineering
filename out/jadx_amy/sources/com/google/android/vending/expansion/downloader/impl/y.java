package com.google.android.vending.expansion.downloader.impl;

import android.R;
import android.app.Notification;
import android.app.PendingIntent;
import android.content.Context;

/* compiled from: V14CustomNotification.java */
/* loaded from: classes.dex */
public class y implements j {
    CharSequence a;
    CharSequence b;
    int c;
    long d = -1;
    long e = -1;
    long f;
    PendingIntent g;

    @Override // com.google.android.vending.expansion.downloader.impl.j
    public void a(int i) {
        this.c = i;
    }

    @Override // com.google.android.vending.expansion.downloader.impl.j
    public void a(CharSequence charSequence) {
        this.a = charSequence;
    }

    @Override // com.google.android.vending.expansion.downloader.impl.j
    public void a(long j) {
        this.d = j;
    }

    @Override // com.google.android.vending.expansion.downloader.impl.j
    public void b(long j) {
        this.e = j;
    }

    @Override // com.google.android.vending.expansion.downloader.impl.j
    public Notification a(Context context) {
        Notification.Builder builder = new Notification.Builder(context);
        builder.setContentTitle(this.a);
        if (this.d > 0 && -1 != this.e) {
            builder.setProgress((int) (this.d >> 8), (int) (this.e >> 8), false);
        } else {
            builder.setProgress(0, 0, true);
        }
        builder.setContentText(com.google.android.vending.expansion.downloader.l.a(this.e, this.d));
        builder.setContentInfo(context.getString(com.google.android.vending.expansion.downloader.s.r, com.google.android.vending.expansion.downloader.l.a(this.f)));
        if (this.c != 0) {
            builder.setSmallIcon(this.c);
        } else {
            builder.setSmallIcon(R.drawable.stat_sys_download);
        }
        builder.setOngoing(true);
        builder.setTicker(this.b);
        builder.setContentIntent(this.g);
        builder.setOnlyAlertOnce(true);
        return builder.getNotification();
    }

    @Override // com.google.android.vending.expansion.downloader.impl.j
    public void a(PendingIntent pendingIntent) {
        this.g = pendingIntent;
    }

    @Override // com.google.android.vending.expansion.downloader.impl.j
    public void b(CharSequence charSequence) {
        this.b = charSequence;
    }

    @Override // com.google.android.vending.expansion.downloader.impl.j
    public void c(long j) {
        this.f = j;
    }
}
