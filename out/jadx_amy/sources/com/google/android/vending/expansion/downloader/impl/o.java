package com.google.android.vending.expansion.downloader.impl;

import java.io.FileOutputStream;

/* compiled from: DownloadThread.java */
/* loaded from: classes.dex */
class o {
    public String a;
    public FileOutputStream b;
    public int e;
    public String f;
    public String h;
    public boolean c = false;
    public int d = 0;
    public boolean g = false;

    public o(h hVar, DownloaderService downloaderService) {
        this.e = 0;
        this.e = hVar.l;
        this.h = hVar.a;
        this.a = downloaderService.a(hVar.c);
    }
}
