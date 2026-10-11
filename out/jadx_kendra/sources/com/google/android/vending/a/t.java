package com.google.android.vending.a;

import android.text.TextUtils;
import java.util.regex.Pattern;

/* compiled from: ResponseData.java */
/* loaded from: classes.dex */
public class t {
    public int a;
    public int b;
    public String c;
    public String d;
    public String e;
    public long f;
    public String g;

    public static t a(String str) {
        String substring;
        int indexOf = str.indexOf(58);
        if (-1 == indexOf) {
            substring = "";
        } else {
            String substring2 = str.substring(0, indexOf);
            substring = indexOf >= str.length() ? "" : str.substring(indexOf + 1);
            str = substring2;
        }
        String[] split = TextUtils.split(str, Pattern.quote("|"));
        if (split.length < 6) {
            throw new IllegalArgumentException("Wrong number of fields.");
        }
        t tVar = new t();
        tVar.g = substring;
        tVar.a = Integer.parseInt(split[0]);
        tVar.b = Integer.parseInt(split[1]);
        tVar.c = split[2];
        tVar.d = split[3];
        tVar.e = split[4];
        tVar.f = Long.parseLong(split[5]);
        return tVar;
    }

    public String toString() {
        return TextUtils.join("|", new Object[]{Integer.valueOf(this.a), Integer.valueOf(this.b), this.c, this.d, this.e, Long.valueOf(this.f)});
    }
}
