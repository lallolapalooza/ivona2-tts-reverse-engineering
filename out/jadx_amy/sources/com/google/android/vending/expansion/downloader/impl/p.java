package com.google.android.vending.expansion.downloader.impl;

/* compiled from: DownloadThread.java */
/* loaded from: classes.dex */
class p extends Throwable {
    public int a;
    final /* synthetic */ k b;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    public p(k kVar, int i, String str) {
        super(str);
        this.b = kVar;
        this.a = i;
    }

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    public p(k kVar, int i, String str, Throwable th) {
        super(str, th);
        this.b = kVar;
        this.a = i;
    }
}
