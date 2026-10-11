package com.ivona.ttslib.engine;

import java.io.UnsupportedEncodingException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.security.InvalidParameterException;

/* compiled from: TTSMessageParser.java */
/* loaded from: classes.dex */
class i {
    private ByteBuffer a;
    private c b = null;

    public i(byte[] bArr) {
        this.a = null;
        if (bArr.length < 5) {
            throw new InvalidParameterException();
        }
        this.a = ByteBuffer.allocate(bArr.length);
        this.a.put(bArr);
        this.a.order(ByteOrder.nativeOrder());
    }

    public c a() {
        if (this.a == null) {
            throw new InvalidParameterException();
        }
        try {
            this.a.position(8);
            return g.a(b(), c(), d(), this.a.slice());
        } catch (UnsupportedEncodingException e) {
            return null;
        } catch (InvalidParameterException e2) {
            this.a.position(8);
            return g.a(b(), c(), null, this.a.remaining() > 0 ? this.a.slice() : null);
        }
    }

    public static ByteBuffer a(ByteBuffer byteBuffer, byte[] bArr) {
        ByteBuffer allocate = ByteBuffer.allocate(byteBuffer.capacity());
        byteBuffer.position(0);
        while (byteBuffer.remaining() > 0) {
            allocate.put((byte) (bArr[byteBuffer.position() % bArr.length] ^ byteBuffer.get()));
        }
        return allocate;
    }

    private int b() {
        return this.a.getInt(0);
    }

    private int c() {
        return this.a.getInt(4);
    }

    private String d() {
        if (this.a.get(8) != 2) {
            return null;
        }
        byte[] array = this.a.array();
        boolean z = false;
        int i = 9;
        while (true) {
            if (i >= array.length) {
                break;
            }
            if (array[i] != 0) {
                i++;
            } else {
                z = true;
                break;
            }
        }
        if (!z || i == 9) {
            throw new InvalidParameterException();
        }
        ByteBuffer allocate = ByteBuffer.allocate(i - 9);
        allocate.put(array, 9, i - 9);
        return new String(allocate.array(), "UTF-8");
    }
}
