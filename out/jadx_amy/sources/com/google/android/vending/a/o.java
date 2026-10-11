package com.google.android.vending.a;

import android.text.TextUtils;
import android.util.Log;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;
import java.security.PublicKey;
import java.security.Signature;
import java.security.SignatureException;

/* compiled from: LicenseValidator.java */
/* loaded from: classes.dex */
class o {
    private final r a;
    private final n b;
    private final int c;
    private final String d;
    private final String e;
    private final c f;

    o(r rVar, c cVar, n nVar, int i, String str, String str2) {
        this.a = rVar;
        this.f = cVar;
        this.b = nVar;
        this.c = i;
        this.d = str;
        this.e = str2;
    }

    public n a() {
        return this.b;
    }

    public int b() {
        return this.c;
    }

    public String c() {
        return this.d;
    }

    public void a(PublicKey publicKey, int i, String str, String str2) {
        String str3;
        t tVar = null;
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("LicenseValidator", "responseCode:" + i);
        }
        if (i == 0 || i == 1 || i == 2) {
            try {
                Signature signature = Signature.getInstance("SHA1withRSA");
                signature.initVerify(publicKey);
                signature.update(str.getBytes());
                if (!signature.verify(com.google.android.vending.a.a.a.a(str2))) {
                    Log.e("LicenseValidator", "Signature verification failed.");
                    d();
                    return;
                }
                try {
                    tVar = t.a(str);
                    if (tVar.a != i) {
                        Log.e("LicenseValidator", "Response codes don't match.");
                        d();
                        return;
                    }
                    if (tVar.b != this.c) {
                        Log.e("LicenseValidator", "Nonce doesn't match.");
                        d();
                        return;
                    }
                    if (!tVar.c.equals(this.d)) {
                        Log.e("LicenseValidator", "Package name doesn't match.");
                        d();
                        return;
                    } else if (!tVar.d.equals(this.e)) {
                        Log.e("LicenseValidator", "Version codes don't match.");
                        d();
                        return;
                    } else {
                        str3 = tVar.e;
                        if (TextUtils.isEmpty(str3)) {
                            Log.e("LicenseValidator", "User identifier is empty.");
                            d();
                            return;
                        }
                    }
                } catch (IllegalArgumentException e) {
                    Log.e("LicenseValidator", "Could not parse response.");
                    d();
                    return;
                }
            } catch (com.google.android.vending.a.a.b e2) {
                Log.e("LicenseValidator", "Could not Base64-decode signature.");
                d();
                return;
            } catch (InvalidKeyException e3) {
                a(5);
                return;
            } catch (NoSuchAlgorithmException e4) {
                throw new RuntimeException(e4);
            } catch (SignatureException e5) {
                throw new RuntimeException(e5);
            }
        } else {
            str3 = null;
        }
        switch (i) {
            case 0:
            case 2:
                a(this.f.a(str3), tVar);
                return;
            case 1:
                a(561, tVar);
                return;
            case 3:
                a(3);
                return;
            case 4:
                Log.w("LicenseValidator", "An error has occurred on the licensing server.");
                a(291, tVar);
                return;
            case 5:
                Log.w("LicenseValidator", "Licensing server is refusing to talk to this device, over quota.");
                a(291, tVar);
                return;
            case 257:
                Log.w("LicenseValidator", "Error contacting licensing server.");
                a(291, tVar);
                return;
            case 258:
                a(1);
                return;
            case 259:
                a(2);
                return;
            default:
                Log.e("LicenseValidator", "Unknown response code for license check.");
                d();
                return;
        }
    }

    private void a(int i, t tVar) {
        this.a.a(i, tVar);
        if (this.a.c()) {
            this.b.a(i);
        } else {
            this.b.b(i);
        }
    }

    private void a(int i) {
        this.b.c(i);
    }

    private void d() {
        this.b.b(561);
    }
}
