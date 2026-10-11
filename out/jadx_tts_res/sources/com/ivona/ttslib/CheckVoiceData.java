package com.ivona.ttslib;

import android.app.Activity;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import com.google.tts.TextToSpeechBeta;
import com.ivona.ttslib.config.ConfigXMLDataSet;
import com.ivona.ttslib.packages.IvonaPackagesInfo;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Iterator;

/* loaded from: classes.dex */
public class CheckVoiceData extends Activity {
    @Override // android.app.Activity
    public void onCreate(Bundle bundle) {
        super.onCreate(bundle);
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("CheckVoiceData", "onCreate");
        }
        a();
        ArrayList<String> arrayList = new ArrayList<>();
        ArrayList<String> arrayList2 = new ArrayList<>();
        if (IvonaPackagesInfo.b()) {
            try {
                for (String str : new ConfigXMLDataSet().a()) {
                    arrayList.add(com.ivona.ttslib.packages.a.b(str));
                }
            } catch (Exception e) {
                if (com.ivona.tts.commonlib.a.c) {
                    e.printStackTrace();
                }
            }
        } else {
            IvonaPackagesInfo a = ((AppIvonaAndroidLib) getApplication()).a();
            a.c();
            for (com.ivona.ttslib.packages.a aVar : a.a().values()) {
                switch (aVar.g()) {
                    case FULL_INSTALLED:
                        arrayList.add(aVar.h());
                        break;
                    default:
                        arrayList2.add(aVar.h());
                        break;
                }
            }
        }
        Intent intent = new Intent();
        intent.putExtra(TextToSpeechBeta.Engine.EXTRA_VOICE_DATA_ROOT_DIRECTORY, IvonaPackagesInfo.a);
        intent.putStringArrayListExtra("availableVoices", arrayList);
        intent.putStringArrayListExtra("unavailableVoices", arrayList2);
        setResult(1, intent);
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("CheckVoiceData", "--- available");
            Iterator<String> it = arrayList.iterator();
            while (it.hasNext()) {
                Log.d("CheckVoiceData", it.next());
            }
            Log.d("CheckVoiceData", "--- unavailable");
            Iterator<String> it2 = arrayList2.iterator();
            while (it2.hasNext()) {
                Log.d("CheckVoiceData", it2.next());
            }
        }
        if (com.ivona.tts.commonlib.a.b) {
            Log.d("CheckVoiceData", "**** CheckVoiceData END");
        }
        finish();
    }

    private void a(String str, String str2) {
        try {
            File fileStreamPath = getFileStreamPath(str);
            if (fileStreamPath.exists()) {
                fileStreamPath.delete();
            }
            FileOutputStream openFileOutput = openFileOutput(str, 1);
            try {
                openFileOutput.write(str2.getBytes());
            } finally {
                openFileOutput.close();
            }
        } catch (FileNotFoundException e) {
            Log.w("CheckVoiceData", "could not open '" + str + "' for writing");
        } catch (IOException e2) {
            Log.w("CheckVoiceData", "caught IOException: " + e2.getMessage());
        }
    }

    private void a() {
        a(".android_version", Integer.valueOf(Build.VERSION.SDK_INT).toString());
    }
}
