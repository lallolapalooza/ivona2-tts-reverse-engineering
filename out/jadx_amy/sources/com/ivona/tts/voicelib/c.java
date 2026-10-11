package com.ivona.tts.voicelib;

import android.content.Intent;
import android.view.View;

/* compiled from: IvonaVoice.java */
/* loaded from: classes.dex */
class c implements View.OnClickListener {
    final /* synthetic */ IvonaVoice a;

    c(IvonaVoice ivonaVoice) {
        this.a = ivonaVoice;
    }

    @Override // android.view.View.OnClickListener
    public void onClick(View view) {
        this.a.startActivity(new Intent("android.settings.WIFI_SETTINGS"));
    }
}
