package com.google.android.vending.a;

import android.content.Context;
import android.util.Log;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.HashMap;
import java.util.Map;
import java.util.Vector;
import org.apache.http.NameValuePair;
import org.apache.http.client.utils.URLEncodedUtils;

/* compiled from: APKExpansionPolicy.java */
/* loaded from: classes.dex */
public class b implements r {
    private long a;
    private long b;
    private long c;
    private long d;
    private int f;
    private final s g;
    private long e = 0;
    private final Vector h = new Vector();
    private final Vector i = new Vector();
    private final Vector j = new Vector();

    public b(Context context, q qVar) {
        this.g = new s(context.getSharedPreferences("com.android.vending.licensing.APKExpansionPolicy", 0), qVar);
        this.f = Integer.parseInt(this.g.b("lastResponse", Integer.toString(291)));
        this.a = Long.parseLong(this.g.b("validityTimestamp", "0"));
        this.b = Long.parseLong(this.g.b("retryUntil", "0"));
        this.c = Long.parseLong(this.g.b("maxRetries", "0"));
        this.d = Long.parseLong(this.g.b("retryCount", "0"));
    }

    public void a() {
        this.g.a("lastResponse", Integer.toString(291));
        b("0");
        c("0");
        a(Long.parseLong("0"));
        a("0");
        this.g.a();
    }

    @Override // com.google.android.vending.a.r
    public void a(int i, t tVar) {
        if (i != 291) {
            a(0L);
        } else {
            a(this.d + 1);
        }
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("APKExpansionPolicy", "response:" + i + "   rawData:" + tVar);
        }
        Log.i("CL", Integer.toString(70567304 + i));
        if (i == 256) {
            Map d = d(tVar.g);
            this.f = i;
            a(Long.toString(System.currentTimeMillis() + 60000));
            for (String str : d.keySet()) {
                if (str.equals("VT")) {
                    a((String) d.get(str));
                } else if (str.equals("GT")) {
                    b((String) d.get(str));
                } else if (str.equals("GR")) {
                    c((String) d.get(str));
                } else if (str.startsWith("FILE_URL")) {
                    a(Integer.parseInt(str.substring("FILE_URL".length())) - 1, (String) d.get(str));
                } else if (str.startsWith("FILE_NAME")) {
                    b(Integer.parseInt(str.substring("FILE_NAME".length())) - 1, (String) d.get(str));
                } else if (str.startsWith("FILE_SIZE")) {
                    a(Integer.parseInt(str.substring("FILE_SIZE".length())) - 1, Long.parseLong((String) d.get(str)));
                }
            }
        } else if (i == 561) {
            a("0");
            b("0");
            c("0");
        }
        d(i);
        this.g.a();
    }

    private void d(int i) {
        this.e = System.currentTimeMillis();
        this.f = i;
        this.g.a("lastResponse", Integer.toString(i));
    }

    private void a(long j) {
        this.d = j;
        this.g.a("retryCount", Long.toString(j));
    }

    private void a(String str) {
        Long valueOf;
        try {
            valueOf = Long.valueOf(Long.parseLong(str));
        } catch (NumberFormatException e) {
            Log.w("APKExpansionPolicy", "License validity timestamp (VT) missing, caching for a minute");
            valueOf = Long.valueOf(System.currentTimeMillis() + 60000);
            str = Long.toString(valueOf.longValue());
        }
        this.a = valueOf.longValue();
        this.g.a("validityTimestamp", str);
    }

    private void b(String str) {
        Long l;
        try {
            l = Long.valueOf(Long.parseLong(str));
        } catch (NumberFormatException e) {
            Log.w("APKExpansionPolicy", "License retry timestamp (GT) missing, grace period disabled");
            str = "0";
            l = 0L;
        }
        this.b = l.longValue();
        this.g.a("retryUntil", str);
    }

    private void c(String str) {
        Long l;
        try {
            l = Long.valueOf(Long.parseLong(str));
        } catch (NumberFormatException e) {
            Log.w("APKExpansionPolicy", "Licence retry count (GR) missing, grace period disabled");
            str = "0";
            l = 0L;
        }
        this.c = l.longValue();
        this.g.a("maxRetries", str);
    }

    public int b() {
        return this.h.size();
    }

    public String a(int i) {
        if (i < this.h.size()) {
            return (String) this.h.elementAt(i);
        }
        return null;
    }

    public void a(int i, String str) {
        if (i >= this.h.size()) {
            this.h.setSize(i + 1);
        }
        this.h.set(i, str);
    }

    public String b(int i) {
        if (i < this.i.size()) {
            return (String) this.i.elementAt(i);
        }
        return null;
    }

    public void b(int i, String str) {
        if (i >= this.i.size()) {
            this.i.setSize(i + 1);
        }
        this.i.set(i, str);
    }

    public long c(int i) {
        if (i < this.j.size()) {
            return ((Long) this.j.elementAt(i)).longValue();
        }
        return -1L;
    }

    public void a(int i, long j) {
        if (i >= this.j.size()) {
            this.j.setSize(i + 1);
        }
        this.j.set(i, Long.valueOf(j));
    }

    @Override // com.google.android.vending.a.r
    public boolean c() {
        long currentTimeMillis = System.currentTimeMillis();
        if (this.f == 256) {
            return currentTimeMillis <= this.a;
        }
        if (this.f != 291 || currentTimeMillis >= this.e + 60000) {
            return false;
        }
        return currentTimeMillis <= this.b || this.d <= this.c;
    }

    private Map d(String str) {
        HashMap hashMap = new HashMap();
        try {
            for (NameValuePair nameValuePair : URLEncodedUtils.parse(new URI("?" + str), "UTF-8")) {
                String name = nameValuePair.getName();
                int i = 0;
                while (hashMap.containsKey(name)) {
                    i++;
                    name = nameValuePair.getName() + i;
                }
                hashMap.put(name, nameValuePair.getValue());
            }
        } catch (URISyntaxException e) {
            Log.w("APKExpansionPolicy", "Invalid syntax error while decoding extras data from server.");
        }
        return hashMap;
    }
}
