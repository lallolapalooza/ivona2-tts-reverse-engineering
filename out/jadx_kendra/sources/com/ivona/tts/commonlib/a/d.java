package com.ivona.tts.commonlib.a;

/* compiled from: RequestCode.java */
/* loaded from: classes.dex */
public enum d {
    CHECK_VOICE_INSTALLED(1, "Check voice installed");

    protected int b;
    protected String c;

    d(int i, String str) {
        this.b = i;
        this.c = str;
    }

    @Override // java.lang.Enum
    public String toString() {
        return this.c;
    }

    public static final d a(String str) {
        d[] values = values();
        if (0 >= values.length) {
            return null;
        }
        d dVar = values[0];
        if (dVar.c.equals(str)) {
        }
        return dVar;
    }
}
