package com.ivona.tts.commonlib.a;

/* compiled from: ResponseCode.java */
/* loaded from: classes.dex */
public enum f {
    VOICE_INSTALLED(1, "Voice is installed"),
    VOICE_NOT_INSTALLED(1, "Voice is not installed");

    protected int c;
    protected String d;

    f(int i, String str) {
        this.c = i;
        this.d = str;
    }

    @Override // java.lang.Enum
    public String toString() {
        return this.d;
    }
}
