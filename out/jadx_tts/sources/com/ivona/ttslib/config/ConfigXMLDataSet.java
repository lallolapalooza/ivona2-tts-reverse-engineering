package com.ivona.ttslib.config;

import android.util.Log;
import com.ivona.tts.commonlib.a;

/* loaded from: classes.dex */
public class ConfigXMLDataSet {
    private static String[] a;
    private static String[] b;

    private static native String[] getPackagesCfg();

    private static native String[] getSettingsCfg();

    static {
        String str;
        if (a.c) {
            Log.d("ConfigXMLDataSet", "loading XML config");
        }
        System.loadLibrary("ttsivona");
        a = getSettingsCfg();
        b = getPackagesCfg();
        if (a.c) {
            String str2 = (a != null ? "XML config loaded - settingsCfg:" + a.length : "XML config loaded - settingsCfg:0 ") + " packageCfg:";
            if (b != null) {
                str = str2 + b.length;
            } else {
                str = str2 + "0";
            }
            Log.d("ConfigXMLDataSet", str);
        }
    }

    public final String[] a() {
        return b;
    }
}
