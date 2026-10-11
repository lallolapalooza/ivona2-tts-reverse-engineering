package com.ivona.tts.commonlib.a;

/* compiled from: Request.java */
/* loaded from: classes.dex */
public class c {
    private static final byte[] a = {-47, 41, -124, -25, -8, 123, -57, -111, -61, 58, -80, -50, 9, 48, -13, 90, -13, 48, 17, 42, 104, 100, 20, -46, 14, 39, 43, 48, 115, -80, 1, 16, 21, -60, -75, -70, -95, -35, -40, -59, -10, -69, -121, 46, 34, -53, 23, -73, -104, 85, -69, 73, -27, 92, 109, 86, -28, -107, -58, 53, -36, 39, -32, 126};
    private d b;
    private byte[] c;
    private String d;

    public static c a(byte[] bArr) {
        a aVar = new a(bArr, a);
        return new c(d.a(aVar.b()), aVar.b(), aVar.c());
    }

    private c(d dVar, String str, byte[] bArr) {
        this.b = dVar;
        this.c = bArr;
        this.d = str;
    }

    public d a() {
        return this.b;
    }

    public byte[] b() {
        return this.c;
    }

    public String c() {
        return this.d;
    }
}
