package com.ivona.ttslib;

import android.content.DialogInterface;
import android.content.Intent;

/* compiled from: IvonaGui.java */
/* loaded from: classes.dex */
class k implements DialogInterface.OnClickListener {
    final /* synthetic */ IvonaGui a;

    k(IvonaGui ivonaGui) {
        this.a = ivonaGui;
    }

    @Override // android.content.DialogInterface.OnClickListener
    public void onClick(DialogInterface dialogInterface, int i) {
        Intent intent;
        if (com.ivona.tts.commonlib.b.c() && com.ivona.tts.commonlib.b.g()) {
            intent = new Intent();
            intent.setAction("android.settings.SETTINGS");
        } else if (com.ivona.tts.commonlib.b.c()) {
            intent = new Intent();
            intent.setAction("com.android.settings.TTS_SETTINGS");
        } else if (com.ivona.tts.commonlib.b.d()) {
            intent = new Intent();
            intent.setAction("android.settings.SETTINGS");
        } else if (com.ivona.tts.commonlib.b.f()) {
            intent = new Intent();
            intent.setAction("com.android.settings.VOICE_INPUT_OUTPUT_SETTINGS");
        } else if (com.ivona.tts.commonlib.b.b()) {
            intent = new Intent();
            intent.setClassName("com.google.tts", "com.google.tts.ConfigurationManager");
        } else {
            intent = new Intent("android.intent.action.MAIN");
            intent.setClassName("com.android.settings", "com.android.settings.TextToSpeechSettings");
        }
        com.ivona.tts.commonlib.b.b(this.a, intent);
    }
}
