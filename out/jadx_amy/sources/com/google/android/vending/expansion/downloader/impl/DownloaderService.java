package com.google.android.vending.expansion.downloader.impl;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.net.wifi.WifiManager;
import android.os.Handler;
import android.os.IBinder;
import android.os.Messenger;
import android.os.SystemClock;
import android.util.Log;
import com.google.android.vending.expansion.downloader.DownloadProgressInfo;
import java.io.File;

/* loaded from: classes.dex */
public abstract class DownloaderService extends CustomIntentService implements com.google.android.vending.expansion.downloader.n {
    private static boolean g;
    long a;
    long b;
    int c;
    long d;
    long e;
    float f;
    private boolean h;
    private boolean i;
    private boolean j;
    private boolean k;
    private boolean l;
    private boolean m;
    private boolean n;
    private int o;
    private int p;
    private ConnectivityManager q;
    private WifiManager r;
    private PackageInfo s;
    private BroadcastReceiver t;
    private final com.google.android.vending.expansion.downloader.o u;
    private final Messenger v;
    private Messenger w;
    private i x;
    private PendingIntent y;
    private PendingIntent z;

    public abstract String h();

    public abstract byte[] i();

    public abstract String j();

    public DownloaderService() {
        super("LVLDownloadService");
        this.u = com.google.android.vending.expansion.downloader.h.a(this);
        this.v = this.u.a();
    }

    public static boolean b(int i) {
        return i >= 400 && i < 600;
    }

    public static boolean c(int i) {
        return (i >= 200 && i < 300) || (i >= 400 && i < 600);
    }

    @Override // com.google.android.vending.expansion.downloader.impl.CustomIntentService, android.app.Service
    public IBinder onBind(Intent intent) {
        Log.d("LVLDL", "Service Bound");
        return this.v.getBinder();
    }

    public boolean f() {
        return this.h && !this.j;
    }

    private void a(int i, int i2) {
        switch (i) {
            case 0:
                this.j = true;
                switch (i2) {
                    case 1:
                    case 2:
                    case 4:
                    case 7:
                    case 11:
                        this.l = false;
                        this.m = false;
                        break;
                    case 3:
                    case 5:
                    case 6:
                    case 8:
                    case 9:
                    case 10:
                        this.l = true;
                        this.m = false;
                        break;
                    case 12:
                    default:
                        this.j = false;
                        this.l = false;
                        this.m = false;
                        break;
                    case 13:
                    case 14:
                    case 15:
                        this.l = true;
                        this.m = true;
                        break;
                }
            case 1:
            case 7:
            case 9:
                this.j = false;
                this.l = false;
                this.m = false;
                break;
            case 6:
                this.j = true;
                this.l = true;
                this.m = true;
                break;
        }
    }

    private void a(NetworkInfo networkInfo) {
        boolean z = this.h;
        boolean z2 = this.i;
        boolean z3 = this.j;
        boolean z4 = this.k;
        boolean z5 = this.l;
        if (networkInfo != null) {
            this.k = networkInfo.isRoaming();
            this.i = networkInfo.isFailover();
            this.h = networkInfo.isConnected();
            a(networkInfo.getType(), networkInfo.getSubtype());
        } else {
            this.k = false;
            this.i = false;
            this.h = false;
            a(-1, -1);
        }
        this.n = (!this.n && z == this.h && z2 == this.i && z3 == this.j && z4 == this.k && z5 == this.l) ? false : true;
    }

    void g() {
        if (this.q == null) {
            this.q = (ConnectivityManager) getSystemService("connectivity");
        }
        if (this.r == null) {
            this.r = (WifiManager) getSystemService("wifi");
        }
        if (this.q == null) {
            Log.w("LVLDL", "couldn't get connectivity manager to poll network state");
        } else {
            a(this.q.getActiveNetworkInfo());
        }
    }

    private static boolean a(u uVar, PackageInfo packageInfo) {
        return uVar.f != packageInfo.versionCode;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static synchronized boolean n() {
        boolean z;
        synchronized (DownloaderService.class) {
            z = g;
        }
        return z;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static synchronized void b(boolean z) {
        synchronized (DownloaderService.class) {
            g = z;
        }
    }

    public static int a(Context context, Intent intent, Class cls) {
        return a(context, (PendingIntent) intent.getParcelableExtra("EPI"), cls);
    }

    public static int a(Context context, PendingIntent pendingIntent, Class cls) {
        return a(context, pendingIntent, context.getPackageName(), cls.getName());
    }

    public static int a(Context context, PendingIntent pendingIntent, String str, String str2) {
        int i = 0;
        PackageInfo packageInfo = context.getPackageManager().getPackageInfo(context.getPackageName(), 0);
        u a = u.a(context);
        int i2 = a(a, packageInfo) ? 1 : 0;
        if (a.g == 0) {
            h[] a2 = a.a();
            if (a2 != null) {
                int length = a2.length;
                while (true) {
                    if (i >= length) {
                        break;
                    }
                    h hVar = a2[i];
                    if (com.google.android.vending.expansion.downloader.l.a(context, hVar.c, hVar.e, true)) {
                        i++;
                    } else {
                        a.c(-1);
                        i2 = 2;
                        break;
                    }
                }
            }
        } else {
            i2 = 2;
        }
        switch (i2) {
            case 1:
            case 2:
                Intent intent = new Intent();
                intent.setClassName(str, str2);
                intent.putExtra("EPI", pendingIntent);
                context.startService(intent);
            default:
                return i2;
        }
    }

    @Override // com.google.android.vending.expansion.downloader.n
    public void a() {
        this.o = 1;
        this.p = 490;
    }

    @Override // com.google.android.vending.expansion.downloader.n
    public void b() {
        this.o = 1;
        this.p = 193;
    }

    @Override // com.google.android.vending.expansion.downloader.n
    public void a(int i) {
        u.a(this).b(i);
    }

    @Override // com.google.android.vending.expansion.downloader.n
    public void c() {
        if (this.o == 1) {
            this.o = 0;
        }
        Intent intent = new Intent(this, getClass());
        intent.putExtra("EPI", this.y);
        startService(intent);
    }

    public void a(Context context) {
        Context applicationContext = context.getApplicationContext();
        new Handler(applicationContext.getMainLooper()).post(new s(this, applicationContext, this.y));
    }

    public boolean a(u uVar, int i, String str, long j) {
        String str2;
        h a = uVar.a(str);
        if (a != null && (str2 = a.c) != null) {
            if (str.equals(str2)) {
                return false;
            }
            File file = new File(com.google.android.vending.expansion.downloader.l.a(this, str2));
            if (file.exists()) {
                file.delete();
            }
        }
        return com.google.android.vending.expansion.downloader.l.a(this, str, j, true) ? false : true;
    }

    private void b(long j) {
        AlarmManager alarmManager = (AlarmManager) getSystemService("alarm");
        if (alarmManager == null) {
            Log.e("LVLDL", "couldn't get alarm manager");
            return;
        }
        String j2 = j();
        Intent intent = new Intent("android.intent.action.DOWNLOAD_WAKEUP");
        intent.putExtra("EPI", this.y);
        intent.setClassName(getPackageName(), j2);
        this.z = PendingIntent.getBroadcast(this, 0, intent, 1073741824);
        alarmManager.set(0, System.currentTimeMillis() + j, this.z);
    }

    private void o() {
        if (this.z != null) {
            AlarmManager alarmManager = (AlarmManager) getSystemService("alarm");
            if (alarmManager == null) {
                Log.e("LVLDL", "couldn't get alarm manager");
            } else {
                alarmManager.cancel(this.z);
                this.z = null;
            }
        }
    }

    @Override // com.google.android.vending.expansion.downloader.impl.CustomIntentService
    protected void a(Intent intent) {
        int i;
        boolean z = true;
        b(true);
        try {
            u a = u.a(this);
            PendingIntent pendingIntent = (PendingIntent) intent.getParcelableExtra("EPI");
            if (pendingIntent != null) {
                this.x.a(pendingIntent);
                this.y = pendingIntent;
            } else {
                if (this.y == null) {
                    Log.e("LVLDL", "Downloader started in bad state without notification intent.");
                    return;
                }
                this.x.a(this.y);
            }
            if (a(a, this.s)) {
                a((Context) this);
                return;
            }
            h[] a2 = a.a();
            this.a = 0L;
            this.b = 0L;
            this.c = a2.length;
            for (h hVar : a2) {
                if (hVar.h == 200 && !com.google.android.vending.expansion.downloader.l.a(this, hVar.c, hVar.e, true)) {
                    hVar.h = 0;
                    hVar.f = 0L;
                }
                this.b += hVar.e;
                this.a += hVar.f;
            }
            g();
            if (this.t == null) {
                this.t = new r(this, this);
                IntentFilter intentFilter = new IntentFilter("android.net.conn.CONNECTIVITY_CHANGE");
                intentFilter.addAction("android.net.wifi.WIFI_STATE_CHANGED");
                registerReceiver(this.t, intentFilter);
            }
            for (h hVar2 : a2) {
                long j = hVar2.f;
                if (hVar2.h != 200) {
                    k kVar = new k(hVar2, this, this.x);
                    o();
                    b(5000L);
                    kVar.a();
                    o();
                }
                a.d(hVar2);
                switch (hVar2.h) {
                    case 193:
                        i = 7;
                        z = false;
                        break;
                    case 194:
                    case 195:
                        i = 6;
                        break;
                    case 196:
                    case 197:
                        if (this.r != null && !this.r.isWifiEnabled()) {
                            i = 8;
                            break;
                        } else {
                            i = 9;
                            break;
                        }
                    case 200:
                        this.a = (hVar2.f - j) + this.a;
                        a.a(this.s.versionCode, 0);
                    case 403:
                        a((Context) this);
                        return;
                    case 487:
                        i = 13;
                        hVar2.f = 0L;
                        a.c(hVar2);
                        break;
                    case 490:
                        i = 18;
                        break;
                    case 498:
                        i = 17;
                        break;
                    case 499:
                        i = 14;
                        break;
                    default:
                        i = 19;
                        z = false;
                        break;
                }
                if (z) {
                    b(60000L);
                } else {
                    o();
                }
                this.x.a(i);
                return;
            }
            this.x.a(5);
        } finally {
            b(false);
        }
    }

    @Override // com.google.android.vending.expansion.downloader.impl.CustomIntentService, android.app.Service
    public void onDestroy() {
        if (this.t != null) {
            unregisterReceiver(this.t);
            this.t = null;
        }
        this.u.b(this);
        super.onDestroy();
    }

    public int a(u uVar) {
        if (this.h) {
            if (!this.j) {
                return 1;
            }
            int i = uVar.h;
            if (this.k) {
                return 5;
            }
            return (i & 1) == 0 ? 6 : 1;
        }
        return 2;
    }

    @Override // com.google.android.vending.expansion.downloader.impl.CustomIntentService, android.app.Service
    public void onCreate() {
        super.onCreate();
        try {
            this.s = getPackageManager().getPackageInfo(getPackageName(), 0);
            this.x = new i(this, getPackageManager().getApplicationLabel(getApplicationInfo()));
        } catch (PackageManager.NameNotFoundException e) {
            e.printStackTrace();
        }
    }

    public String a(String str) {
        return com.google.android.vending.expansion.downloader.l.a(this) + File.separator + str + ".tmp";
    }

    public String a(String str, long j) {
        String a = a(str);
        File file = new File(a);
        if (!com.google.android.vending.expansion.downloader.l.a()) {
            Log.d("LVLDL", "External media not mounted: " + a);
            throw new q(499, "external media is not yet mounted");
        }
        if (file.exists()) {
            Log.d("LVLDL", "File already exists: " + a);
            throw new q(488, "requested destination file already exists");
        }
        if (com.google.android.vending.expansion.downloader.l.a(com.google.android.vending.expansion.downloader.l.a(a)) < j) {
            throw new q(498, "insufficient space on external storage");
        }
        return a;
    }

    public int k() {
        return this.o;
    }

    public int l() {
        return this.p;
    }

    public void a(long j) {
        long j2;
        long uptimeMillis = SystemClock.uptimeMillis();
        if (0 != this.e) {
            float f = (j - this.d) / (uptimeMillis - this.e);
            if (0.0f != this.f) {
                this.f = (f * 0.005f) + (0.995f * this.f);
            } else {
                this.f = f;
            }
            j2 = (long) ((this.b - j) / this.f);
        } else {
            j2 = -1;
        }
        this.e = uptimeMillis;
        this.d = j;
        this.x.a(new DownloadProgressInfo(this.b, j, j2, this.f));
    }

    @Override // com.google.android.vending.expansion.downloader.impl.CustomIntentService
    protected boolean e() {
        return u.a(this).g == 0;
    }

    @Override // com.google.android.vending.expansion.downloader.n
    public void d() {
        this.x.a();
    }

    @Override // com.google.android.vending.expansion.downloader.n
    public void a(Messenger messenger) {
        this.w = messenger;
        this.x.b(this.w);
    }
}
