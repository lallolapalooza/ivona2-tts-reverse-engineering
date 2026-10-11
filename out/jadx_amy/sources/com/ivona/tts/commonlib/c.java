package com.ivona.tts.commonlib;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.util.Log;

/* compiled from: VUtils.java */
/* loaded from: classes.dex */
public class c {
    public static PackageInfo a(Context context) {
        try {
            return context.getPackageManager().getPackageInfo(context.getPackageName(), 0);
        } catch (PackageManager.NameNotFoundException e) {
            if (a.c) {
                Log.e("VUtils", "Error reading package info.");
                return null;
            }
            return null;
        }
    }

    public static PackageInfo b(Context context) {
        try {
            return context.getPackageManager().getPackageInfo("com.ivona.tts", 0);
        } catch (PackageManager.NameNotFoundException e) {
            Log.e("VUtils", "Error reading package info.");
            return null;
        }
    }

    public static boolean a(Context context, Intent intent) {
        return intent != null && context.getPackageManager().queryIntentActivities(intent, 0).size() > 0;
    }

    public static boolean b(Context context, Intent intent) {
        return intent != null && context.getPackageManager().queryIntentServices(intent, 0).size() > 0;
    }

    public static boolean a(Context context, int i, String str) {
        String[] packagesForUid = context.getPackageManager().getPackagesForUid(i);
        if (packagesForUid == null || packagesForUid.length == 0) {
            return false;
        }
        for (String str2 : packagesForUid) {
            if (str2.equals(str)) {
                return true;
            }
        }
        return false;
    }
}
