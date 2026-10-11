package com.ivona.tts.voicelib;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import com.ivona.tts.commonlib.AppLib;
import java.io.IOException;

/* loaded from: classes.dex */
public abstract class CheckVoiceInstalled extends Activity {
    protected abstract String a();

    @Override // android.app.Activity
    public void onCreate(Bundle bundle) {
        super.onCreate(bundle);
        Intent intent = new Intent();
        try {
            try {
                byte[] byteArrayExtra = getIntent().getByteArrayExtra("checkVoice");
                com.ivona.tts.commonlib.a.f fVar = com.ivona.tts.commonlib.a.f.VOICE_NOT_INSTALLED;
                com.ivona.tts.commonlib.a.c a = com.ivona.tts.commonlib.a.c.a(byteArrayExtra);
                if (com.ivona.tts.commonlib.a.c) {
                    Log.d(a(), "Received request: libvoice" + a.c() + " code: " + a.a().toString());
                }
                com.ivona.tts.commonlib.a.f fVar2 = (a.c().equals(((AppLib) getApplicationContext()).a()) && a.a() == com.ivona.tts.commonlib.a.d.CHECK_VOICE_INSTALLED && b()) ? com.ivona.tts.commonlib.a.f.VOICE_INSTALLED : fVar;
                if (com.ivona.tts.commonlib.a.c) {
                    Log.d(a(), "Response code is " + fVar2.toString());
                }
                intent.putExtra("checkVoiceResult", new com.ivona.tts.commonlib.a.e(a, fVar2).a());
                if (com.ivona.tts.commonlib.a.c) {
                    Log.i(a(), "finishing activity");
                }
                setResult(0, intent);
                finish();
            } catch (IOException e) {
                if (com.ivona.tts.commonlib.a.c) {
                    Log.e(a(), "Checking voice data failed: " + e.getMessage());
                }
                if (com.ivona.tts.commonlib.a.c) {
                    Log.i(a(), "finishing activity");
                }
                setResult(0, intent);
                finish();
            }
        } catch (Throwable th) {
            if (com.ivona.tts.commonlib.a.c) {
                Log.i(a(), "finishing activity");
            }
            setResult(0, intent);
            finish();
            throw th;
        }
    }

    @Override // android.app.Activity
    public void onPause() {
        super.onPause();
        if (com.ivona.tts.commonlib.a.c) {
            Log.i(a(), "Entered onPause()");
        }
    }

    private boolean b() {
        if (com.ivona.tts.commonlib.a.c) {
            Log.d(a(), "Voice is installed");
            return true;
        }
        return true;
    }

    @Override // android.app.Activity
    public void onDestroy() {
        super.onDestroy();
        if (com.ivona.tts.commonlib.a.c) {
            Log.i(a(), "Entered onDestroy()");
        }
    }

    @Override // android.app.Activity
    public void onResume() {
        super.onResume();
        if (com.ivona.tts.commonlib.a.c) {
            Log.i(a(), "Entered onResume()");
        }
    }
}
