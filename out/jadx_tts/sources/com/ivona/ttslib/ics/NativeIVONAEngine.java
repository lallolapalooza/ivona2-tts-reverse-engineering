package com.ivona.ttslib.ics;

import android.util.Log;
import java.util.StringTokenizer;

/* loaded from: classes.dex */
public class NativeIVONAEngine {
    private static final String TAG = "NativeIVONAEngine";

    public static native void setEnvRuntime(String str, String str2);

    public native void create();

    public native void destroy();

    public native int getSampleRate();

    public native String[] getVersion();

    public native String[] onGetLanguage();

    public native int onLoadLanguage(String str, String str2, String str3);

    protected native int setContrast(int i);

    public native void stop();

    static {
        StringTokenizer stringTokenizer = new StringTokenizer(System.getProperty("java.library.path"), ";");
        while (stringTokenizer.hasMoreTokens()) {
            Log.d(TAG, "path: " + stringTokenizer.nextToken());
        }
        System.loadLibrary("ttsivona");
    }
}
