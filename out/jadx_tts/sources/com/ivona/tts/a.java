package com.ivona.tts;

import android.content.Context;
import android.content.Intent;

/* compiled from: WelcomeActivity.java */
/* loaded from: classes.dex */
class a {
    public String a;
    public String b;

    public a(String str, String str2) {
        this.a = str;
        this.b = str2;
    }

    public String a() {
        return "&" + this.b + "=1";
    }

    public boolean a(Context context) {
        Intent intent = new Intent();
        intent.setClassName(this.a, this.a + ".CheckVoiceInstalled");
        return a(intent, context);
    }

    private boolean a(Intent intent, Context context) {
        return context.getPackageManager().queryIntentActivities(intent, 0).size() > 0;
    }
}
