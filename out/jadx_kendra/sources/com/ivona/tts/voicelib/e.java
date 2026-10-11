package com.ivona.tts.voicelib;

import android.webkit.WebView;
import android.webkit.WebViewClient;

/* compiled from: IvonaVoice.java */
/* loaded from: classes.dex */
class e extends WebViewClient {
    final /* synthetic */ IvonaVoice a;

    e(IvonaVoice ivonaVoice) {
        this.a = ivonaVoice;
    }

    @Override // android.webkit.WebViewClient
    public void onPageFinished(WebView webView, String str) {
        this.a.showDialog(10);
    }
}
