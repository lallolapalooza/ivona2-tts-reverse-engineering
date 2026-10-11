package com.google.android.vending.expansion.downloader;

import android.os.Bundle;
import android.os.Handler;
import android.os.Message;
import android.os.Messenger;
import android.os.RemoteException;

/* compiled from: DownloaderServiceMarshaller.java */
/* loaded from: classes.dex */
class i implements n {
    private Messenger a;

    private void a(int i, Bundle bundle) {
        Message obtain = Message.obtain((Handler) null, i);
        obtain.setData(bundle);
        try {
            this.a.send(obtain);
        } catch (RemoteException e) {
            e.printStackTrace();
        }
    }

    public i(Messenger messenger) {
        this.a = messenger;
    }

    @Override // com.google.android.vending.expansion.downloader.n
    public void a() {
        a(1, new Bundle());
    }

    @Override // com.google.android.vending.expansion.downloader.n
    public void b() {
        a(2, new Bundle());
    }

    @Override // com.google.android.vending.expansion.downloader.n
    public void a(int i) {
        Bundle bundle = new Bundle();
        bundle.putInt("flags", i);
        a(3, bundle);
    }

    @Override // com.google.android.vending.expansion.downloader.n
    public void c() {
        a(4, new Bundle());
    }

    @Override // com.google.android.vending.expansion.downloader.n
    public void d() {
        a(5, new Bundle());
    }

    @Override // com.google.android.vending.expansion.downloader.n
    public void a(Messenger messenger) {
        Bundle bundle = new Bundle(1);
        bundle.putParcelable("EMH", messenger);
        a(6, bundle);
    }
}
