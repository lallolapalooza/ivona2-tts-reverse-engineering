package com.google.tts;

/* loaded from: classes.dex */
public enum TTSParams {
    VOICE_MALE,
    VOICE_FEMALE,
    VOICE_ROBOT;

    /* renamed from: values, reason: to resolve conflict with enum method */
    public static TTSParams[] valuesCustom() {
        TTSParams[] valuesCustom = values();
        int length = valuesCustom.length;
        TTSParams[] tTSParamsArr = new TTSParams[length];
        System.arraycopy(valuesCustom, 0, tTSParamsArr, 0, length);
        return tTSParamsArr;
    }
}
