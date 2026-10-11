package com.google.android.vending.a.a;

/* compiled from: Base64.java */
/* loaded from: classes.dex */
public class a {
    static final /* synthetic */ boolean a;
    private static final byte[] b;
    private static final byte[] c;
    private static final byte[] d;
    private static final byte[] e;

    static {
        a = !a.class.desiredAssertionStatus();
        b = new byte[]{65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 43, 47};
        c = new byte[]{65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 45, 95};
        d = new byte[]{-9, -9, -9, -9, -9, -9, -9, -9, -9, -5, -5, -9, -9, -5, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -5, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, 62, -9, -9, -9, 63, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, -9, -9, -9, -1, -9, -9, -9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -9, -9, -9, -9, -9, -9, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, -9, -9, -9, -9, -9};
        e = new byte[]{-9, -9, -9, -9, -9, -9, -9, -9, -9, -5, -5, -9, -9, -5, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -5, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, -9, 62, -9, -9, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, -9, -9, -9, -1, -9, -9, -9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -9, -9, -9, -9, 63, -9, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, -9, -9, -9, -9, -9};
    }

    private a() {
    }

    /* JADX WARN: Can't fix incorrect switch cases order, some code will duplicate */
    /* JADX WARN: Code restructure failed: missing block: B:12:0x0027, code lost:
    
        return r7;
     */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    private static byte[] a(byte[] r4, int r5, int r6, byte[] r7, int r8, byte[] r9) {
        /*
            r3 = 61
            r0 = 0
            if (r6 <= 0) goto L28
            r1 = r4[r5]
            int r1 = r1 << 24
            int r1 = r1 >>> 8
            r2 = r1
        Lc:
            r1 = 1
            if (r6 <= r1) goto L2a
            int r1 = r5 + 1
            r1 = r4[r1]
            int r1 = r1 << 24
            int r1 = r1 >>> 16
        L17:
            r1 = r1 | r2
            r2 = 2
            if (r6 <= r2) goto L23
            int r0 = r5 + 2
            r0 = r4[r0]
            int r0 = r0 << 24
            int r0 = r0 >>> 24
        L23:
            r0 = r0 | r1
            switch(r6) {
                case 1: goto L6e;
                case 2: goto L4f;
                case 3: goto L2c;
                default: goto L27;
            }
        L27:
            return r7
        L28:
            r2 = r0
            goto Lc
        L2a:
            r1 = r0
            goto L17
        L2c:
            int r1 = r0 >>> 18
            r1 = r9[r1]
            r7[r8] = r1
            int r1 = r8 + 1
            int r2 = r0 >>> 12
            r2 = r2 & 63
            r2 = r9[r2]
            r7[r1] = r2
            int r1 = r8 + 2
            int r2 = r0 >>> 6
            r2 = r2 & 63
            r2 = r9[r2]
            r7[r1] = r2
            int r1 = r8 + 3
            r0 = r0 & 63
            r0 = r9[r0]
            r7[r1] = r0
            goto L27
        L4f:
            int r1 = r0 >>> 18
            r1 = r9[r1]
            r7[r8] = r1
            int r1 = r8 + 1
            int r2 = r0 >>> 12
            r2 = r2 & 63
            r2 = r9[r2]
            r7[r1] = r2
            int r1 = r8 + 2
            int r0 = r0 >>> 6
            r0 = r0 & 63
            r0 = r9[r0]
            r7[r1] = r0
            int r0 = r8 + 3
            r7[r0] = r3
            goto L27
        L6e:
            int r1 = r0 >>> 18
            r1 = r9[r1]
            r7[r8] = r1
            int r1 = r8 + 1
            int r0 = r0 >>> 12
            r0 = r0 & 63
            r0 = r9[r0]
            r7[r1] = r0
            int r0 = r8 + 2
            r7[r0] = r3
            int r0 = r8 + 3
            r7[r0] = r3
            goto L27
        */
        throw new UnsupportedOperationException("Method not decompiled: com.google.android.vending.a.a.a.a(byte[], int, int, byte[], int, byte[]):byte[]");
    }

    public static String a(byte[] bArr) {
        return a(bArr, 0, bArr.length, b, true);
    }

    public static String a(byte[] bArr, int i, int i2, byte[] bArr2, boolean z) {
        byte[] a2 = a(bArr, i, i2, bArr2, Integer.MAX_VALUE);
        int length = a2.length;
        while (!z && length > 0 && a2[length - 1] == 61) {
            length--;
        }
        return new String(a2, 0, length);
    }

    public static byte[] a(byte[] bArr, int i, int i2, byte[] bArr2, int i3) {
        int i4 = ((i2 + 2) / 3) * 4;
        byte[] bArr3 = new byte[i4 + (i4 / i3)];
        int i5 = i2 - 2;
        int i6 = 0;
        int i7 = 0;
        int i8 = 0;
        while (i8 < i5) {
            int i9 = ((bArr[i8 + i] << 24) >>> 8) | ((bArr[(i8 + 1) + i] << 24) >>> 16) | ((bArr[(i8 + 2) + i] << 24) >>> 24);
            bArr3[i7] = bArr2[i9 >>> 18];
            bArr3[i7 + 1] = bArr2[(i9 >>> 12) & 63];
            bArr3[i7 + 2] = bArr2[(i9 >>> 6) & 63];
            bArr3[i7 + 3] = bArr2[i9 & 63];
            int i10 = i6 + 4;
            if (i10 == i3) {
                bArr3[i7 + 4] = 10;
                i7++;
                i10 = 0;
            }
            i8 += 3;
            i7 += 4;
            i6 = i10;
        }
        if (i8 < i2) {
            a(bArr, i8 + i, i2 - i8, bArr3, i7, bArr2);
            if (i6 + 4 == i3) {
                bArr3[i7 + 4] = 10;
                i7++;
            }
            i7 += 4;
        }
        if (a || i7 == bArr3.length) {
            return bArr3;
        }
        throw new AssertionError();
    }

    private static int a(byte[] bArr, int i, byte[] bArr2, int i2, byte[] bArr3) {
        if (bArr[i + 2] == 61) {
            bArr2[i2] = (byte) ((((bArr3[bArr[i]] << 24) >>> 6) | ((bArr3[bArr[i + 1]] << 24) >>> 12)) >>> 16);
            return 1;
        }
        if (bArr[i + 3] == 61) {
            int i3 = ((bArr3[bArr[i]] << 24) >>> 6) | ((bArr3[bArr[i + 1]] << 24) >>> 12) | ((bArr3[bArr[i + 2]] << 24) >>> 18);
            bArr2[i2] = (byte) (i3 >>> 16);
            bArr2[i2 + 1] = (byte) (i3 >>> 8);
            return 2;
        }
        int i4 = ((bArr3[bArr[i]] << 24) >>> 6) | ((bArr3[bArr[i + 1]] << 24) >>> 12) | ((bArr3[bArr[i + 2]] << 24) >>> 18) | ((bArr3[bArr[i + 3]] << 24) >>> 24);
        bArr2[i2] = (byte) (i4 >> 16);
        bArr2[i2 + 1] = (byte) (i4 >> 8);
        bArr2[i2 + 2] = (byte) i4;
        return 3;
    }

    public static byte[] a(String str) {
        byte[] bytes = str.getBytes();
        return a(bytes, 0, bytes.length);
    }

    public static byte[] a(byte[] bArr, int i, int i2) {
        return a(bArr, i, i2, d);
    }

    /* JADX WARN: Code restructure failed: missing block: B:33:0x00bd, code lost:
    
        if (r2 == 0) goto L38;
     */
    /* JADX WARN: Code restructure failed: missing block: B:34:0x00bf, code lost:
    
        if (r2 != 1) goto L37;
     */
    /* JADX WARN: Code restructure failed: missing block: B:36:0x00db, code lost:
    
        throw new com.google.android.vending.a.a.b("single trailing character at offset " + (r14 - 1));
     */
    /* JADX WARN: Code restructure failed: missing block: B:37:0x00dc, code lost:
    
        r0 = r2 + 1;
        r6[r2] = 61;
        r3 = r3 + a(r6, 0, r5, r3, r15);
     */
    /* JADX WARN: Code restructure failed: missing block: B:38:0x00e5, code lost:
    
        r0 = new byte[r3];
        java.lang.System.arraycopy(r5, 0, r0, 0, r3);
     */
    /* JADX WARN: Code restructure failed: missing block: B:39:0x00ea, code lost:
    
        return r0;
     */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static byte[] a(byte[] r12, int r13, int r14, byte[] r15) {
        /*
            Method dump skipped, instructions count: 240
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: com.google.android.vending.a.a.a.a(byte[], int, int, byte[]):byte[]");
    }
}
