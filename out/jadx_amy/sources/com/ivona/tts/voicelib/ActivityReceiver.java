package com.ivona.tts.voicelib;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.util.Log;

/* loaded from: classes.dex */
public class ActivityReceiver extends BroadcastReceiver {
    private Thread a;

    @Override // android.content.BroadcastReceiver
    public void onReceive(Context context, Intent intent) {
        int i;
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("ActivityReceiver", "onReceive: " + this.a);
        }
        if (!a(context) && this.a == null) {
            Bundle extras = intent.getExtras();
            if (extras == null || !extras.containsKey("android.intent.extra.UID")) {
                i = -1;
            } else {
                i = extras.getInt("android.intent.extra.UID");
                if (com.ivona.tts.commonlib.a.c) {
                    Log.d("ActivityReceiver", "onReceive got uid: " + i);
                }
            }
            if (i != -1 && com.ivona.tts.commonlib.c.a(context, i, "com.ivona.tts")) {
                if (com.ivona.tts.commonlib.a.c) {
                    Log.d("ActivityReceiver", "com.ivona.tts intent not available but is on installed list");
                }
                this.a = new Thread(new a(context.getApplicationContext()));
                this.a.start();
                return;
            }
            return;
        }
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("ActivityReceiver", "onReceive - com.ivona.tts available");
        }
        Intent intent2 = new Intent();
        intent2.setClassName("com.ivona.tts", "com.ivona.ttslib.engine.TTSServiceActivation");
        context.startService(intent2);
    }

    public static boolean a(Context context) {
        Intent intent = new Intent();
        intent.setClassName("com.ivona.tts", "com.ivona.ttslib.CustomSettingsService");
        intent.putExtra("upkgmon", true);
        if (!com.ivona.tts.commonlib.c.b(context, intent)) {
            return false;
        }
        context.startService(intent);
        return true;
    }
}
