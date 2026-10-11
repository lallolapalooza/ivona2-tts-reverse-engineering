package com.ivona.tts.voicelib;

import android.content.Context;
import android.util.Log;

/* compiled from: ActivityReceiver.java */
/* loaded from: classes.dex */
class a implements Runnable {
    private final Context a;

    a(Context context) {
        this.a = context;
    }

    @Override // java.lang.Runnable
    public void run() {
        do {
            try {
                if (com.ivona.tts.commonlib.a.c) {
                    Log.d("ActivityReceiver", "waiting");
                }
                Thread.sleep(300L);
            } catch (InterruptedException e) {
                if (com.ivona.tts.commonlib.a.c) {
                    e.printStackTrace();
                }
                Log.e("ActivityReceiver", "Failed to send update data");
                return;
            }
        } while (!ActivityReceiver.a(this.a));
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("ActivityReceiver", "update was sent");
        }
    }
}
