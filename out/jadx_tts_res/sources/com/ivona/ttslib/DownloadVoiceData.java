package com.ivona.ttslib;

import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.preference.Preference;
import android.preference.PreferenceActivity;
import android.preference.PreferenceCategory;
import com.google.tts.TextToSpeechBeta;
import com.ivona.ttslib.packages.IvonaPackagesInfo;
import java.util.Locale;

/* loaded from: classes.dex */
public class DownloadVoiceData extends PreferenceActivity {
    @Override // android.preference.PreferenceActivity, android.app.Activity
    protected void onCreate(Bundle bundle) {
        Preference preference;
        super.onCreate(bundle);
        if (IvonaPackagesInfo.b()) {
            finish();
            return;
        }
        setPreferenceScreen(getPreferenceManager().createPreferenceScreen(this));
        boolean z = true;
        for (com.ivona.ttslib.packages.a aVar : ((AppIvonaAndroidLib) getApplication()).a().a().values()) {
            Preference findPreference = findPreference(aVar.d());
            com.ivona.ttslib.packages.b g = aVar.g();
            if (g != com.ivona.ttslib.packages.b.UNKNOWN) {
                if (findPreference == null) {
                    Locale f = aVar.f();
                    String locale = f.toString();
                    PreferenceCategory preferenceCategory = (PreferenceCategory) findPreference(locale);
                    if (preferenceCategory == null) {
                        preferenceCategory = new PreferenceCategory(this);
                        preferenceCategory.setKey(locale);
                        preferenceCategory.setTitle(f.getDisplayName());
                        getPreferenceScreen().addPreference(preferenceCategory);
                    }
                    Preference preference2 = new Preference(this);
                    preferenceCategory.addPreference(preference2);
                    preference = preference2;
                } else {
                    preference = findPreference;
                }
                preference.setKey(aVar.d());
                preference.setPersistent(false);
                preference.setTitle(aVar.d());
                preference.setEnabled(true);
                switch (c.a[g.ordinal()]) {
                    case 1:
                        preference.setSummary(aa.w);
                        break;
                    case TextToSpeechBeta.LANG_COUNTRY_VAR_AVAILABLE /* 2 */:
                        preference.setSummary(aa.c);
                        break;
                }
                preference.setOnPreferenceClickListener(new b(this, aVar));
                z = false;
            }
        }
        if (z) {
            String str = "http://mobile.ivona.com/?set_lang=" + getString(aa.z);
            SharedPreferences sharedPreferences = getSharedPreferences("ivona_referrer", 0);
            if (sharedPreferences.contains("referrer")) {
                str = str + "&referrer=" + sharedPreferences.getString("referrer", "");
            }
            startActivity(new Intent("android.intent.action.VIEW", Uri.parse(str)));
            finish();
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public boolean a(Intent intent) {
        return getPackageManager().queryIntentActivities(intent, 0).size() > 0;
    }
}
