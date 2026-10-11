package com.google.android.vending.expansion.downloader.impl;

import android.app.Notification;
import android.app.PendingIntent;
import android.content.Context;
import android.os.Build;
import android.widget.RemoteViews;

/* compiled from: V3CustomNotification.java */
/* loaded from: classes.dex */
public class z implements j {
    CharSequence a;
    CharSequence b;
    int c;
    long f;
    PendingIntent g;
    long d = -1;
    long e = -1;
    Notification h = new Notification();

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
        Notification notification = this.h;
        notification.icon = this.c;
        notification.flags |= 2;
        if (Build.VERSION.SDK_INT > 10) {
            notification.flags |= 8;
        }
        RemoteViews remoteViews = new RemoteViews(context.getPackageName(), com.google.android.vending.expansion.downloader.r.a);
        remoteViews.setTextViewText(com.google.android.vending.expansion.downloader.q.g, this.a);
        remoteViews.setViewVisibility(com.google.android.vending.expansion.downloader.q.b, 0);
        remoteViews.setTextViewText(com.google.android.vending.expansion.downloader.q.b, com.google.android.vending.expansion.downloader.l.a(this.e, this.d));
        remoteViews.setViewVisibility(com.google.android.vending.expansion.downloader.q.d, 0);
        remoteViews.setProgressBar(com.google.android.vending.expansion.downloader.q.c, (int) (this.d >> 8), (int) (this.e >> 8), this.d <= 0);
        remoteViews.setViewVisibility(com.google.android.vending.expansion.downloader.q.f, 0);
        remoteViews.setTextViewText(com.google.android.vending.expansion.downloader.q.f, context.getString(com.google.android.vending.expansion.downloader.s.r, com.google.android.vending.expansion.downloader.l.a(this.f)));
        remoteViews.setTextViewText(com.google.android.vending.expansion.downloader.q.e, com.google.android.vending.expansion.downloader.l.b(this.e, this.d));
        remoteViews.setImageViewResource(com.google.android.vending.expansion.downloader.q.a, this.c);
        notification.contentView = remoteViews;
        notification.contentIntent = this.g;
        return notification;
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
