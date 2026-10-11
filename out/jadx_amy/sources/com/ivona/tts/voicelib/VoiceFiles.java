package com.ivona.tts.voicelib;

import android.content.Context;
import android.os.Environment;
import android.util.Log;
import java.io.File;

/* loaded from: classes.dex */
public class VoiceFiles {
    private static native int checkFiles(String str, String str2);

    static {
        System.loadLibrary("tiver");
    }

    public static boolean a(Context context) {
        String name = context.getApplicationContext().getClass().getName();
        String substring = name.substring(0, name.lastIndexOf("."));
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("VoiceFiles", "cls name:" + substring);
        }
        int length = substring.length();
        for (int i = 0; i < 3 && length != -1; i++) {
            length = substring.lastIndexOf(46, length - 1);
        }
        String substring2 = substring.substring(length + 1);
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("VoiceFiles", "finding pkg:" + substring2);
        }
        q a = q.a(substring2);
        String absolutePath = Environment.getExternalStorageDirectory().getAbsolutePath();
        if (a != null) {
            if (com.ivona.tts.commonlib.a.c) {
                Log.d("VoiceFiles", "Checking old files:" + a.a() + ", " + a.b());
            }
            File file = new File(absolutePath + "/ivona/" + a.a());
            if (file.exists()) {
                if (com.ivona.tts.commonlib.a.c) {
                    Log.d("VoiceFiles", "Old vox exists... deleting.");
                }
                file.delete();
            }
            File file2 = new File(absolutePath + "/ivona/" + a.b());
            if (file2.exists()) {
                if (com.ivona.tts.commonlib.a.c) {
                    Log.d("VoiceFiles", "Old lang.dat exists... deleting.");
                }
                file2.delete();
            }
        }
        int checkFiles = checkFiles(substring, absolutePath + "/");
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("VoiceFiles", "checkFiles res:" + checkFiles);
        }
        return checkFiles == 0;
    }
}
