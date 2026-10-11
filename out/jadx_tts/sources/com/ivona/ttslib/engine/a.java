package com.ivona.ttslib.engine;

import android.util.Log;
import java.io.BufferedReader;
import java.io.FileReader;

/* compiled from: CPUBenchmark.java */
/* loaded from: classes.dex */
public class a extends Thread {
    b a = b.STOPPED;
    private int b;
    private int c;
    private long d;
    private int e;
    private int f;
    private long g;
    private int h;
    private int i;
    private long j;

    private int a(boolean z) {
        int i;
        Exception e;
        FileReader fileReader;
        int i2 = 0;
        try {
            fileReader = new FileReader(z ? "/proc/stat" : "/proc/self/stat");
            BufferedReader bufferedReader = new BufferedReader(fileReader);
            if (z) {
                while (true) {
                    String readLine = bufferedReader.readLine();
                    if (readLine == null) {
                        break;
                    }
                    if (readLine.startsWith("cpu ")) {
                        String[] split = readLine.split("\\s+");
                        i2 = Integer.parseInt(split[3]) + Integer.parseInt(split[1]) + Integer.parseInt(split[2]);
                    }
                }
                i = i2;
            } else {
                String[] split2 = bufferedReader.readLine().split("\\s+");
                i = Integer.parseInt(split2[14]) + Integer.parseInt(split2[13]);
            }
        } catch (Exception e2) {
            i = 0;
            e = e2;
        }
        try {
            fileReader.close();
        } catch (Exception e3) {
            e = e3;
            e.printStackTrace();
            return i;
        }
        return i;
    }

    private void c() {
        this.h = a(true);
        this.i = a(false);
        this.j = System.currentTimeMillis();
    }

    private void d() {
        this.e = this.h;
        this.f = this.i;
        this.g = this.j;
    }

    public void a(long j, int i, int i2) {
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("IvonaCPUBenchmark", String.format("last %d ms: process: %d / total: %d = %.2f%% | ∑time: %d ms, ∑process: %d / ∑total: %d = %.2f%%", Long.valueOf(j), Integer.valueOf(i2), Integer.valueOf(i), Float.valueOf((i2 * 100.0f) / i), Long.valueOf(this.d), Integer.valueOf(this.c), Integer.valueOf(this.b), Float.valueOf((this.c * 100.0f) / this.b)));
        }
    }

    private void e() {
        int i = this.h - this.e;
        int i2 = this.i - this.f;
        long j = this.j - this.g;
        this.b += i;
        this.c += i2;
        this.d += j;
        a(j, i, i2);
    }

    @Override // java.lang.Thread, java.lang.Runnable
    public synchronized void run() {
        this.a = b.PAUSED;
        while (this.a != b.STOPPED) {
            try {
                wait(1000L);
            } catch (InterruptedException e) {
            }
            if (this.a != b.PAUSED) {
                c();
                e();
                d();
            }
        }
    }

    public synchronized void a() {
        this.a = b.PAUSED;
    }

    public synchronized void b() {
        c();
        d();
        this.a = b.RUNNING;
        notify();
    }
}
