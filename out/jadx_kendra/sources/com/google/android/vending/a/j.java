package com.google.android.vending.a;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.pm.PackageManager;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.os.RemoteException;
import android.util.Log;
import java.security.KeyFactory;
import java.security.NoSuchAlgorithmException;
import java.security.PublicKey;
import java.security.SecureRandom;
import java.security.spec.InvalidKeySpecException;
import java.security.spec.X509EncodedKeySpec;
import java.util.HashSet;
import java.util.LinkedList;
import java.util.Queue;
import java.util.Set;

/* compiled from: LicenseChecker.java */
/* loaded from: classes.dex */
public class j implements ServiceConnection {
    private static final SecureRandom a = new SecureRandom();
    private static final boolean b = com.ivona.tts.commonlib.a.c;
    private g c;
    private final PublicKey d;
    private final Context e;
    private final r f;
    private final Handler g;
    private final String h;
    private final String i;
    private final Set j = new HashSet();
    private final Queue k = new LinkedList();

    public j(Context context, r rVar, String str) {
        this.e = context;
        this.f = rVar;
        this.d = a(str);
        this.h = this.e.getPackageName();
        this.i = a(context, this.h);
        HandlerThread handlerThread = new HandlerThread("background thread");
        handlerThread.start();
        this.g = new Handler(handlerThread.getLooper());
    }

    private static PublicKey a(String str) {
        try {
            return KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(com.google.android.vending.a.a.a.a(str)));
        } catch (com.google.android.vending.a.a.b e) {
            Log.e("CL", "92950241");
            throw new IllegalArgumentException(e);
        } catch (NoSuchAlgorithmException e2) {
            throw new RuntimeException(e2);
        } catch (InvalidKeySpecException e3) {
            Log.e("CL", "79780660");
            throw new IllegalArgumentException(e3);
        }
    }

    public synchronized void a(n nVar) {
        if (this.f.c()) {
            Log.i("CL", "92372424");
            nVar.a(256);
        } else {
            o oVar = new o(this.f, new p(), nVar, d(), this.h, this.i);
            if (this.c == null) {
                Log.i("CL", "84992414");
                try {
                    if (this.e.bindService(new Intent(new String(com.google.android.vending.a.a.a.a("Y29tLmFuZHJvaWQudmVuZGluZy5saWNlbnNpbmcuSUxpY2Vuc2luZ1NlcnZpY2U="))), this, 1)) {
                        this.k.offer(oVar);
                    } else {
                        Log.e("CL", "02887714");
                        b(oVar);
                    }
                } catch (com.google.android.vending.a.a.b e) {
                    e.printStackTrace();
                } catch (SecurityException e2) {
                    nVar.c(6);
                }
            } else {
                this.k.offer(oVar);
                b();
            }
        }
    }

    private void b() {
        while (true) {
            o oVar = (o) this.k.poll();
            if (oVar != null) {
                try {
                    Log.i("CL", "35465370");
                    this.c.a(oVar.b(), oVar.c(), new k(this, oVar));
                    this.j.add(oVar);
                } catch (RemoteException e) {
                    Log.w("CL", "71830661", e);
                    b(oVar);
                }
            } else {
                return;
            }
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public synchronized void a(o oVar) {
        this.j.remove(oVar);
        if (this.j.isEmpty()) {
            c();
        }
    }

    @Override // android.content.ServiceConnection
    public synchronized void onServiceConnected(ComponentName componentName, IBinder iBinder) {
        this.c = h.a(iBinder);
        b();
    }

    @Override // android.content.ServiceConnection
    public synchronized void onServiceDisconnected(ComponentName componentName) {
        Log.w("CL", "83185512");
        this.c = null;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public synchronized void b(o oVar) {
        this.f.a(291, null);
        if (this.f.c()) {
            oVar.a().a(291);
        } else {
            oVar.a().b(291);
        }
    }

    private void c() {
        if (this.c != null) {
            try {
                this.e.unbindService(this);
            } catch (IllegalArgumentException e) {
                Log.e("CL", "63929867");
            }
            this.c = null;
        }
    }

    private int d() {
        return a.nextInt();
    }

    private static String a(Context context, String str) {
        try {
            return String.valueOf(context.getPackageManager().getPackageInfo(str, 0).versionCode);
        } catch (PackageManager.NameNotFoundException e) {
            Log.e("CL", "25101865");
            return "";
        }
    }
}
