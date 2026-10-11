package com.google.android.vending.expansion.downloader.impl;

import android.content.Context;
import android.net.Proxy;
import android.os.Build;
import android.util.Log;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.SyncFailedException;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;
import org.apache.http.Header;
import org.apache.http.HttpHost;
import org.apache.http.HttpResponse;
import org.apache.http.client.methods.HttpGet;

/* compiled from: DownloadThread.java */
/* loaded from: classes.dex */
public class k {
    private Context a;
    private h b;
    private DownloaderService c;
    private final u d;
    private final i e;
    private String f;

    public k(h hVar, DownloaderService downloaderService, i iVar) {
        this.a = downloaderService;
        this.b = hVar;
        this.c = downloaderService;
        this.e = iVar;
        this.d = u.a(downloaderService);
        this.f = "APKXDL (Linux; U; Android " + Build.VERSION.RELEASE + ";" + Locale.getDefault().toString() + "; " + Build.DEVICE + "/" + Build.ID + ")" + downloaderService.getPackageName();
    }

    private String b() {
        return this.f;
    }

    public HttpHost a(Context context, String str) {
        String host;
        if (a(str) || this.c.f() || (host = Proxy.getHost(context)) == null) {
            return null;
        }
        return new HttpHost(host, Proxy.getPort(context), "http");
    }

    private static final boolean a(String str) {
        if (str == null) {
            return false;
        }
        try {
            String host = URI.create(str).getHost();
            if (host == null) {
                return false;
            }
            if (!host.equalsIgnoreCase("localhost") && !host.equals("127.0.0.1")) {
                if (!host.equals("[::1]")) {
                    return false;
                }
            }
            return true;
        } catch (IllegalArgumentException e) {
            return false;
        }
    }

    /* JADX WARN: Multi-variable type inference failed */
    /* JADX WARN: Removed duplicated region for block: B:45:0x0111  */
    /* JADX WARN: Removed duplicated region for block: B:47:0x0116  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public void a() {
        /*
            Method dump skipped, instructions count: 314
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: com.google.android.vending.expansion.downloader.impl.k.a():void");
    }

    private void a(o oVar, a aVar, HttpGet httpGet) {
        m mVar = new m();
        e(oVar);
        d(oVar, mVar);
        a(mVar, httpGet);
        a(oVar);
        this.e.a(3);
        HttpResponse b = b(oVar, aVar, httpGet);
        c(oVar, mVar, b);
        a(oVar, mVar, b);
        InputStream a = a(oVar, b);
        this.e.a(4);
        a(oVar, mVar, new byte[4096], a);
    }

    private void a(o oVar) {
        switch (this.c.a(this.d)) {
            case 1:
            case 4:
            default:
                return;
            case 2:
                throw new p(this, 195, "waiting for network to return");
            case 3:
                throw new p(this, 197, "waiting for wifi");
            case 5:
                throw new p(this, 195, "roaming is not allowed");
            case 6:
                throw new p(this, 196, "waiting for wifi or for download over cellular to be authorized");
        }
    }

    private void a(o oVar, m mVar, byte[] bArr, InputStream inputStream) {
        while (true) {
            int b = b(oVar, mVar, bArr, inputStream);
            if (b == -1) {
                b(oVar, mVar);
                return;
            }
            oVar.g = true;
            a(oVar, bArr, b);
            mVar.a += b;
            mVar.b = b + mVar.b;
            a(oVar, mVar);
            e(oVar);
        }
    }

    private void b(o oVar) {
        c(oVar);
        String str = oVar.a;
        String a = com.google.android.vending.expansion.downloader.l.a(this.c, this.b.c);
        if (!oVar.a.equals(a)) {
            File file = new File(str);
            File file2 = new File(a);
            if (this.b.e != -1 && this.b.f == this.b.e) {
                if (!file.renameTo(file2)) {
                    throw new p(this, 492, "unable to finalize destination file");
                }
                return;
            }
            throw new p(this, 487, "file delivered with incorrect size. probably due to network not browser configured");
        }
    }

    private void a(o oVar, int i) {
        d(oVar);
        if (oVar.a != null && DownloaderService.b(i)) {
            new File(oVar.a).delete();
            oVar.a = null;
        }
    }

    /* JADX WARN: Multi-variable type inference failed */
    /* JADX WARN: Type inference failed for: r2v0 */
    /* JADX WARN: Type inference failed for: r2v1 */
    /* JADX WARN: Type inference failed for: r2v10, types: [java.lang.String] */
    /* JADX WARN: Type inference failed for: r2v11, types: [java.lang.String] */
    /* JADX WARN: Type inference failed for: r2v12, types: [java.io.FileOutputStream] */
    /* JADX WARN: Type inference failed for: r2v13, types: [java.lang.String] */
    /* JADX WARN: Type inference failed for: r2v14, types: [java.lang.String] */
    /* JADX WARN: Type inference failed for: r2v18 */
    /* JADX WARN: Type inference failed for: r2v19 */
    /* JADX WARN: Type inference failed for: r2v2, types: [java.io.FileOutputStream] */
    /* JADX WARN: Type inference failed for: r2v20 */
    /* JADX WARN: Type inference failed for: r2v21 */
    /* JADX WARN: Type inference failed for: r2v22 */
    /* JADX WARN: Type inference failed for: r2v25 */
    /* JADX WARN: Type inference failed for: r2v26 */
    /* JADX WARN: Type inference failed for: r2v27 */
    /* JADX WARN: Type inference failed for: r2v28 */
    /* JADX WARN: Type inference failed for: r2v29 */
    /* JADX WARN: Type inference failed for: r2v30 */
    /* JADX WARN: Type inference failed for: r2v31 */
    /* JADX WARN: Type inference failed for: r2v32 */
    /* JADX WARN: Type inference failed for: r2v33 */
    /* JADX WARN: Type inference failed for: r2v34 */
    /* JADX WARN: Type inference failed for: r2v35 */
    /* JADX WARN: Type inference failed for: r2v5 */
    /* JADX WARN: Type inference failed for: r2v6, types: [java.io.FileOutputStream] */
    /* JADX WARN: Type inference failed for: r2v7, types: [java.lang.String] */
    /* JADX WARN: Type inference failed for: r2v8, types: [java.lang.String] */
    /* JADX WARN: Type inference failed for: r2v9, types: [java.io.FileOutputStream] */
    private void c(o oVar) {
        FileOutputStream fileOutputStream;
        Object obj;
        ?? r2 = 0;
        r2 = 0;
        r2 = 0;
        r2 = 0;
        r2 = 0;
        r2 = 0;
        try {
            try {
                try {
                    fileOutputStream = new FileOutputStream(oVar.a, true);
                } catch (Throwable th) {
                    th = th;
                    r2 = obj;
                    if (r2 != 0) {
                        try {
                            r2.close();
                        } catch (IOException e) {
                            Log.w("LVLDL", "IOException while closing synced file: ", e);
                        } catch (RuntimeException e2) {
                            Log.w("LVLDL", "exception while closing file: ", e2);
                        }
                    }
                    throw th;
                }
            } catch (FileNotFoundException e3) {
                e = e3;
                fileOutputStream = null;
            } catch (SyncFailedException e4) {
                e = e4;
            } catch (IOException e5) {
                e = e5;
            } catch (RuntimeException e6) {
                e = e6;
            }
            try {
                fileOutputStream.getFD().sync();
                obj = fileOutputStream;
                if (fileOutputStream != null) {
                    try {
                        fileOutputStream.close();
                        obj = fileOutputStream;
                    } catch (IOException e7) {
                        Log.w("LVLDL", "IOException while closing synced file: ", e7);
                        obj = "LVLDL";
                        r2 = "IOException while closing synced file: ";
                    } catch (RuntimeException e8) {
                        Log.w("LVLDL", "exception while closing file: ", e8);
                        obj = "LVLDL";
                        r2 = "exception while closing file: ";
                    }
                }
            } catch (FileNotFoundException e9) {
                e = e9;
                String str = "LVLDL";
                Log.w("LVLDL", "file " + oVar.a + " not found: " + e);
                obj = fileOutputStream;
                r2 = str;
                if (fileOutputStream != null) {
                    try {
                        fileOutputStream.close();
                        obj = fileOutputStream;
                        r2 = str;
                    } catch (IOException e10) {
                        Log.w("LVLDL", "IOException while closing synced file: ", e10);
                        obj = "LVLDL";
                        r2 = "IOException while closing synced file: ";
                    } catch (RuntimeException e11) {
                        Log.w("LVLDL", "exception while closing file: ", e11);
                        obj = "LVLDL";
                        r2 = "exception while closing file: ";
                    }
                }
            } catch (SyncFailedException e12) {
                e = e12;
                r2 = fileOutputStream;
                Log.w("LVLDL", "file " + oVar.a + " sync failed: " + e);
                if (r2 != 0) {
                    try {
                        r2.close();
                    } catch (IOException e13) {
                        r2 = "IOException while closing synced file: ";
                        Log.w("LVLDL", "IOException while closing synced file: ", e13);
                    } catch (RuntimeException e14) {
                        r2 = "exception while closing file: ";
                        Log.w("LVLDL", "exception while closing file: ", e14);
                    }
                }
            } catch (IOException e15) {
                e = e15;
                r2 = fileOutputStream;
                Log.w("LVLDL", "IOException trying to sync " + oVar.a + ": " + e);
                if (r2 != 0) {
                    try {
                        r2.close();
                    } catch (IOException e16) {
                        r2 = "IOException while closing synced file: ";
                        Log.w("LVLDL", "IOException while closing synced file: ", e16);
                    } catch (RuntimeException e17) {
                        r2 = "exception while closing file: ";
                        Log.w("LVLDL", "exception while closing file: ", e17);
                    }
                }
            } catch (RuntimeException e18) {
                e = e18;
                r2 = fileOutputStream;
                Log.w("LVLDL", "exception while syncing file: ", e);
                if (r2 != 0) {
                    try {
                        r2.close();
                    } catch (IOException e19) {
                        r2 = "IOException while closing synced file: ";
                        Log.w("LVLDL", "IOException while closing synced file: ", e19);
                    } catch (RuntimeException e20) {
                        r2 = "exception while closing file: ";
                        Log.w("LVLDL", "exception while closing file: ", e20);
                    }
                }
            }
        } catch (Throwable th2) {
            th = th2;
        }
    }

    private void d(o oVar) {
        try {
            if (oVar.b != null) {
                oVar.b.close();
                oVar.b = null;
            }
        } catch (IOException e) {
        }
    }

    private void e(o oVar) {
        if (this.c.k() == 1) {
            switch (this.c.l()) {
                case 193:
                    throw new p(this, this.c.l(), "download paused");
                default:
                    return;
            }
        }
    }

    private void a(o oVar, m mVar) {
        long currentTimeMillis = System.currentTimeMillis();
        if (mVar.a - mVar.h > 4096 && currentTimeMillis - mVar.i > 1000) {
            this.b.f = mVar.a;
            this.d.b(this.b);
            mVar.h = mVar.a;
            mVar.i = currentTimeMillis;
            this.c.a(mVar.b + this.c.a);
        }
    }

    private void a(o oVar, byte[] bArr, int i) {
        try {
            if (oVar.b == null) {
                oVar.b = new FileOutputStream(oVar.a, true);
            }
            oVar.b.write(bArr, 0, i);
            d(oVar);
        } catch (IOException e) {
            if (!com.google.android.vending.expansion.downloader.l.a()) {
                throw new p(this, 499, "external media not mounted while writing destination file");
            }
            if (com.google.android.vending.expansion.downloader.l.a(com.google.android.vending.expansion.downloader.l.a(oVar.a)) < i) {
                throw new p(this, 498, "insufficient space while writing destination file", e);
            }
            throw new p(this, 492, "while writing destination file: " + e.toString(), e);
        }
    }

    private void b(o oVar, m mVar) {
        this.b.f = mVar.a;
        this.d.c(this.b);
        if ((mVar.e == null || mVar.a == Integer.parseInt(mVar.e)) ? false : true) {
            if (a(mVar)) {
                throw new p(this, 489, "mismatched content length");
            }
            throw new p(this, f(oVar), "closed socket before end of file");
        }
    }

    private boolean a(m mVar) {
        return mVar.a > 0 && mVar.c == null;
    }

    private int b(o oVar, m mVar, byte[] bArr, InputStream inputStream) {
        try {
            return inputStream.read(bArr);
        } catch (IOException e) {
            c();
            this.b.f = mVar.a;
            this.d.c(this.b);
            if (a(mVar)) {
                throw new p(this, 489, "while reading response: " + e.toString() + ", can't resume interrupted download with no ETag", e);
            }
            throw new p(this, f(oVar), "while reading response: " + e.toString(), e);
        }
    }

    private InputStream a(o oVar, HttpResponse httpResponse) {
        try {
            return httpResponse.getEntity().getContent();
        } catch (IOException e) {
            c();
            throw new p(this, f(oVar), "while getting entity: " + e.toString(), e);
        }
    }

    private void c() {
        Log.i("LVLDL", "Net " + (this.c.a(this.d) == 1 ? "Up" : "Down"));
    }

    private void a(o oVar, m mVar, HttpResponse httpResponse) {
        if (!mVar.d) {
            b(oVar, mVar, httpResponse);
            try {
                oVar.a = this.c.a(this.b.c, this.b.e);
                try {
                    oVar.b = new FileOutputStream(oVar.a);
                } catch (FileNotFoundException e) {
                    try {
                        if (new File(com.google.android.vending.expansion.downloader.l.a(this.c)).mkdirs()) {
                            oVar.b = new FileOutputStream(oVar.a);
                        }
                    } catch (Exception e2) {
                        throw new p(this, 492, "while opening destination file: " + e.toString(), e);
                    }
                }
                c(oVar, mVar);
                a(oVar);
            } catch (q e3) {
                throw new p(this, e3.a, e3.b);
            }
        }
    }

    private void c(o oVar, m mVar) {
        this.b.d = mVar.c;
        this.d.c(this.b);
    }

    private void b(o oVar, m mVar, HttpResponse httpResponse) {
        Header firstHeader;
        Header firstHeader2 = httpResponse.getFirstHeader("Content-Disposition");
        if (firstHeader2 != null) {
            mVar.f = firstHeader2.getValue();
        }
        Header firstHeader3 = httpResponse.getFirstHeader("Content-Location");
        if (firstHeader3 != null) {
            mVar.g = firstHeader3.getValue();
        }
        Header firstHeader4 = httpResponse.getFirstHeader("ETag");
        if (firstHeader4 != null) {
            mVar.c = firstHeader4.getValue();
        }
        String str = null;
        Header firstHeader5 = httpResponse.getFirstHeader("Transfer-Encoding");
        if (firstHeader5 != null) {
            str = firstHeader5.getValue();
        }
        Header firstHeader6 = httpResponse.getFirstHeader("Content-Type");
        if (firstHeader6 != null && !firstHeader6.getValue().equals("application/vnd.android.obb")) {
            throw new p(this, 487, "file delivered with incorrect Mime type");
        }
        if (str == null && (firstHeader = httpResponse.getFirstHeader("Content-Length")) != null) {
            mVar.e = firstHeader.getValue();
            long parseLong = Long.parseLong(mVar.e);
            if (parseLong != -1 && parseLong != this.b.e) {
                Log.e("LVLDL", "Incorrect file size delivered.");
            }
        }
        if (mVar.e == null && (str == null || !str.equalsIgnoreCase("chunked"))) {
            throw new p(this, 495, "can't know size of download, giving up");
        }
    }

    private void c(o oVar, m mVar, HttpResponse httpResponse) {
        int statusCode = httpResponse.getStatusLine().getStatusCode();
        if (statusCode == 503 && this.b.j < 5) {
            b(oVar, httpResponse);
        }
        if (statusCode == 301 || statusCode == 302 || statusCode == 303 || statusCode == 307) {
            a(oVar, httpResponse, statusCode);
        }
        if (statusCode != (mVar.d ? 206 : 200)) {
            a(oVar, mVar, statusCode);
        } else {
            oVar.e = 0;
        }
    }

    private void a(o oVar, m mVar, int i) {
        int i2;
        if (DownloaderService.b(i)) {
            i2 = i;
        } else if (i >= 300 && i < 400) {
            i2 = 493;
        } else if (mVar.d && i == 200) {
            i2 = 489;
        } else {
            i2 = 494;
        }
        throw new p(this, i2, "http error " + i);
    }

    private void a(o oVar, HttpResponse httpResponse, int i) {
        if (oVar.e >= 5) {
            throw new p(this, 497, "too many redirects");
        }
        Header firstHeader = httpResponse.getFirstHeader("Location");
        if (firstHeader == null) {
            return;
        }
        try {
            String uri = new URI(this.b.a).resolve(new URI(firstHeader.getValue())).toString();
            oVar.e++;
            oVar.h = uri;
            if (i == 301 || i == 303) {
                oVar.f = uri;
            }
            throw new n(this);
        } catch (URISyntaxException e) {
            throw new p(this, 495, "Couldn't resolve redirect URI");
        }
    }

    private void a(m mVar, HttpGet httpGet) {
        if (mVar.d) {
            if (mVar.c != null) {
                httpGet.addHeader("If-Match", mVar.c);
            }
            httpGet.addHeader("Range", "bytes=" + mVar.a + "-");
        }
    }

    private void b(o oVar, HttpResponse httpResponse) {
        oVar.c = true;
        Header firstHeader = httpResponse.getFirstHeader("Retry-After");
        if (firstHeader != null) {
            try {
                oVar.d = Integer.parseInt(firstHeader.getValue());
                if (oVar.d < 0) {
                    oVar.d = 0;
                } else {
                    if (oVar.d < 30) {
                        oVar.d = 30;
                    } else if (oVar.d > 86400) {
                        oVar.d = 86400;
                    }
                    oVar.d += com.google.android.vending.expansion.downloader.l.a.nextInt(31);
                    oVar.d *= 1000;
                }
            } catch (NumberFormatException e) {
            }
        }
        throw new p(this, 194, "got 503 Service Unavailable, will retry later");
    }

    private HttpResponse b(o oVar, a aVar, HttpGet httpGet) {
        try {
            return aVar.execute(httpGet);
        } catch (IOException e) {
            c();
            throw new p(this, f(oVar), "while trying to execute request: " + e.toString(), e);
        } catch (IllegalArgumentException e2) {
            throw new p(this, 495, "while trying to execute request: " + e2.toString(), e2);
        }
    }

    private int f(o oVar) {
        if (this.c.a(this.d) != 1) {
            return 195;
        }
        if (this.b.j < 5) {
            oVar.c = true;
            return 194;
        }
        Log.w("LVLDL", "reached max retries for " + this.b.j);
        return 495;
    }

    private void d(o oVar, m mVar) {
        if (oVar.a != null) {
            if (!com.google.android.vending.expansion.downloader.l.b(oVar.a)) {
                throw new p(this, 492, "found invalid internal destination filename");
            }
            File file = new File(oVar.a);
            if (file.exists()) {
                long length = file.length();
                if (length == 0) {
                    file.delete();
                    oVar.a = null;
                } else {
                    if (this.b.d == null) {
                        file.delete();
                        throw new p(this, 489, "Trying to resume a download that can't be resumed");
                    }
                    try {
                        oVar.b = new FileOutputStream(oVar.a, true);
                        mVar.a = (int) length;
                        if (this.b.e != -1) {
                            mVar.e = Long.toString(this.b.e);
                        }
                        mVar.c = this.b.d;
                        mVar.d = true;
                    } catch (FileNotFoundException e) {
                        throw new p(this, 492, "while opening destination for resuming: " + e.toString(), e);
                    }
                }
            }
        }
        if (oVar.b != null) {
            d(oVar);
        }
    }

    private void a(int i, boolean z, int i2, int i3, boolean z2, String str) {
        b(i, z, i2, i3, z2, str);
        if (DownloaderService.c(i)) {
        }
    }

    private void b(int i, boolean z, int i2, int i3, boolean z2, String str) {
        this.b.h = i;
        this.b.k = i2;
        this.b.l = i3;
        this.b.g = System.currentTimeMillis();
        if (!z) {
            this.b.j = 0;
        } else if (z2) {
            this.b.j = 1;
        } else {
            this.b.j++;
        }
        this.d.c(this.b);
    }
}
