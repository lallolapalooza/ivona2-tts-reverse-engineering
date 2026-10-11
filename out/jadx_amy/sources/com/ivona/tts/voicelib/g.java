package com.ivona.tts.voicelib;

import android.content.DialogInterface;
import android.content.SharedPreferences;

/* compiled from: IvonaVoice.java */
/* loaded from: classes.dex */
class g implements DialogInterface.OnClickListener {
    final /* synthetic */ IvonaVoice a;

    g(IvonaVoice ivonaVoice) {
        this.a = ivonaVoice;
    }

    @Override // android.content.DialogInterface.OnClickListener
    public void onClick(DialogInterface dialogInterface, int i) {
        SharedPreferences sharedPreferences;
        sharedPreferences = this.a.a;
        SharedPreferences.Editor edit = sharedPreferences.edit();
        edit.putInt("agr_int_ver", this.a.getResources().getInteger(n.a));
        edit.commit();
        this.a.b(true);
    }
}
