package com.google.android.vending.a;

import java.io.UnsupportedEncodingException;
import java.security.GeneralSecurityException;
import javax.crypto.BadPaddingException;
import javax.crypto.Cipher;
import javax.crypto.IllegalBlockSizeException;
import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.PBEKeySpec;
import javax.crypto.spec.SecretKeySpec;

/* compiled from: AESObfuscator.java */
/* loaded from: classes.dex */
public class a implements q {
    private static final byte[] a = {16, 74, 71, -80, 32, 101, -47, 72, 117, -14, 0, -29, 70, 65, -12, 74};
    private Cipher b;
    private Cipher c;

    public a(byte[] bArr, String str, String str2) {
        try {
            SecretKeySpec secretKeySpec = new SecretKeySpec(SecretKeyFactory.getInstance("PBEWITHSHAAND256BITAES-CBC-BC").generateSecret(new PBEKeySpec((str + str2).toCharArray(), bArr, 1024, 256)).getEncoded(), "AES");
            this.b = Cipher.getInstance("AES/CBC/PKCS5Padding");
            this.b.init(1, secretKeySpec, new IvParameterSpec(a));
            this.c = Cipher.getInstance("AES/CBC/PKCS5Padding");
            this.c.init(2, secretKeySpec, new IvParameterSpec(a));
        } catch (GeneralSecurityException e) {
            throw new RuntimeException("Invalid environment", e);
        }
    }

    @Override // com.google.android.vending.a.q
    public String a(String str, String str2) {
        if (str == null) {
            return null;
        }
        try {
            return com.google.android.vending.a.a.a.a(this.b.doFinal(("com.android.vending.licensing.AESObfuscator-1|" + str2 + str).getBytes("UTF-8")));
        } catch (UnsupportedEncodingException e) {
            throw new RuntimeException("Invalid environment", e);
        } catch (GeneralSecurityException e2) {
            throw new RuntimeException("Invalid environment", e2);
        }
    }

    @Override // com.google.android.vending.a.q
    public String b(String str, String str2) {
        if (str == null) {
            return null;
        }
        try {
            String str3 = new String(this.c.doFinal(com.google.android.vending.a.a.a.a(str)), "UTF-8");
            if (str3.indexOf("com.android.vending.licensing.AESObfuscator-1|" + str2) != 0) {
                throw new u("Header not found (invalid data or key):" + str);
            }
            return str3.substring("com.android.vending.licensing.AESObfuscator-1|".length() + str2.length(), str3.length());
        } catch (com.google.android.vending.a.a.b e) {
            throw new u(e.getMessage() + ":" + str);
        } catch (UnsupportedEncodingException e2) {
            throw new RuntimeException("Invalid environment", e2);
        } catch (BadPaddingException e3) {
            throw new u(e3.getMessage() + ":" + str);
        } catch (IllegalBlockSizeException e4) {
            throw new u(e4.getMessage() + ":" + str);
        }
    }
}
