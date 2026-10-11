package com.ivona.ttslib;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.util.Log;

/* loaded from: classes.dex */
public class CustomSettings extends Activity {
    @Override // android.app.Activity
    protected void onCreate(Bundle bundle) {
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("CustomSettings", "onCreate");
        }
        super.onCreate(bundle);
        SharedPreferences sharedPreferences = getSharedPreferences("ivona_custom", 0);
        if (getIntent().hasExtra("isEmailSet")) {
            Intent intent = new Intent();
            intent.putExtra("emailSet", sharedPreferences.getBoolean("emailSet", false));
            setResult(0, intent);
        }
        finish();
    }
}
