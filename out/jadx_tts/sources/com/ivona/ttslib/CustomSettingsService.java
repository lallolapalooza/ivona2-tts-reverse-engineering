package com.ivona.ttslib;

import android.app.IntentService;
import android.content.Intent;
import android.content.SharedPreferences;
import android.util.Log;

/* loaded from: classes.dex */
public class CustomSettingsService extends IntentService {
    public CustomSettingsService() {
        super("CustomSettingsService");
    }

    @Override // android.app.IntentService
    protected void onHandleIntent(Intent intent) {
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("CustomSettingsService", "onHandleIntent");
        }
        if (intent.hasExtra("setEmail")) {
            if (com.ivona.tts.commonlib.a.c) {
                Log.d("CustomSettingsService", "set email");
            }
            SharedPreferences sharedPreferences = getSharedPreferences("ivona_custom", 0);
            boolean z = intent.getExtras().getBoolean("setEmail");
            SharedPreferences.Editor edit = sharedPreferences.edit();
            edit.putBoolean("emailSet", z);
            edit.commit();
            return;
        }
        if (intent.hasExtra("upkgmon")) {
            if (com.ivona.tts.commonlib.a.c) {
                Log.d("CustomSettingsService", "update packages");
            }
            ((AppIvonaAndroidLib) getApplicationContext()).a().c();
        }
    }
}
