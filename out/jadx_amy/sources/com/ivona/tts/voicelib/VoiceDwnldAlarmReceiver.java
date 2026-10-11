package com.ivona.tts.voicelib;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;

/* loaded from: classes.dex */
public class VoiceDwnldAlarmReceiver extends BroadcastReceiver {
    @Override // android.content.BroadcastReceiver
    public void onReceive(Context context, Intent intent) {
        try {
            com.google.android.vending.expansion.downloader.c.a(context, intent, VoiceDownloaderService.class);
        } catch (PackageManager.NameNotFoundException e) {
            if (com.ivona.tts.commonlib.a.c) {
                e.printStackTrace();
            }
        }
    }
}
