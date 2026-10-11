package com.ivona.ttslib.engine;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/* compiled from: TTSMessageCipher.java */
/* loaded from: classes.dex */
public class h {
    private static final byte[] e = {-91, 1, 110, 111, 81, 78, 77, 118, 47, -121, -7, -15, 101, -105, -109, -71, 51, 105, -10, -101, -120, 3, 14, 107, -52, -104, 119, -34, -119, 65, 25, 62, 113, 35, 75, -1, 48, -78, -61, 56, -77, Byte.MIN_VALUE, -116, 12, -46, -56, -111, -9, -94, -24, 44, 6, 34, 20, 40, 28, -36, -126, -80, -76, 69, 104, -87, -42};
    byte[] a = null;
    private c b;
    private byte[] c;
    private ByteBuffer d;

    public h(byte[] bArr) {
        this.b = null;
        this.c = null;
        this.d = null;
        this.d = ByteBuffer.allocate(bArr.length);
        this.d.put(bArr);
        this.d.order(ByteOrder.nativeOrder());
        this.b = null;
        this.c = null;
    }

    public ByteBuffer a() {
        if (this.d == null) {
            throw new NullPointerException();
        }
        ByteBuffer a = i.a(this.d, e);
        a.position(a.capacity() - 48);
        ByteBuffer slice = a.slice();
        this.c = new byte[slice.remaining()];
        slice.get(this.c);
        a.position(0);
        a.limit(a.capacity() - 48);
        return i.a(a.slice(), this.c);
    }
}
