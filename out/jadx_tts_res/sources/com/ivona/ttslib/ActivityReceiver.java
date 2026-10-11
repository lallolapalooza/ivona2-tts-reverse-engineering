package com.ivona.ttslib;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;
import com.ivona.ttslib.engine.TTSServiceActivation;

/* loaded from: classes.dex */
public class ActivityReceiver extends BroadcastReceiver {
    @Override // android.content.BroadcastReceiver
    public void onReceive(Context context, Intent intent) {
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("ActivityReceiver", "onReceive");
        }
        context.startService(new Intent(context, (Class<?>) TTSServiceActivation.class));
    }
}
