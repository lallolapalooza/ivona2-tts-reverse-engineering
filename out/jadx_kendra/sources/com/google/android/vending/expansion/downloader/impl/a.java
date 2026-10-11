package com.google.android.vending.expansion.downloader.impl;

import android.util.Log;
import org.apache.http.HttpHost;
import org.apache.http.HttpRequest;
import org.apache.http.HttpRequestInterceptor;
import org.apache.http.HttpResponse;
import org.apache.http.client.HttpClient;
import org.apache.http.client.ResponseHandler;
import org.apache.http.client.methods.HttpUriRequest;
import org.apache.http.conn.ClientConnectionManager;
import org.apache.http.params.HttpParams;
import org.apache.http.protocol.HttpContext;

/* compiled from: AndroidHttpClient.java */
/* loaded from: classes.dex */
public final class a implements HttpClient {
    static Class a;
    public static long b;
    private static final HttpRequestInterceptor c;
    private final HttpClient d;
    private RuntimeException e = new IllegalStateException("AndroidHttpClient created and never closed");
    private volatile e f;

    static {
        try {
            a = Class.forName("android.net.SSLSessionCache");
        } catch (Exception e) {
        }
        b = 256L;
        c = new b();
    }

    /* JADX WARN: Removed duplicated region for block: B:11:0x0081  */
    /* JADX WARN: Removed duplicated region for block: B:15:0x0053 A[EXC_TOP_SPLITTER, SYNTHETIC] */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static com.google.android.vending.expansion.downloader.impl.a a(java.lang.String r9, android.content.Context r10) {
        /*
            Method dump skipped, instructions count: 223
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: com.google.android.vending.expansion.downloader.impl.a.a(java.lang.String, android.content.Context):com.google.android.vending.expansion.downloader.impl.a");
    }

    private a(ClientConnectionManager clientConnectionManager, HttpParams httpParams) {
        this.d = new c(this, clientConnectionManager, httpParams);
    }

    protected void finalize() {
        super.finalize();
        if (this.e != null) {
            Log.e("AndroidHttpClient", "Leak found", this.e);
            this.e = null;
        }
    }

    public void a() {
        if (this.e != null) {
            getConnectionManager().shutdown();
            this.e = null;
        }
    }

    @Override // org.apache.http.client.HttpClient
    public HttpParams getParams() {
        return this.d.getParams();
    }

    @Override // org.apache.http.client.HttpClient
    public ClientConnectionManager getConnectionManager() {
        return this.d.getConnectionManager();
    }

    @Override // org.apache.http.client.HttpClient
    public HttpResponse execute(HttpUriRequest httpUriRequest) {
        return this.d.execute(httpUriRequest);
    }

    @Override // org.apache.http.client.HttpClient
    public HttpResponse execute(HttpUriRequest httpUriRequest, HttpContext httpContext) {
        return this.d.execute(httpUriRequest, httpContext);
    }

    @Override // org.apache.http.client.HttpClient
    public HttpResponse execute(HttpHost httpHost, HttpRequest httpRequest) {
        return this.d.execute(httpHost, httpRequest);
    }

    @Override // org.apache.http.client.HttpClient
    public HttpResponse execute(HttpHost httpHost, HttpRequest httpRequest, HttpContext httpContext) {
        return this.d.execute(httpHost, httpRequest, httpContext);
    }

    @Override // org.apache.http.client.HttpClient
    public Object execute(HttpUriRequest httpUriRequest, ResponseHandler responseHandler) {
        return this.d.execute(httpUriRequest, responseHandler);
    }

    @Override // org.apache.http.client.HttpClient
    public Object execute(HttpUriRequest httpUriRequest, ResponseHandler responseHandler, HttpContext httpContext) {
        return this.d.execute(httpUriRequest, responseHandler, httpContext);
    }

    @Override // org.apache.http.client.HttpClient
    public Object execute(HttpHost httpHost, HttpRequest httpRequest, ResponseHandler responseHandler) {
        return this.d.execute(httpHost, httpRequest, responseHandler);
    }

    @Override // org.apache.http.client.HttpClient
    public Object execute(HttpHost httpHost, HttpRequest httpRequest, ResponseHandler responseHandler, HttpContext httpContext) {
        return this.d.execute(httpHost, httpRequest, responseHandler, httpContext);
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* JADX WARN: Removed duplicated region for block: B:28:0x0089  */
    /* JADX WARN: Removed duplicated region for block: B:29:0x00a9  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static java.lang.String b(org.apache.http.client.methods.HttpUriRequest r7, boolean r8) {
        /*
            java.lang.StringBuilder r2 = new java.lang.StringBuilder
            r2.<init>()
            java.lang.String r0 = "curl "
            r2.append(r0)
            org.apache.http.Header[] r1 = r7.getAllHeaders()
            int r3 = r1.length
            r0 = 0
        L10:
            if (r0 >= r3) goto L47
            r4 = r1[r0]
            if (r8 != 0) goto L31
            java.lang.String r5 = r4.getName()
            java.lang.String r6 = "Authorization"
            boolean r5 = r5.equals(r6)
            if (r5 != 0) goto L2e
            java.lang.String r5 = r4.getName()
            java.lang.String r6 = "Cookie"
            boolean r5 = r5.equals(r6)
            if (r5 == 0) goto L31
        L2e:
            int r0 = r0 + 1
            goto L10
        L31:
            java.lang.String r5 = "--header \""
            r2.append(r5)
            java.lang.String r4 = r4.toString()
            java.lang.String r4 = r4.trim()
            r2.append(r4)
            java.lang.String r4 = "\" "
            r2.append(r4)
            goto L2e
        L47:
            java.net.URI r1 = r7.getURI()
            boolean r0 = r7 instanceof org.apache.http.impl.client.RequestWrapper
            if (r0 == 0) goto Laf
            r0 = r7
            org.apache.http.impl.client.RequestWrapper r0 = (org.apache.http.impl.client.RequestWrapper) r0
            org.apache.http.HttpRequest r0 = r0.getOriginal()
            boolean r3 = r0 instanceof org.apache.http.client.methods.HttpUriRequest
            if (r3 == 0) goto Laf
            org.apache.http.client.methods.HttpUriRequest r0 = (org.apache.http.client.methods.HttpUriRequest) r0
            java.net.URI r0 = r0.getURI()
        L60:
            java.lang.String r1 = "\""
            r2.append(r1)
            r2.append(r0)
            java.lang.String r0 = "\""
            r2.append(r0)
            boolean r0 = r7 instanceof org.apache.http.HttpEntityEnclosingRequest
            if (r0 == 0) goto La4
            org.apache.http.HttpEntityEnclosingRequest r7 = (org.apache.http.HttpEntityEnclosingRequest) r7
            org.apache.http.HttpEntity r0 = r7.getEntity()
            if (r0 == 0) goto La4
            boolean r1 = r0.isRepeatable()
            if (r1 == 0) goto La4
            long r3 = r0.getContentLength()
            r5 = 1024(0x400, double:5.06E-321)
            int r1 = (r3 > r5 ? 1 : (r3 == r5 ? 0 : -1))
            if (r1 >= 0) goto La9
            java.io.ByteArrayOutputStream r1 = new java.io.ByteArrayOutputStream
            r1.<init>()
            r0.writeTo(r1)
            java.lang.String r0 = r1.toString()
            java.lang.String r1 = " --data-ascii \""
            java.lang.StringBuilder r1 = r2.append(r1)
            java.lang.StringBuilder r0 = r1.append(r0)
            java.lang.String r1 = "\""
            r0.append(r1)
        La4:
            java.lang.String r0 = r2.toString()
            return r0
        La9:
            java.lang.String r0 = " [TOO MUCH DATA TO INCLUDE]"
            r2.append(r0)
            goto La4
        Laf:
            r0 = r1
            goto L60
        */
        throw new UnsupportedOperationException("Method not decompiled: com.google.android.vending.expansion.downloader.impl.a.b(org.apache.http.client.methods.HttpUriRequest, boolean):java.lang.String");
    }
}
