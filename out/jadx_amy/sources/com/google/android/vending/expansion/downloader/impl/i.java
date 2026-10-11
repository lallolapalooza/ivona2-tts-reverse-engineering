package com.google.android.vending.expansion.downloader.impl;

import android.R;
import android.app.Notification;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.os.Messenger;
import com.google.android.vending.expansion.downloader.DownloadProgressInfo;

/* compiled from: DownloadNotification.java */
/* loaded from: classes.dex */
public class i implements com.google.android.vending.expansion.downloader.m {
    static final int b = "DownloadNotification".hashCode();
    private final Context d;
    private final NotificationManager e;
    private String f;
    private com.google.android.vending.expansion.downloader.m g;
    private final CharSequence j;
    private String k;
    private PendingIntent l;
    private DownloadProgressInfo m;
    private int c = -1;
    final j a = g.a();
    private final Notification h = new Notification();
    private Notification i = this.h;

    public void a(PendingIntent pendingIntent) {
        this.l = pendingIntent;
    }

    public void a() {
        if (this.g != null) {
            this.g.a(this.c);
        }
    }

    @Override // com.google.android.vending.expansion.downloader.m
    public void a(int i) {
        int a;
        int i2;
        boolean z = false;
        if (this.g != null) {
            this.g.a(i);
        }
        if (i != this.c) {
            this.c = i;
            if (i != 1 && this.l != null) {
                switch (i) {
                    case 0:
                        a = com.google.android.vending.expansion.downloader.s.q;
                        i2 = 17301642;
                        break;
                    case 1:
                    case 6:
                    case 8:
                    case 9:
                    case 10:
                    case 11:
                    case 12:
                    case 13:
                    case 14:
                    default:
                        i2 = 17301642;
                        a = com.google.android.vending.expansion.downloader.l.a(i);
                        z = true;
                        break;
                    case 2:
                    case 3:
                        a = com.google.android.vending.expansion.downloader.l.a(i);
                        z = true;
                        i2 = 17301634;
                        break;
                    case 4:
                        a = com.google.android.vending.expansion.downloader.l.a(i);
                        i2 = 17301633;
                        z = true;
                        break;
                    case 5:
                    case 7:
                        a = com.google.android.vending.expansion.downloader.l.a(i);
                        i2 = 17301634;
                        break;
                    case 15:
                    case 16:
                    case 17:
                    case 18:
                    case 19:
                        a = com.google.android.vending.expansion.downloader.l.a(i);
                        i2 = 17301642;
                        break;
                }
                this.k = this.d.getString(a);
                this.f = this.j.toString();
                this.i.tickerText = ((Object) this.j) + ": " + this.k;
                this.i.icon = i2;
                this.i.setLatestEventInfo(this.d, this.f, this.k, this.l);
                if (z) {
                    this.i.flags |= 2;
                } else {
                    this.i.flags &= -3;
                    this.i.flags |= 16;
                }
                this.e.notify(b, this.i);
            }
        }
    }

    @Override // com.google.android.vending.expansion.downloader.m
    public void a(DownloadProgressInfo downloadProgressInfo) {
        this.m = downloadProgressInfo;
        if (this.g != null) {
            this.g.a(downloadProgressInfo);
        }
        if (downloadProgressInfo.a <= 0) {
            this.h.tickerText = this.f;
            this.h.icon = R.drawable.stat_sys_download;
            this.h.setLatestEventInfo(this.d, this.j, this.k, this.l);
            this.i = this.h;
        } else {
            this.a.b(downloadProgressInfo.b);
            this.a.a(downloadProgressInfo.a);
            this.a.a(R.drawable.stat_sys_download);
            this.a.a(this.l);
            this.a.b(((Object) this.j) + ": " + this.k);
            this.a.a(this.j);
            this.a.c(downloadProgressInfo.c);
            this.i = this.a.a(this.d);
        }
        this.e.notify(b, this.i);
    }

    public void b(Messenger messenger) {
        this.g = com.google.android.vending.expansion.downloader.c.a(messenger);
        if (this.m != null) {
            this.g.a(this.m);
        }
        if (this.c != -1) {
            this.g.a(this.c);
        }
    }

    i(Context context, CharSequence charSequence) {
        this.d = context;
        this.j = charSequence;
        this.e = (NotificationManager) this.d.getSystemService("notification");
    }

    @Override // com.google.android.vending.expansion.downloader.m
    public void a(Messenger messenger) {
    }
}
