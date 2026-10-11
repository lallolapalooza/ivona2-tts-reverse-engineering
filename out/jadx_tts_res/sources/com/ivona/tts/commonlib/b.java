package com.ivona.tts.commonlib;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import android.util.Log;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Formatter;

/* compiled from: VUtils.java */
/* loaded from: classes.dex */
public class b {
    public static PackageInfo a(Context context, String str) {
        try {
            return context.getPackageManager().getPackageInfo(str, 0);
        } catch (PackageManager.NameNotFoundException e) {
            if (a.c) {
                Log.e("VUtils", "Error reading package info.");
                return null;
            }
            return null;
        }
    }

    public static PackageInfo a(Context context) {
        try {
            return context.getPackageManager().getPackageInfo("com.ivona.tts", 0);
        } catch (PackageManager.NameNotFoundException e) {
            Log.e("VUtils", "Error reading package info.");
            return null;
        }
    }

    public static int a() {
        return Build.VERSION.SDK_INT;
    }

    public static boolean b() {
        return Build.VERSION.SDK_INT < 8;
    }

    public static boolean c() {
        return Build.VERSION.SDK_INT >= 15;
    }

    public static boolean d() {
        return Build.VERSION.SDK_INT == 14;
    }

    public static boolean e() {
        return Build.VERSION.SDK_INT >= 14;
    }

    public static boolean f() {
        return Build.VERSION.SDK_INT >= 11 && Build.VERSION.SDK_INT <= 13;
    }

    public static boolean a(Context context, Intent intent) {
        return intent != null && context.getPackageManager().queryIntentActivities(intent, 0).size() > 0;
    }

    public static boolean b(Context context, Intent intent) {
        if (!a(context, intent)) {
            return false;
        }
        context.startActivity(intent);
        return true;
    }

    public static boolean g() {
        return Build.MANUFACTURER.compareToIgnoreCase("HTC") == 0 && Build.MODEL.compareToIgnoreCase("HTC One X") == 0;
    }

    public static String a(String str) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(("069f69d25c5923cb2f72b5aacd143a19490a115b0675f0d52043c3fd9efbd4a4" + str).getBytes());
            Formatter formatter = new Formatter();
            for (byte b : digest) {
                formatter.format("%02x", Byte.valueOf(b));
            }
            String formatter2 = formatter.toString();
            formatter.close();
            if (a.c) {
                Log.d("VUtils", "sha256(salt + " + str + ") = " + formatter2);
                return formatter2;
            }
            return formatter2;
        } catch (NoSuchAlgorithmException e) {
            e.printStackTrace();
            return "";
        }
    }

    /* JADX WARN: Removed duplicated region for block: B:10:0x0029  */
    /* JADX WARN: Removed duplicated region for block: B:12:0x002f  */
    /* JADX WARN: Removed duplicated region for block: B:15:0x003d  */
    /* JADX WARN: Removed duplicated region for block: B:18:0x0047  */
    /* JADX WARN: Removed duplicated region for block: B:20:0x004b  */
    /* JADX WARN: Removed duplicated region for block: B:24:0x006b  */
    /* JADX WARN: Removed duplicated region for block: B:25:0x006e  */
    /* JADX WARN: Removed duplicated region for block: B:26:0x0070  */
    /* JADX WARN: Removed duplicated region for block: B:7:0x001c  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static java.lang.String b(android.content.Context r5) {
        /*
            r2 = 0
            int r0 = a()
            r1 = 5
            if (r0 < r1) goto L72
            android.accounts.AccountManager r0 = android.accounts.AccountManager.get(r5)
            java.lang.String r1 = "com.google"
            android.accounts.Account[] r0 = r0.getAccountsByType(r1)
            int r1 = r0.length
            if (r1 <= 0) goto L72
            r1 = 0
            r0 = r0[r1]
            java.lang.String r0 = r0.name
        L1a:
            if (r0 != 0) goto L70
            java.lang.String r0 = ""
            r1 = r0
        L1f:
            java.lang.String r0 = "phone"
            java.lang.Object r0 = r5.getSystemService(r0)
            android.telephony.TelephonyManager r0 = (android.telephony.TelephonyManager) r0
            if (r0 == 0) goto L6e
            java.lang.String r0 = r0.getDeviceId()
        L2d:
            if (r0 != 0) goto L31
            java.lang.String r0 = ""
        L31:
            android.content.ContentResolver r2 = r5.getContentResolver()
            java.lang.String r3 = "android_id"
            java.lang.String r2 = android.provider.Settings.Secure.getString(r2, r3)
            if (r2 != 0) goto L3f
            java.lang.String r2 = ""
        L3f:
            int r3 = a()
            r4 = 9
            if (r3 < r4) goto L6b
            java.lang.String r3 = android.os.Build.SERIAL
        L49:
            if (r3 != 0) goto L4d
            java.lang.String r3 = ""
        L4d:
            java.lang.StringBuilder r4 = new java.lang.StringBuilder
            r4.<init>()
            java.lang.StringBuilder r1 = r4.append(r1)
            java.lang.StringBuilder r1 = r1.append(r2)
            java.lang.StringBuilder r1 = r1.append(r3)
            java.lang.StringBuilder r0 = r1.append(r0)
            java.lang.String r0 = r0.toString()
            java.lang.String r0 = a(r0)
            return r0
        L6b:
            java.lang.String r3 = ""
            goto L49
        L6e:
            r0 = r2
            goto L2d
        L70:
            r1 = r0
            goto L1f
        L72:
            r0 = r2
            goto L1a
        */
        throw new UnsupportedOperationException("Method not decompiled: com.ivona.tts.commonlib.b.b(android.content.Context):java.lang.String");
    }
}
