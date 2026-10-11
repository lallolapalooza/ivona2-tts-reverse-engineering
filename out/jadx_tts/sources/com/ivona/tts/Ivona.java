package com.ivona.tts;

import android.app.Activity;
import android.os.Bundle;
import android.os.Environment;

/* loaded from: classes.dex */
public class Ivona extends Activity {
    public static final String a = Environment.getExternalStorageDirectory() + "/ivona";

    @Override // android.app.Activity
    public void onCreate(Bundle bundle) {
        super.onCreate(bundle);
        finish();
    }
}
