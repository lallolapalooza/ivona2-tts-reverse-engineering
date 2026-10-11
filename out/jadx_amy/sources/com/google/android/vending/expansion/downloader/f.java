package com.google.android.vending.expansion.downloader;

import android.content.Context;
import android.os.Bundle;
import android.os.Handler;
import android.os.Message;
import android.os.Messenger;

/* compiled from: DownloaderClientMarshaller.java */
/* loaded from: classes.dex */
class f extends Handler {
    final /* synthetic */ e a;

    f(e eVar) {
        this.a = eVar;
    }

    @Override // android.os.Handler
    public void handleMessage(Message message) {
        m mVar;
        m mVar2;
        Context context;
        Context context2;
        m mVar3;
        switch (message.what) {
            case 10:
                mVar2 = this.a.b;
                mVar2.a(message.getData().getInt("newState"));
                break;
            case 11:
                Bundle data = message.getData();
                context = this.a.f;
                if (context != null) {
                    context2 = this.a.f;
                    data.setClassLoader(context2.getClassLoader());
                    DownloadProgressInfo downloadProgressInfo = (DownloadProgressInfo) message.getData().getParcelable("progress");
                    mVar3 = this.a.b;
                    mVar3.a(downloadProgressInfo);
                    break;
                }
                break;
            case 12:
                mVar = this.a.b;
                mVar.a((Messenger) message.getData().getParcelable("EMH"));
                break;
        }
    }
}
