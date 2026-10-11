package com.google.android.vending.a;

import android.content.Context;
import android.provider.Settings;
import android.util.Log;
import java.security.PublicKey;
import java.util.Date;
import java.util.Set;

/* compiled from: LicenseChecker.java */
/* loaded from: classes.dex */
class m implements Runnable {
    final /* synthetic */ int a;
    final /* synthetic */ String b;
    final /* synthetic */ String c;
    final /* synthetic */ k d;

    m(k kVar, int i, String str, String str2) {
        this.d = kVar;
        this.a = i;
        this.b = str;
        this.c = str2;
    }

    @Override // java.lang.Runnable
    public void run() {
        Set set;
        o oVar;
        boolean z;
        Context context;
        o oVar2;
        PublicKey publicKey;
        o oVar3;
        boolean z2 = true;
        Log.i("CL", "93109208");
        set = this.d.a.j;
        oVar = this.d.b;
        if (set.contains(oVar)) {
            this.d.b();
            oVar2 = this.d.b;
            publicKey = this.d.a.d;
            oVar2.a(publicKey, this.a, this.b, this.c);
            j jVar = this.d.a;
            oVar3 = this.d.b;
            jVar.a(oVar3);
        }
        z = j.b;
        if (z) {
            String str = null;
            switch (this.a) {
                case 257:
                    str = "ERROR_CONTACTING_SERVER";
                    break;
                case 258:
                    str = "ERROR_INVALID_PACKAGE_NAME";
                    break;
                case 259:
                    str = "ERROR_NON_MATCHING_UID";
                    break;
                default:
                    z2 = false;
                    break;
            }
            if (z2) {
                context = this.d.a.e;
                String string = Settings.Secure.getString(context.getContentResolver(), "android_id");
                Date date = new Date();
                Log.d("CL", "Server Failure: " + str);
                Log.d("CL", "Android ID: " + string);
                Log.d("CL", "Time: " + date.toGMTString());
            }
        }
    }
}
