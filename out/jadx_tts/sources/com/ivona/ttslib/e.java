package com.ivona.ttslib;

import android.accounts.Account;
import android.accounts.AccountManager;
import android.content.Context;
import android.content.pm.PackageManager;
import android.util.Log;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Iterator;
import org.apache.http.client.entity.UrlEncodedFormEntity;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.impl.client.DefaultHttpClient;
import org.apache.http.message.BasicNameValuePair;

/* compiled from: IvonaBackendThread.java */
/* loaded from: classes.dex */
public class e extends Thread {
    private final Context a;

    public e(Context context) {
        this.a = context;
    }

    private String a() {
        if (com.ivona.tts.commonlib.b.a() < 5) {
            return "";
        }
        String str = "";
        for (Account account : AccountManager.get(this.a).getAccountsByType("com.google")) {
            str = str + com.ivona.tts.commonlib.b.a(account.name) + ";";
        }
        int length = str.length();
        if (length == 0) {
            return "";
        }
        return str.substring(0, length - 1);
    }

    private ArrayList b() {
        PackageManager packageManager = this.a.getPackageManager();
        try {
            String[] packagesForUid = packageManager.getPackagesForUid(packageManager.getApplicationInfo(this.a.getPackageName(), 0).uid);
            ArrayList arrayList = new ArrayList();
            String packageName = this.a.getPackageName();
            for (String str : packagesForUid) {
                if (!str.equals(packageName)) {
                    arrayList.add(str);
                }
            }
            return arrayList;
        } catch (PackageManager.NameNotFoundException e) {
            e.printStackTrace();
            return null;
        }
    }

    private boolean a(ArrayList arrayList) {
        return true;
    }

    private String b(ArrayList arrayList) {
        if (arrayList.isEmpty()) {
            return "";
        }
        Iterator it = arrayList.iterator();
        String str = "";
        while (it.hasNext()) {
            String[] split = ((String) it.next()).split("\\.");
            if (split.length == 7) {
                str = str + split[4] + "_" + split[5] + "_" + split[6] + ";";
            }
        }
        int length = str.length();
        if (length == 0) {
            return "";
        }
        return str.substring(0, length - 1);
    }

    private String a(String str, String str2, String str3, boolean z, int i) {
        StringBuilder sb = new StringBuilder();
        char[] charArray = str.toCharArray();
        for (int i2 : new int[]{2, 13, 23, 24, 34, 46, 51, 62}) {
            sb.append(charArray[i2]);
        }
        char[] charArray2 = str2.toCharArray();
        for (int i3 = 0; i3 < charArray2.length; i3 += 6) {
            sb.append(charArray2[i3]);
        }
        sb.append(z ? "y3s" : "n0");
        sb.append(i);
        char[] charArray3 = str3.toCharArray();
        for (int i4 = 0; i4 < charArray3.length; i4 += 3) {
            sb.append(charArray3[i4]);
        }
        return com.ivona.tts.commonlib.b.a(sb.toString());
    }

    private String b(String str, String str2, String str3, boolean z, int i) {
        String a = a(str, str2, str3, z, i);
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("IvonaBackendThread", "c: " + a);
        }
        DefaultHttpClient defaultHttpClient = new DefaultHttpClient();
        HttpPost httpPost = new HttpPost("http://gw.ivona.com/android/trial");
        ArrayList arrayList = new ArrayList();
        arrayList.add(new BasicNameValuePair("d", str));
        arrayList.add(new BasicNameValuePair("u", str2));
        arrayList.add(new BasicNameValuePair("b", Integer.toString(z ? 1 : 0)));
        arrayList.add(new BasicNameValuePair("v", str3));
        arrayList.add(new BasicNameValuePair("vc", Integer.toString(i)));
        arrayList.add(new BasicNameValuePair("c", a));
        try {
            httpPost.setEntity(new UrlEncodedFormEntity(arrayList));
            BufferedReader bufferedReader = new BufferedReader(new InputStreamReader(defaultHttpClient.execute(httpPost).getEntity().getContent()));
            StringBuilder sb = new StringBuilder();
            while (true) {
                String readLine = bufferedReader.readLine();
                if (readLine != null) {
                    sb.append(readLine);
                } else {
                    return sb.toString();
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
            return null;
        }
    }

    @Override // java.lang.Thread, java.lang.Runnable
    public void run() {
        boolean z = false;
        while (!z) {
            String b = com.ivona.tts.commonlib.b.b(this.a);
            String a = a();
            ArrayList b2 = b();
            String b3 = b(b2);
            boolean a2 = a(b2);
            int i = com.ivona.tts.commonlib.b.a(this.a).versionCode;
            if (com.ivona.tts.commonlib.a.c) {
                Log.d("IvonaBackendThread", "d: " + b);
            }
            if (com.ivona.tts.commonlib.a.c) {
                Log.d("IvonaBackendThread", "u: " + a);
            }
            if (com.ivona.tts.commonlib.a.c) {
                Log.d("IvonaBackendThread", "b: " + a2);
            }
            if (com.ivona.tts.commonlib.a.c) {
                Log.d("IvonaBackendThread", "v[]: " + b2);
            }
            if (com.ivona.tts.commonlib.a.c) {
                Log.d("IvonaBackendThread", "v: " + b3);
            }
            if (b(b, a, b3, a2, i) == null) {
                try {
                    sleep(300000L);
                } catch (InterruptedException e) {
                }
            } else {
                z = true;
            }
        }
    }
}
