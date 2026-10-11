package com.ivona.tts.voicelib;

import android.content.DialogInterface;

/* compiled from: IvonaVoice.java */
/* loaded from: classes.dex */
class f implements DialogInterface.OnClickListener {
    final /* synthetic */ IvonaVoice a;

    f(IvonaVoice ivonaVoice) {
        this.a = ivonaVoice;
    }

    @Override // android.content.DialogInterface.OnClickListener
    public void onClick(DialogInterface dialogInterface, int i) {
        this.a.finish();
    }
}
