package com.ivona.ttslib.ics;

import android.speech.tts.SynthesisCallback;
import android.speech.tts.SynthesisRequest;
import android.util.Log;
import com.google.tts.TextToSpeechBeta;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;

/* loaded from: classes.dex */
public class NativeIVONAEngineICS extends NativeIVONAEngine {
    private static final String GENERATE_MARKS_PARAM_KEY = "com.ivona.tts.oem.GENERATE_MARKS";
    private static final String SET_CONTRAST = "com.ivona.tts.oem.SET_CONTRAST";
    private static final String TAG = "NativeIVONAEngineICS";
    private static int TTS_SYNTH_DONE = 0;
    private static com.ivona.ttslib.engine.a cpuBenchmark;
    Method audioAvailableWithMarks;
    private SynthesisCallback callback = null;
    private byte[] audioBuffer = null;
    private int audioBufferSize = 0;
    List marks = null;

    private native int setProperty(String str, String str2);

    private native int synthesizeText(String str, byte[] bArr);

    private native int synthesizeText(String str, byte[] bArr, List list, int i);

    public NativeIVONAEngineICS() {
        if (com.ivona.tts.commonlib.a.d) {
            cpuBenchmark = new com.ivona.ttslib.engine.a();
            cpuBenchmark.start();
        }
    }

    public int audioAvailableClbk(int i, int i2) {
        if (this.callback == null) {
            return -1;
        }
        if (i2 == TTS_SYNTH_DONE) {
            return 1;
        }
        if (com.ivona.tts.commonlib.a.c) {
            Log.d(TAG, "aaclbk: ab:" + this.audioBuffer.toString() + " length: " + i + " status: " + i2);
        }
        if (i > 0) {
            if (this.marks != null && this.audioAvailableWithMarks != null) {
                try {
                    this.audioAvailableWithMarks.invoke(this.callback, this.audioBuffer, 0, Integer.valueOf(i), this.marks);
                } catch (Exception e) {
                    e.printStackTrace();
                    this.callback.audioAvailable(this.audioBuffer, 0, i);
                }
            } else {
                this.callback.audioAvailable(this.audioBuffer, 0, i);
            }
        }
        return 0;
    }

    public void speak(SynthesisRequest synthesisRequest, SynthesisCallback synthesisCallback) {
        int i = 0;
        int i2 = 1;
        this.callback = synthesisCallback;
        synthesisCallback.start(getSampleRate(), 2, 1);
        int maxBufferSize = synthesisCallback.getMaxBufferSize();
        if (this.audioBufferSize < maxBufferSize) {
            this.audioBuffer = new byte[maxBufferSize];
            this.audioBufferSize = maxBufferSize;
        }
        setProperty(TextToSpeechBeta.Engine.KEY_PARAM_RATE, String.valueOf(synthesisRequest.getSpeechRate()));
        setProperty(TextToSpeechBeta.Engine.KEY_PARAM_PITCH, String.valueOf(synthesisRequest.getPitch()));
        try {
            i = Integer.parseInt(synthesisRequest.getParams().getString(GENERATE_MARKS_PARAM_KEY));
        } catch (Exception e) {
        }
        try {
            i2 = Integer.parseInt(synthesisRequest.getParams().getString(SET_CONTRAST));
        } catch (Exception e2) {
        }
        if (com.ivona.tts.commonlib.a.c) {
            Log.d(TAG, "setContrast: " + i2);
        }
        if (i > 0) {
            try {
                this.audioAvailableWithMarks = synthesisCallback.getClass().getMethod("audioAvailable", byte[].class, Integer.TYPE, Integer.TYPE, List.class);
                if (this.marks == null) {
                    this.marks = new ArrayList();
                }
                if (com.ivona.tts.commonlib.a.d) {
                    cpuBenchmark.b();
                }
                synthesizeText(synthesisRequest.getText(), this.audioBuffer, this.marks, i);
                if (com.ivona.tts.commonlib.a.d) {
                    cpuBenchmark.a();
                }
            } catch (NoSuchMethodException e3) {
                e3.printStackTrace();
                if (com.ivona.tts.commonlib.a.d) {
                    cpuBenchmark.b();
                }
                synthesizeText(synthesisRequest.getText(), this.audioBuffer);
                if (com.ivona.tts.commonlib.a.d) {
                    cpuBenchmark.a();
                }
            }
        } else {
            if (com.ivona.tts.commonlib.a.d) {
                cpuBenchmark.b();
            }
            synthesizeText(synthesisRequest.getText(), this.audioBuffer);
            if (com.ivona.tts.commonlib.a.d) {
                cpuBenchmark.a();
            }
        }
        synthesisCallback.done();
        this.callback = null;
    }
}
