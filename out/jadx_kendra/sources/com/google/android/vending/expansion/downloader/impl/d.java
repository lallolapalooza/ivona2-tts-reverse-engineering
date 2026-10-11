package com.google.android.vending.expansion.downloader.impl;

import org.apache.http.HttpRequest;
import org.apache.http.HttpRequestInterceptor;
import org.apache.http.client.methods.HttpUriRequest;
import org.apache.http.protocol.HttpContext;

/* compiled from: AndroidHttpClient.java */
/* loaded from: classes.dex */
class d implements HttpRequestInterceptor {
    final /* synthetic */ a a;

    private d(a aVar) {
        this.a = aVar;
    }

    /* synthetic */ d(a aVar, b bVar) {
        this(aVar);
    }

    @Override // org.apache.http.HttpRequestInterceptor
    public void process(HttpRequest httpRequest, HttpContext httpContext) {
        e eVar;
        boolean a;
        String b;
        eVar = this.a.f;
        if (eVar != null) {
            a = eVar.a();
            if (a && (httpRequest instanceof HttpUriRequest)) {
                b = a.b((HttpUriRequest) httpRequest, false);
                eVar.a(b);
            }
        }
    }
}
