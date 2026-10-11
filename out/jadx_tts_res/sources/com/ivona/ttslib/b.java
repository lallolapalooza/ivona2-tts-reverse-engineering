package com.ivona.ttslib;

import android.content.ComponentName;
import android.content.Intent;
import android.preference.Preference;

/* compiled from: DownloadVoiceData.java */
/* loaded from: classes.dex */
class b implements Preference.OnPreferenceClickListener {
    final /* synthetic */ com.ivona.ttslib.packages.a a;
    final /* synthetic */ DownloadVoiceData b;

    b(DownloadVoiceData downloadVoiceData, com.ivona.ttslib.packages.a aVar) {
        this.b = downloadVoiceData;
        this.a = aVar;
    }

    @Override // android.preference.Preference.OnPreferenceClickListener
    public boolean onPreferenceClick(Preference preference) {
        boolean a;
        Intent intent = new Intent("android.intent.action.MAIN");
        intent.setComponent(ComponentName.unflattenFromString(this.a.c() + "/.IvonaVoice"));
        intent.addCategory("android.intent.category.LAUNCHER");
        a = this.b.a(intent);
        if (!a) {
            intent.setComponent(ComponentName.unflattenFromString(this.a.c() + "/.IvonaKendra"));
        }
        this.b.startActivity(intent);
        this.b.finish();
        return true;
    }
}
