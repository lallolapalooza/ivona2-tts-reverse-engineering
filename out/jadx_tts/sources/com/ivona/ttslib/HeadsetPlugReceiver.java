package com.ivona.ttslib;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;
import com.ivona.ttslib.ics.IVONATextToSpeechService;

/* loaded from: classes.dex */
public class HeadsetPlugReceiver extends BroadcastReceiver {
    @Override // android.content.BroadcastReceiver
    public void onReceive(Context context, Intent intent) {
        if (com.ivona.tts.commonlib.a.c) {
            if (intent.hasExtra("state")) {
                Log.d("HeadsetPlugReceiver", "onReceive - state " + intent.getIntExtra("state", 0));
            } else {
                Log.d("HeadsetPlugReceiver", "onReceive - no state");
            }
        }
        if (intent.hasExtra("state")) {
            IVONATextToSpeechService.setContrast(intent.getIntExtra("state", 0) == 0);
        }
    }
}
