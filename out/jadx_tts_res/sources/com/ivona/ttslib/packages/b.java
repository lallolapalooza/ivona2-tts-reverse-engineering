package com.ivona.ttslib.packages;

/* compiled from: IvonaPackage.java */
/* loaded from: classes.dex */
public enum b {
    UNKNOWN(-1),
    FILES_WITHOUT_APK(2),
    APK_INSTALLED(1),
    FULL_INSTALLED(0);

    private int e;

    b(int i) {
        this.e = i;
    }

    public static b a(int i) {
        for (b bVar : values()) {
            if (bVar.e == i) {
                return bVar;
            }
        }
        return null;
    }
}
