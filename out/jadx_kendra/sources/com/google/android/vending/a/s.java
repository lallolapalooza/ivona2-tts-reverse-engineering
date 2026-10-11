package com.google.android.vending.a;

import android.content.SharedPreferences;
import android.util.Log;

/* compiled from: PreferenceObfuscator.java */
/* loaded from: classes.dex */
public class s {
    private final SharedPreferences a;
    private final q b;
    private SharedPreferences.Editor c = null;

    public s(SharedPreferences sharedPreferences, q qVar) {
        this.a = sharedPreferences;
        this.b = qVar;
    }

    public void a(String str, String str2) {
        if (this.c == null) {
            this.c = this.a.edit();
        }
        this.c.putString(str, this.b.a(str2, str));
    }

    public String b(String str, String str2) {
        String string = this.a.getString(str, null);
        if (string != null) {
            try {
                return this.b.b(string, str);
            } catch (u e) {
                Log.w("PreferenceObfuscator", "Validation error while reading preference: " + str);
                return str2;
            }
        }
        return str2;
    }

    public void a() {
        if (this.c != null) {
            this.c.commit();
            this.c = null;
        }
    }
}
