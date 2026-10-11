package com.google.android.vending.a;

import android.util.Log;

/* compiled from: LicenseChecker.java */
/* loaded from: classes.dex */
class l implements Runnable {
    final /* synthetic */ j a;
    final /* synthetic */ k b;

    l(k kVar, j jVar) {
        this.b = kVar;
        this.a = jVar;
    }

    @Override // java.lang.Runnable
    public void run() {
        o oVar;
        o oVar2;
        Log.i("CL", "76720855");
        j jVar = this.b.a;
        oVar = this.b.b;
        jVar.b(oVar);
        j jVar2 = this.b.a;
        oVar2 = this.b.b;
        jVar2.a(oVar2);
    }
}
