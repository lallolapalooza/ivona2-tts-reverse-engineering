package com.ivona.tts.voicelib;

import android.view.View;

/* compiled from: IvonaVoice.java */
/* loaded from: classes.dex */
class d implements View.OnClickListener {
    final /* synthetic */ IvonaVoice a;

    d(IvonaVoice ivonaVoice) {
        this.a = ivonaVoice;
    }

    @Override // android.view.View.OnClickListener
    public void onClick(View view) {
        boolean z;
        com.google.android.vending.expansion.downloader.n nVar;
        boolean z2;
        com.google.android.vending.expansion.downloader.n nVar2;
        z = this.a.c;
        if (z) {
            nVar2 = this.a.d;
            nVar2.c();
        } else {
            nVar = this.a.d;
            nVar.b();
        }
        IvonaVoice ivonaVoice = this.a;
        z2 = this.a.c;
        ivonaVoice.a(!z2);
    }
}
