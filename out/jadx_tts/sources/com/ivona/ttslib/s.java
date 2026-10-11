package com.ivona.ttslib;

import android.speech.tts.TextToSpeech;

/* compiled from: IvonaGui.java */
/* loaded from: classes.dex */
class s implements TextToSpeech.OnInitListener {
    final /* synthetic */ IvonaGui a;

    s(IvonaGui ivonaGui) {
        this.a = ivonaGui;
    }

    @Override // android.speech.tts.TextToSpeech.OnInitListener
    public void onInit(int i) {
        this.a.f = i;
        this.a.d();
    }
}
