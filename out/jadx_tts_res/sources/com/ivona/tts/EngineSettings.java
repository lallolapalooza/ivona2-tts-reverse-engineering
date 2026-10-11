package com.ivona.tts;

import android.content.Context;
import android.os.Bundle;
import android.preference.ListPreference;
import android.preference.Preference;
import android.preference.PreferenceActivity;
import android.preference.PreferenceCategory;
import android.util.Log;
import com.google.tts.R;
import com.ivona.ttslib.AppIvonaAndroidLib;
import com.ivona.ttslib.packages.IvonaPackagesInfo;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/* loaded from: classes.dex */
public class EngineSettings extends PreferenceActivity implements Preference.OnPreferenceChangeListener {
    @Override // android.preference.PreferenceActivity, android.app.Activity
    protected void onCreate(Bundle bundle) {
        super.onCreate(bundle);
        setPreferenceScreen(getPreferenceManager().createPreferenceScreen(this));
        IvonaPackagesInfo a = ((AppIvonaAndroidLib) getApplication()).a();
        PreferenceCategory preferenceCategory = new PreferenceCategory(this);
        preferenceCategory.setTitle(R.string.preferred_voice);
        getPreferenceScreen().addPreference(preferenceCategory);
        Map d = a.d();
        for (Locale locale : d.keySet()) {
            preferenceCategory.addPreference(a(locale, (List) d.get(locale)));
        }
    }

    private Preference a(Locale locale, List list) {
        int i = 0;
        ListPreference listPreference = new ListPreference(this);
        listPreference.setKey(a(locale));
        listPreference.setTitle(locale.getDisplayName());
        listPreference.setDialogTitle(R.string.preferred_voice_dialog_title);
        listPreference.setPersistent(false);
        listPreference.setOnPreferenceChangeListener(this);
        String[] strArr = new String[list.size()];
        String[] strArr2 = new String[list.size()];
        while (true) {
            int i2 = i;
            if (i2 >= list.size()) {
                break;
            }
            com.ivona.ttslib.packages.a aVar = (com.ivona.ttslib.packages.a) list.get(i2);
            strArr[i2] = aVar.d();
            strArr2[i2] = aVar.c();
            i = i2 + 1;
        }
        listPreference.setEntries(strArr);
        listPreference.setEntryValues(strArr2);
        com.ivona.ttslib.packages.a b = b(locale, list);
        if (b != null) {
            listPreference.setValue(b.c());
            listPreference.setSummary(b.d());
        }
        return listPreference;
    }

    private com.ivona.ttslib.packages.a b(Locale locale, List list) {
        String a = a(this, a(locale));
        if (a != null) {
            Iterator it = list.iterator();
            while (it.hasNext()) {
                com.ivona.ttslib.packages.a aVar = (com.ivona.ttslib.packages.a) it.next();
                if (a.equals(aVar.c())) {
                    return aVar;
                }
            }
        }
        if (list.size() > 0) {
            return (com.ivona.ttslib.packages.a) list.get(0);
        }
        return null;
    }

    @Override // android.preference.Preference.OnPreferenceChangeListener
    public boolean onPreferenceChange(Preference preference, Object obj) {
        com.ivona.ttslib.packages.a aVar = (com.ivona.ttslib.packages.a) ((AppIvonaAndroidLib) getApplication()).a().a().get(obj.toString());
        if (aVar != null) {
            a(preference.getKey(), aVar.c());
            preference.setSummary(aVar.d());
            return true;
        }
        return true;
    }

    public static String a(Locale locale) {
        return "." + locale.getISO3Language().toLowerCase() + "_" + locale.getISO3Country().toLowerCase();
    }

    public static String a(Context context, String str) {
        try {
            if (!context.getFileStreamPath(str).exists()) {
                return null;
            }
            byte[] bArr = new byte[4096];
            FileInputStream openFileInput = context.openFileInput(str);
            try {
                int read = openFileInput.read(bArr);
                openFileInput.close();
                return new String(bArr, 0, read);
            } catch (Throwable th) {
                openFileInput.close();
                throw th;
            }
        } catch (FileNotFoundException e) {
            Log.w("Ivona.EngineSettings", "could not open '" + str + "' for reading");
            return null;
        } catch (IOException e2) {
            Log.w("Ivona.EngineSettings", "caught IOException: " + e2.getMessage());
            return null;
        }
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
            Log.w("Ivona.EngineSettings", "could not open '" + str + "' for writing");
        } catch (IOException e2) {
            Log.w("Ivona.EngineSettings", "caught IOException: " + e2.getMessage());
        }
    }
}
