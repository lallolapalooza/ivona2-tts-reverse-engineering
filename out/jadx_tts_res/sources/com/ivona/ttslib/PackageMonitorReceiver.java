package com.ivona.ttslib;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;
import com.ivona.ttslib.engine.TTSServiceActivation;

/* loaded from: classes.dex */
public class PackageMonitorReceiver extends BroadcastReceiver {
    @Override // android.content.BroadcastReceiver
    public void onReceive(Context context, Intent intent) {
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("PackageMonitorReceiver", "onReceive");
        }
        context.startService(new Intent(context, (Class<?>) TTSServiceActivation.class));
        Intent intent2 = new Intent(context, (Class<?>) CustomSettingsService.class);
        intent2.putExtra("upkgmon", true);
        context.startService(intent2);
    }
}
