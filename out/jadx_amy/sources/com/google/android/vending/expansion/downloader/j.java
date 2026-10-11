package com.google.android.vending.expansion.downloader;

import android.content.Context;
import android.os.Messenger;

/* compiled from: DownloaderServiceMarshaller.java */
/* loaded from: classes.dex */
class j implements o {
    final Messenger a = new Messenger(new k(this));
    private n b;

    public j(n nVar) {
        this.b = null;
        this.b = nVar;
    }

    @Override // com.google.android.vending.expansion.downloader.o
    public Messenger a() {
        return this.a;
    }

    @Override // com.google.android.vending.expansion.downloader.o
    public void a(Context context) {
    }

    @Override // com.google.android.vending.expansion.downloader.o
    public void b(Context context) {
    }
}
