package com.ivona.ttslib.engine;

import java.nio.ByteBuffer;

/* compiled from: TTSMessage.java */
/* loaded from: classes.dex */
public class g implements c {
    private int a;
    private int b;
    private int c;
    private String d;
    private ByteBuffer e;

    public static c a(int i, int i2, String str, ByteBuffer byteBuffer) {
        return new g(i, i2, str, byteBuffer);
    }

    private g(int i, int i2, String str, ByteBuffer byteBuffer) {
        this.a = -1;
        this.b = -1;
        this.c = -1;
        this.d = null;
        this.e = null;
        this.a = i;
        this.b = i2;
        this.d = str;
        this.e = byteBuffer;
        if (i == 1 && i2 == 1 && str != null) {
            if (str.startsWith("Voice library version mismatch")) {
                this.c = 1;
            }
            if (str.startsWith("Voice not allowed by the certificate")) {
                this.c = 2;
            }
        }
    }

    @Override // com.ivona.ttslib.engine.c
    public int a() {
        return this.a;
    }

    @Override // com.ivona.ttslib.engine.c
    public int b() {
        return this.c;
    }
}
