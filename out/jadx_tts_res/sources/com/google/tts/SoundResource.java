package com.google.tts;

/* loaded from: classes.dex */
public class SoundResource {
    public String filename;
    public int resId;
    public String sourcePackageName;

    public SoundResource(String str, int i) {
        this.sourcePackageName = str;
        this.resId = i;
        this.filename = null;
    }

    public SoundResource(String str) {
        this.sourcePackageName = null;
        this.resId = -1;
        this.filename = str;
    }
}
