package com.ivona.tts.voicelib;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.view.View;
import android.widget.Toast;

/* compiled from: IvonaVoice.java */
/* loaded from: classes.dex */
class i implements View.OnClickListener {
    final /* synthetic */ IvonaVoice a;

    i(IvonaVoice ivonaVoice) {
        this.a = ivonaVoice;
    }

    @Override // android.view.View.OnClickListener
    public void onClick(View view) {
        Intent intent = new Intent("android.intent.action.VIEW");
        intent.setData(Uri.parse("market://details?id=com.ivona.tts"));
        try {
            this.a.startActivity(intent);
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this.a, p.k, 1).show();
        }
    }
}
