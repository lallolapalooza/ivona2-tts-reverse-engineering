package com.ivona.tts.voicebeta.pol.pol.maja;

import android.content.Context;
import android.content.Intent;
import com.ivona.tts.voicelib.UpdateReceiverLib;

/* loaded from: classes.dex */
public class UpdateReceiver extends UpdateReceiverLib {
    @Override // com.ivona.tts.voicelib.UpdateReceiverLib
    protected Intent a(Context context) {
        Intent intent = new Intent();
        intent.setClass(context, IvonaVoice.class);
        return intent;
    }
}
