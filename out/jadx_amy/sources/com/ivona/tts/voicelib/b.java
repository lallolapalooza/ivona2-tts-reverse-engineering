package com.ivona.tts.voicelib;

import android.view.View;

/* compiled from: IvonaVoice.java */
/* loaded from: classes.dex */
class b implements View.OnClickListener {
    final /* synthetic */ IvonaVoice a;

    b(IvonaVoice ivonaVoice) {
        this.a = ivonaVoice;
    }

    @Override // android.view.View.OnClickListener
    public void onClick(View view) {
        com.google.android.vending.expansion.downloader.n nVar;
        com.google.android.vending.expansion.downloader.n nVar2;
        View view2;
        nVar = this.a.d;
        nVar.a(1);
        nVar2 = this.a.d;
        nVar2.c();
        view2 = this.a.l;
        view2.setVisibility(8);
    }
}
