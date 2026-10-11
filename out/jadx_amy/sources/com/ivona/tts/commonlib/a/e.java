package com.ivona.tts.commonlib.a;

/* compiled from: Response.java */
/* loaded from: classes.dex */
public class e {
    private f a;
    private byte[] b;
    private String c;

    public e(c cVar, f fVar) {
        this(cVar.b(), fVar, cVar.c());
    }

    private e(byte[] bArr, f fVar, String str) {
        this.a = fVar;
        this.b = bArr;
        this.c = str;
    }

    public byte[] a() {
        b bVar = new b(this.b);
        bVar.a(this.a.toString());
        bVar.a(this.c);
        return bVar.a();
    }
}
