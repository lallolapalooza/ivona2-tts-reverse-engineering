package com.google.android.vending.expansion.downloader.impl;

import android.app.PendingIntent;
import android.content.Context;
import android.content.pm.PackageManager;
import android.util.Log;

/* compiled from: DownloaderService.java */
/* loaded from: classes.dex */
class t implements com.google.android.vending.a.n {
    final /* synthetic */ com.google.android.vending.a.b a;
    final /* synthetic */ s b;

    t(s sVar, com.google.android.vending.a.b bVar) {
        this.b = sVar;
        this.a = bVar;
    }

    @Override // com.google.android.vending.a.n
    public void a(int i) {
        int i2;
        PendingIntent pendingIntent;
        i iVar;
        i iVar2;
        int i3;
        try {
            int b = this.a.b();
            u a = u.a(this.b.a);
            if (b != 0) {
                int i4 = 0;
                i2 = 0;
                while (i4 < b) {
                    String b2 = this.a.b(i4);
                    if (b2 != null) {
                        h hVar = new h(i4, b2, this.b.a.getPackageName());
                        long c = this.a.c(i4);
                        if (this.b.b.a(a, i4, b2, c)) {
                            i3 = i2 | (-1);
                            hVar.a();
                            hVar.a = this.a.a(i4);
                            hVar.e = c;
                            hVar.h = i3;
                            a.c(hVar);
                        } else {
                            h a2 = a.a(hVar.c);
                            if (a2 == null) {
                                Log.d("LVLDL", "file " + hVar.c + " found. Not downloading.");
                                hVar.h = 200;
                                hVar.e = c;
                                hVar.f = c;
                                hVar.a = this.a.a(i4);
                                a.c(hVar);
                                i3 = i2;
                            } else if (a2.h != 200) {
                                a2.a = this.a.a(i4);
                                a.c(a2);
                                i3 = i2 | (-1);
                            }
                        }
                        i4++;
                        i2 = i3;
                    }
                    i3 = i2;
                    i4++;
                    i2 = i3;
                }
            } else {
                i2 = 0;
            }
            try {
                a.a(this.b.a.getPackageManager().getPackageInfo(this.b.a.getPackageName(), 0).versionCode, i2);
                Class<?> cls = this.b.b.getClass();
                Context context = this.b.a;
                pendingIntent = this.b.b.y;
                switch (DownloaderService.a(context, pendingIntent, cls)) {
                    case 0:
                        iVar2 = this.b.b.x;
                        iVar2.a(5);
                        break;
                    case 1:
                        Log.e("LVLDL", "In LVL checking loop!");
                        iVar = this.b.b.x;
                        iVar.a(15);
                        throw new RuntimeException("Error with LVL checking and database integrity");
                }
            } catch (PackageManager.NameNotFoundException e) {
                e.printStackTrace();
                throw new RuntimeException("Error with getting information from package name");
            }
        } finally {
            DownloaderService.b(false);
        }
    }

    @Override // com.google.android.vending.a.n
    public void b(int i) {
        i iVar;
        i iVar2;
        try {
            switch (i) {
                case 291:
                    iVar = this.b.b.x;
                    iVar.a(16);
                    break;
                case 561:
                    iVar2 = this.b.b.x;
                    iVar2.a(15);
                    break;
                default:
            }
        } finally {
            DownloaderService.b(false);
        }
    }

    @Override // com.google.android.vending.a.n
    public void c(int i) {
        i iVar;
        try {
            iVar = this.b.b.x;
            iVar.a(16);
        } finally {
            DownloaderService.b(false);
        }
    }
}
