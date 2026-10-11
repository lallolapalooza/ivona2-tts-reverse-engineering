package com.ivona.ttslib.ics;

import android.os.Handler;
import android.os.Message;
import android.util.Log;

/* compiled from: IVONATextToSpeechService.java */
/* loaded from: classes.dex */
final class a extends Handler {
    a() {
    }

    @Override // android.os.Handler
    public void handleMessage(Message message) {
        NativeIVONAEngineICS nativeIVONAEngineICS;
        String[] strArr;
        String[] strArr2;
        String[] strArr3;
        String[] strArr4;
        super.handleMessage(message);
        switch (message.what) {
            case 1:
                if (com.ivona.tts.commonlib.a.c) {
                    Log.d("IVONATextToSpeechService", "MSG_INIT");
                }
                nativeIVONAEngineICS = IVONATextToSpeechService.ivonaEngine;
                nativeIVONAEngineICS.create();
                strArr = IVONATextToSpeechService.initLanguage;
                if (strArr != null) {
                    strArr2 = IVONATextToSpeechService.initLanguage;
                    String str = strArr2[0];
                    strArr3 = IVONATextToSpeechService.initLanguage;
                    String str2 = strArr3[1];
                    strArr4 = IVONATextToSpeechService.initLanguage;
                    IVONATextToSpeechService.loadLanguage(str, str2, strArr4[2], true);
                    String[] unused = IVONATextToSpeechService.initLanguage = null;
                }
                IVONATextToSpeechService.engineCreatedSignal.countDown();
                break;
        }
    }
}
