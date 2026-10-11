package com.ivona.ttslib.packages;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.Environment;
import android.os.Process;
import android.text.TextUtils;
import android.util.Log;
import com.ivona.ttslib.config.ConfigXMLDataSet;
import com.ivona.ttslib.ics.NativeIVONAEngine;
import java.io.BufferedOutputStream;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.security.InvalidParameterException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.locks.ReentrantLock;

/* loaded from: classes.dex */
public class IvonaPackagesInfo {
    public static final String a;
    private final Context b;
    private Map c;
    private final ReentrantLock d = new ReentrantLock();

    private static native String[] getVoicesApiVersion(String[] strArr);

    private static native int isoemn();

    static {
        System.loadLibrary("ttsivona");
        a = Environment.getExternalStorageDirectory() + "/ivona";
    }

    public IvonaPackagesInfo(Context context) {
        this.b = context;
    }

    public Map a() {
        if (this.c == null) {
            this.c = new HashMap(c.a());
            try {
                BufferedReader bufferedReader = new BufferedReader(new InputStreamReader(this.b.openFileInput("ivona_pkgs.csv")));
                if (com.ivona.tts.commonlib.a.c) {
                    Log.d("IvonaPackagesInfo", "---- reading CSV");
                }
                while (true) {
                    String readLine = bufferedReader.readLine();
                    if (readLine == null) {
                        break;
                    }
                    String[] split = readLine.split(";");
                    if (split.length >= 6) {
                        a aVar = new a(split[0], split[4], Integer.parseInt(split[2]), split[5], Integer.parseInt(split[1]), b.a(Integer.parseInt(split[3])));
                        aVar.a();
                        this.c.put(split[0], aVar);
                    }
                }
            } catch (FileNotFoundException e) {
                if (com.ivona.tts.commonlib.a.c) {
                    Log.e("IvonaPackagesInfo", "Failed to read packages infromation file.");
                    e.printStackTrace();
                }
            } catch (IOException e2) {
                if (com.ivona.tts.commonlib.a.c) {
                    Log.e("IvonaPackagesInfo", "Failed to read packages infromation file.");
                    e2.printStackTrace();
                }
            }
        }
        return this.c;
    }

    public static boolean b() {
        return isoemn() == 1;
    }

    public boolean c() {
        boolean z;
        BufferedOutputStream bufferedOutputStream = null;
        try {
            if (com.ivona.tts.commonlib.a.c) {
                Log.d("IvonaPackagesInfo", "Rebuild");
            }
            long currentTimeMillis = System.currentTimeMillis();
            PackageManager packageManager = this.b.getPackageManager();
            String[] packagesForUid = packageManager.getPackagesForUid(Process.myUid());
            if (this.c != null) {
                int length = packagesForUid.length;
                int i = 0;
                while (true) {
                    if (i >= length) {
                        z = false;
                        break;
                    }
                    String str = packagesForUid[i];
                    if (!this.c.containsKey(str)) {
                        z = true;
                        break;
                    }
                    try {
                    } catch (PackageManager.NameNotFoundException e) {
                        if (com.ivona.tts.commonlib.a.c) {
                            Log.e("IvonaPackagesInfo", "NameNotFoundException on checking version:" + str);
                        }
                    }
                    if (packageManager.getPackageInfo(str, 0).versionCode != ((a) this.c.get(str)).b()) {
                        z = true;
                        break;
                    }
                    i++;
                }
                if (packagesForUid.length != this.c.size()) {
                    z = true;
                }
                if (!z) {
                    if (com.ivona.tts.commonlib.a.c) {
                        Log.d("IvonaPackagesInfo", "Rebuild - nothing was changed");
                    }
                    if (0 != 0) {
                        try {
                            bufferedOutputStream.close();
                        } catch (IOException e2) {
                            e2.printStackTrace();
                        }
                    }
                    if (!this.d.isLocked()) {
                        return true;
                    }
                    this.d.unlock();
                    return true;
                }
            }
            this.d.lock();
            try {
                FileOutputStream openFileOutput = this.b.openFileOutput("ivona_pkgs.csv", 1);
                NativeIVONAEngine.setEnvRuntime(new File(this.b.getApplicationInfo().dataDir).getParent() + "/", Environment.getExternalStorageDirectory().getAbsolutePath() + "/");
                String[] voicesApiVersion = getVoicesApiVersion(packagesForUid);
                BufferedOutputStream bufferedOutputStream2 = new BufferedOutputStream(openFileOutput);
                try {
                    this.c = new HashMap(c.a());
                    try {
                        bufferedOutputStream2.write((Long.toString(currentTimeMillis) + "\n").getBytes());
                        int i2 = 0;
                        while (true) {
                            int i3 = i2;
                            if (i3 >= packagesForUid.length) {
                                break;
                            }
                            if (!TextUtils.isEmpty(voicesApiVersion[i3])) {
                                String[] split = voicesApiVersion[i3].split(";");
                                if (com.ivona.tts.commonlib.a.c) {
                                    Log.d("IvonaPackagesInfo", "pkgsInstalled[" + i3 + "]:'" + packagesForUid[i3] + "'");
                                }
                                try {
                                    PackageInfo packageInfo = packageManager.getPackageInfo(packagesForUid[i3], 0);
                                    this.c.put(packagesForUid[i3], new a(packagesForUid[i3], split[2], Integer.parseInt(split[0]), split[3], packageInfo.versionCode, b.a(Integer.parseInt(split[1]))));
                                    bufferedOutputStream2.write((packagesForUid[i3] + ";" + packageInfo.versionCode + ";" + voicesApiVersion[i3] + "\n").getBytes());
                                } catch (PackageManager.NameNotFoundException e3) {
                                    if (com.ivona.tts.commonlib.a.c) {
                                        Log.e("IvonaPackagesInfo", "NameNotFoundException:" + packagesForUid[i3]);
                                    }
                                }
                            }
                            i2 = i3 + 1;
                        }
                        if (bufferedOutputStream2 != null) {
                            try {
                                bufferedOutputStream2.close();
                            } catch (IOException e4) {
                                e4.printStackTrace();
                            }
                        }
                        if (this.d.isLocked()) {
                            this.d.unlock();
                        }
                        if (com.ivona.tts.commonlib.a.c) {
                            Log.d("IvonaPackagesInfo", "Rebuild - done");
                        }
                        return true;
                    } catch (IOException e5) {
                        e5.printStackTrace();
                        if (bufferedOutputStream2 != null) {
                            try {
                                bufferedOutputStream2.close();
                            } catch (IOException e6) {
                                e6.printStackTrace();
                            }
                        }
                        if (!this.d.isLocked()) {
                            return false;
                        }
                        this.d.unlock();
                        return false;
                    } catch (InvalidParameterException e7) {
                        e7.printStackTrace();
                        if (bufferedOutputStream2 != null) {
                            try {
                                bufferedOutputStream2.close();
                            } catch (IOException e8) {
                                e8.printStackTrace();
                            }
                        }
                        if (!this.d.isLocked()) {
                            return false;
                        }
                        this.d.unlock();
                        return false;
                    }
                } catch (Throwable th) {
                    th = th;
                    bufferedOutputStream = bufferedOutputStream2;
                    if (bufferedOutputStream != null) {
                        try {
                            bufferedOutputStream.close();
                        } catch (IOException e9) {
                            e9.printStackTrace();
                        }
                    }
                    if (this.d.isLocked()) {
                        this.d.unlock();
                    }
                    throw th;
                }
            } catch (FileNotFoundException e10) {
                e10.printStackTrace();
                if (0 != 0) {
                    try {
                        bufferedOutputStream.close();
                    } catch (IOException e11) {
                        e11.printStackTrace();
                    }
                }
                if (!this.d.isLocked()) {
                    return false;
                }
                this.d.unlock();
                return false;
            }
        } catch (Throwable th2) {
            th = th2;
        }
    }

    public int a(String str, String str2, String str3, ConfigXMLDataSet configXMLDataSet) {
        int i;
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("IvonaPackagesInfo", "getVoiceByLocale: required - " + str + "/" + (str2 == null ? "null" : str2) + "/" + (str3 == null ? "null" : str3));
        }
        if (this.c == null) {
            return -2;
        }
        Iterator it = this.c.values().iterator();
        int i2 = -2;
        while (it.hasNext()) {
            Locale e = ((a) it.next()).e();
            if (TextUtils.isEmpty(str) || !e.getISO3Language().equals(str)) {
                i = -2;
            } else {
                i = 0;
                if (!TextUtils.isEmpty(str2) && e.getISO3Country().equals(str2)) {
                    i = 1;
                    if (!TextUtils.isEmpty(str3) && e.getVariant().equals(str3)) {
                        i = 2;
                    }
                }
            }
            if (i <= i2) {
                i = i2;
            }
            i2 = i;
        }
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("IvonaPackagesInfo", "getVoiceByLocale res:" + i2);
        }
        return i2;
    }

    public Map d() {
        HashMap hashMap = new HashMap();
        if (this.c == null) {
            a();
        }
        for (a aVar : this.c.values()) {
            b g = aVar.g();
            if (g == b.FULL_INSTALLED || g == b.FILES_WITHOUT_APK) {
                Locale f = aVar.f();
                ArrayList arrayList = (ArrayList) hashMap.get(f);
                if (arrayList == null) {
                    arrayList = new ArrayList();
                    hashMap.put(f, arrayList);
                }
                arrayList.add(aVar);
            }
        }
        return hashMap;
    }
}
