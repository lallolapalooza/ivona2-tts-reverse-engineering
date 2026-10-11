package com.google.android.vending.expansion.downloader;

import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Messenger;
import com.google.android.vending.expansion.downloader.impl.DownloaderService;

/* compiled from: DownloaderClientMarshaller.java */
/* loaded from: classes.dex */
public class c {
    public static m a(Messenger messenger) {
        return new d(messenger);
    }

    public static o a(m mVar, Class cls) {
        return new e(mVar, cls);
    }

    public static int a(Context context, PendingIntent pendingIntent, Class cls) {
        return DownloaderService.a(context, pendingIntent, cls);
    }

    public static int a(Context context, Intent intent, Class cls) {
        return DownloaderService.a(context, intent, cls);
    }
}
