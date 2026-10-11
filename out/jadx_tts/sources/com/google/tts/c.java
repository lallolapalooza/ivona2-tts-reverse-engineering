package com.google.tts;

import android.speech.tts.TextToSpeech;

/* compiled from: TextToSpeechBeta.java */
/* loaded from: classes.dex */
class c implements TextToSpeech.OnInitListener {
    c() {
    }

    @Override // android.speech.tts.TextToSpeech.OnInitListener
    public void onInit(int i) {
        if (!TextToSpeechBeta.ttsBetaInstalled && TextToSpeechBeta.mInitListener != null) {
            TextToSpeechBeta.mInitListener.a(i, -1);
        }
    }
}
