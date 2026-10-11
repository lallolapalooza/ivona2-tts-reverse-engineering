package com.google.android.vending.expansion.downloader;

import android.os.Handler;
import android.os.Message;
import android.os.Messenger;

/* compiled from: DownloaderServiceMarshaller.java */
/* loaded from: classes.dex */
class k extends Handler {
    final /* synthetic */ j a;

    k(j jVar) {
        this.a = jVar;
    }

    @Override // android.os.Handler
    public void handleMessage(Message message) {
        n nVar;
        n nVar2;
        n nVar3;
        n nVar4;
        n nVar5;
        n nVar6;
        switch (message.what) {
            case 1:
                nVar6 = this.a.b;
                nVar6.a();
                break;
            case 2:
                nVar4 = this.a.b;
                nVar4.b();
                break;
            case 3:
                nVar3 = this.a.b;
                nVar3.a(message.getData().getInt("flags"));
                break;
            case 4:
                nVar5 = this.a.b;
                nVar5.c();
                break;
            case 5:
                nVar2 = this.a.b;
                nVar2.d();
                break;
            case 6:
                nVar = this.a.b;
                nVar.a((Messenger) message.getData().getParcelable("EMH"));
                break;
        }
    }
}
