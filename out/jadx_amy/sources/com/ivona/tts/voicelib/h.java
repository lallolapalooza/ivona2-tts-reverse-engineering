package com.ivona.tts.voicelib;

import android.content.Intent;
import android.net.Uri;
import android.view.View;

/* compiled from: IvonaVoice.java */
/* loaded from: classes.dex */
class h implements View.OnClickListener {
    final /* synthetic */ IvonaVoice a;

    h(IvonaVoice ivonaVoice) {
        this.a = ivonaVoice;
    }

    @Override // android.view.View.OnClickListener
    public void onClick(View view) {
        boolean k;
        String str = "market://details?id=com.google.tts";
        k = this.a.k();
        if (k) {
            str = "http://eyes-free.googlecode.com/files/tts_3.1_market.apk";
        }
        Intent intent = new Intent("android.intent.action.VIEW");
        intent.setData(Uri.parse(str));
        this.a.startActivity(intent);
    }
}
