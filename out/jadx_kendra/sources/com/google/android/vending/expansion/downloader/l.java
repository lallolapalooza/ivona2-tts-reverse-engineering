package com.google.android.vending.expansion.downloader;

import android.content.Context;
import android.os.Environment;
import android.os.StatFs;
import android.os.SystemClock;
import java.io.File;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.Random;
import java.util.TimeZone;
import java.util.regex.Pattern;

/* compiled from: Helpers.java */
/* loaded from: classes.dex */
public class l {
    public static Random a = new Random(SystemClock.uptimeMillis());
    private static final Pattern b = Pattern.compile("attachment;\\s*filename\\s*=\\s*\"([^\"]*)\"");

    public static File a(String str) {
        File downloadCacheDirectory = Environment.getDownloadCacheDirectory();
        if (!str.startsWith(downloadCacheDirectory.getPath())) {
            downloadCacheDirectory = Environment.getExternalStorageDirectory();
            if (!str.startsWith(downloadCacheDirectory.getPath())) {
                throw new IllegalArgumentException("Cannot determine filesystem root for " + str);
            }
        }
        return downloadCacheDirectory;
    }

    public static boolean a() {
        return Environment.getExternalStorageState().equals("mounted");
    }

    public static long a(File file) {
        StatFs statFs = new StatFs(file.getPath());
        return statFs.getBlockSize() * (statFs.getAvailableBlocks() - 4);
    }

    public static boolean b(String str) {
        String replaceFirst = str.replaceFirst("/+", "/");
        return replaceFirst.startsWith(Environment.getDownloadCacheDirectory().toString()) || replaceFirst.startsWith(Environment.getExternalStorageDirectory().toString());
    }

    public static String a(long j, long j2) {
        return j2 == 0 ? "" : String.format("%.2f", Float.valueOf(j / 1048576.0f)) + "MB /" + String.format("%.2f", Float.valueOf(j2 / 1048576.0f)) + "MB";
    }

    public static String b(long j, long j2) {
        return j2 == 0 ? "" : Long.toString((100 * j) / j2) + "%";
    }

    public static String a(long j) {
        SimpleDateFormat simpleDateFormat;
        if (j > 3600000) {
            simpleDateFormat = new SimpleDateFormat("HH:mm", Locale.getDefault());
        } else {
            simpleDateFormat = new SimpleDateFormat("mm:ss", Locale.getDefault());
        }
        return simpleDateFormat.format(new Date(j - TimeZone.getDefault().getRawOffset()));
    }

    public static String a(Context context, String str) {
        return a(context) + File.separator + str;
    }

    public static String a(Context context) {
        return Environment.getExternalStorageDirectory().toString() + a.a + context.getPackageName();
    }

    public static boolean a(Context context, String str, long j, boolean z) {
        File file = new File(a(context, str));
        if (file.exists()) {
            if (file.length() == j) {
                return true;
            }
            if (z) {
                file.delete();
            }
        }
        return false;
    }

    public static int a(int i) {
        switch (i) {
            case 1:
                return s.i;
            case 2:
                return s.h;
            case 3:
                return s.b;
            case 4:
                return s.c;
            case 5:
                return s.a;
            case 6:
                return s.l;
            case 7:
                return s.j;
            case 8:
                return s.o;
            case 9:
                return s.p;
            case 10:
                return s.o;
            case 11:
                return s.p;
            case 12:
                return s.m;
            case 13:
                return s.k;
            case 14:
                return s.n;
            case 15:
                return s.g;
            case 16:
                return s.e;
            case 17:
                return s.f;
            case 18:
                return s.d;
            default:
                return s.q;
        }
    }
}
