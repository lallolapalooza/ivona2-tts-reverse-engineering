package com.google.android.vending.a;

import android.os.Handler;
import android.util.Log;

/* compiled from: LicenseChecker.java */
/* loaded from: classes.dex */
class k extends e {
    final /* synthetic */ j a;
    private final o b;
    private final Runnable c;

    public k(j jVar, o oVar) {
        this.a = jVar;
        this.b = oVar;
        this.c = new l(this, jVar);
        a();
    }

    @Override // com.google.android.vending.a.d
    public void a(int i, String str, String str2) {
        Handler handler;
        handler = this.a.g;
        handler.post(new m(this, i, str, str2));
    }

    private void a() {
        Handler handler;
        Log.i("CL", "06244623");
        handler = this.a.g;
        handler.postDelayed(this.c, 10000L);
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void b() {
        Handler handler;
        Log.i("CL", "96681658");
        handler = this.a.g;
        handler.removeCallbacks(this.c);
    }
}
