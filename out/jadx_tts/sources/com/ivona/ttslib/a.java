package com.ivona.ttslib;

/* compiled from: CheckVoiceData.java */
/* loaded from: classes.dex */
/* synthetic */ class a {
    static final /* synthetic */ int[] a = new int[com.ivona.ttslib.packages.b.values().length];

    static {
        try {
            a[com.ivona.ttslib.packages.b.FULL_INSTALLED.ordinal()] = 1;
        } catch (NoSuchFieldError e) {
        }
        try {
            a[com.ivona.ttslib.packages.b.APK_INSTALLED.ordinal()] = 2;
        } catch (NoSuchFieldError e2) {
        }
        try {
            a[com.ivona.ttslib.packages.b.UNKNOWN.ordinal()] = 3;
        } catch (NoSuchFieldError e3) {
        }
    }
}
