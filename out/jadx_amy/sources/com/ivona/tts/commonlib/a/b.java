package com.ivona.tts.commonlib.a;

import java.io.ByteArrayOutputStream;

/* compiled from: CryptedWriter.java */
/* loaded from: classes.dex */
public class b {
    private byte[] a;
    private ByteArrayOutputStream b = new ByteArrayOutputStream();

    public b(byte[] bArr) {
        this.a = bArr;
    }

    public void a(int i) {
        this.b.write(new byte[]{(byte) ((i >> 24) & 255), (byte) ((i >> 16) & 255), (byte) ((i >> 8) & 255), (byte) ((i >> 0) & 255)});
    }

    public void a(String str) {
        a(str.length());
        this.b.write(str.getBytes());
    }

    public byte[] a() {
        return g.a(this.b.toByteArray(), this.a);
    }
}
