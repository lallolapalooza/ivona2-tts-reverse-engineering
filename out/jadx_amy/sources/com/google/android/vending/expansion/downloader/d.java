package com.google.android.vending.expansion.downloader;

import android.os.Bundle;
import android.os.Handler;
import android.os.Message;
import android.os.Messenger;
import android.os.RemoteException;

/* compiled from: DownloaderClientMarshaller.java */
/* loaded from: classes.dex */
class d implements m {
    private Messenger a;

    @Override // com.google.android.vending.expansion.downloader.m
    public void a(int i) {
        Bundle bundle = new Bundle(1);
        bundle.putInt("newState", i);
        a(10, bundle);
    }

    @Override // com.google.android.vending.expansion.downloader.m
    public void a(DownloadProgressInfo downloadProgressInfo) {
        Bundle bundle = new Bundle(1);
        bundle.putParcelable("progress", downloadProgressInfo);
        a(11, bundle);
    }

    private void a(int i, Bundle bundle) {
        Message obtain = Message.obtain((Handler) null, i);
        obtain.setData(bundle);
        try {
            this.a.send(obtain);
        } catch (RemoteException e) {
            e.printStackTrace();
        }
    }

    public d(Messenger messenger) {
        this.a = messenger;
    }

    @Override // com.google.android.vending.expansion.downloader.m
    public void a(Messenger messenger) {
    }
}
