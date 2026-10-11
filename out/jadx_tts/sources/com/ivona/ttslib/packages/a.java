package com.ivona.ttslib.packages;

import android.util.Log;
import java.security.InvalidParameterException;
import java.util.Locale;

/* compiled from: IvonaPackage.java */
/* loaded from: classes.dex */
public class a {
    private final int a;
    private final int b;
    private final String c;
    private final String d;
    private final Locale e;
    private final String f;
    private final b g;

    public static Locale a(String str) {
        String[] split = str.split("\\.");
        if (split.length < 7) {
            throw new InvalidParameterException("Failed to parse package name");
        }
        return new Locale(split[4], split[5], split[6]);
    }

    public static String b(String str) {
        String[] split = str.split("\\.");
        if (split.length < 6) {
            throw new InvalidParameterException("Failed to parse package name");
        }
        return split[4] + "-" + split[5];
    }

    public a(String str, String str2) {
        this.b = -1;
        this.f = str;
        this.e = a(str);
        this.d = str2;
        this.c = null;
        this.a = -1;
        this.g = b.UNKNOWN;
    }

    public a(String str, String str2, int i, String str3, int i2, b bVar) {
        this.b = i;
        this.f = str;
        this.e = a(str);
        this.d = str2;
        this.c = str3;
        this.a = i2;
        this.g = bVar;
    }

    public void a() {
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("IvonaPackage", "IP(" + this.f + "), ver:" + this.a + " apiVer:" + this.b + " fstate:" + this.g + " name:" + this.d + " SDK:" + this.c);
        }
    }

    public int b() {
        return this.a;
    }

    public String c() {
        return this.f;
    }

    public String d() {
        return this.d;
    }

    public Locale e() {
        return this.e;
    }

    public Locale f() {
        return new Locale(this.e.getISO3Language(), this.e.getISO3Country());
    }

    public b g() {
        return this.g;
    }

    public String h() {
        return this.e.getISO3Language() + "-" + this.e.getISO3Country();
    }
}
