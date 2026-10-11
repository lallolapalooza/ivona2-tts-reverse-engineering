package com.google.android.vending.expansion.downloader;

import android.content.ComponentName;
import android.content.ServiceConnection;
import android.os.IBinder;
import android.os.Messenger;

/* compiled from: DownloaderClientMarshaller.java */
/* loaded from: classes.dex */
class g implements ServiceConnection {
    final /* synthetic */ e a;

    g(e eVar) {
        this.a = eVar;
    }

    @Override // android.content.ServiceConnection
    public void onServiceConnected(ComponentName componentName, IBinder iBinder) {
        m mVar;
        Messenger messenger;
        this.a.e = new Messenger(iBinder);
        mVar = this.a.b;
        messenger = this.a.e;
        mVar.a(messenger);
    }

    @Override // android.content.ServiceConnection
    public void onServiceDisconnected(ComponentName componentName) {
        this.a.e = null;
    }
}
