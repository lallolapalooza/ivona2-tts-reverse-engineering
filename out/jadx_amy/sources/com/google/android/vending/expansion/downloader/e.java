package com.google.android.vending.expansion.downloader;

import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.os.Messenger;

/* compiled from: DownloaderClientMarshaller.java */
/* loaded from: classes.dex */
class e implements o {
    private m b;
    private Class c;
    private boolean d;
    private Messenger e;
    private Context f;
    final Messenger a = new Messenger(new f(this));
    private ServiceConnection g = new g(this);

    public e(m mVar, Class cls) {
        this.b = null;
        this.b = mVar;
        this.c = cls;
    }

    @Override // com.google.android.vending.expansion.downloader.o
    public void a(Context context) {
        this.f = context;
        Intent intent = new Intent(context, (Class<?>) this.c);
        intent.putExtra("EMH", this.a);
        if (context.bindService(intent, this.g, 2)) {
            this.d = true;
        }
    }

    @Override // com.google.android.vending.expansion.downloader.o
    public void b(Context context) {
        if (this.d) {
            context.unbindService(this.g);
            this.d = false;
        }
        this.f = null;
    }

    @Override // com.google.android.vending.expansion.downloader.o
    public Messenger a() {
        return this.a;
    }
}
