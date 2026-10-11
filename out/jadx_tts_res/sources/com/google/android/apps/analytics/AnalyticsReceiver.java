package com.google.android.apps.analytics;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;
import java.util.HashMap;

/* loaded from: classes.dex */
public class AnalyticsReceiver extends BroadcastReceiver {
    static String a(String str) {
        String[] split = str.split("&");
        HashMap hashMap = new HashMap();
        for (String str2 : split) {
            String[] split2 = str2.split("=");
            if (split2.length != 2) {
                break;
            }
            hashMap.put(split2[0], split2[1]);
        }
        boolean z = hashMap.get("utm_campaign") != null;
        boolean z2 = hashMap.get("utm_medium") != null;
        boolean z3 = hashMap.get("utm_source") != null;
        if (!z || !z2 || !z3) {
            Log.w("googleanalytics", "Badly formatted referrer missing campaign, name or source");
            return null;
        }
        String[][] strArr = {new String[]{"utmcid", (String) hashMap.get("utm_id")}, new String[]{"utmcsr", (String) hashMap.get("utm_source")}, new String[]{"utmgclid", (String) hashMap.get("gclid")}, new String[]{"utmccn", (String) hashMap.get("utm_campaign")}, new String[]{"utmcmd", (String) hashMap.get("utm_medium")}, new String[]{"utmctr", (String) hashMap.get("utm_term")}, new String[]{"utmcct", (String) hashMap.get("utm_content")}};
        StringBuilder sb = new StringBuilder();
        boolean z4 = true;
        for (int i = 0; i < strArr.length; i++) {
            if (strArr[i][1] != null) {
                String replace = strArr[i][1].replace("+", "%20").replace(" ", "%20");
                if (z4) {
                    z4 = false;
                } else {
                    sb.append("|");
                }
                sb.append(strArr[i][0]).append("=").append(replace);
            }
        }
        return sb.toString();
    }

    @Override // android.content.BroadcastReceiver
    public void onReceive(Context context, Intent intent) {
        String stringExtra = intent.getStringExtra("referrer");
        if (!"com.android.vending.INSTALL_REFERRER".equals(intent.getAction()) || stringExtra == null) {
            return;
        }
        String a = a(stringExtra);
        if (a == null) {
            Log.w("googleanalytics", "Badly formatted referrer, ignored");
        } else {
            new a(new b(context)).a(a);
            Log.d("googleanalytics", "Stored referrer:" + a);
        }
    }
}
