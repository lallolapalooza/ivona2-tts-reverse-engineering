package com.ivona.tts.commonlib.a;

import java.io.ByteArrayInputStream;
import java.io.IOException;

/* compiled from: CryptedReader.java */
/* loaded from: classes.dex */
public class a {
    private ByteArrayInputStream a;

    public a(byte[] bArr, byte[] bArr2) {
        this.a = new ByteArrayInputStream(g.a(bArr, bArr2));
    }

    public int a() {
        byte[] bArr = new byte[4];
        if (this.a.read(bArr, 0, 4) != 4) {
            throw new IOException("Could not read from array");
        }
        return bArr[3] + (bArr[0] << 24) + (bArr[1] << 16) + (bArr[2] << 8);
    }

    public String b() {
        byte[] bArr = new byte[a()];
        this.a.read(bArr);
        return new String(bArr);
    }

    public byte[] c() {
        byte[] bArr = new byte[a()];
        this.a.read(bArr);
        return bArr;
    }
}
