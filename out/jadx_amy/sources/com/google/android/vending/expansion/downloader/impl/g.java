package com.google.android.vending.expansion.downloader.impl;

import android.os.Build;

/* compiled from: CustomNotificationFactory.java */
/* loaded from: classes.dex */
public class g {
    public static j a() {
        return Build.VERSION.SDK_INT > 13 ? new y() : new z();
    }
}
