package com.ivona.ttslib;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import com.google.tts.TextToSpeechBeta;
import java.util.Locale;

/* loaded from: classes.dex */
public class GetSampleText extends Activity {
    private static final d[] a = {new d("eng", "GBR", aa.j), new d("eng", "USA", aa.k), new d("eng", "AUS", aa.i), new d("spa", "ESP", aa.B), new d("spa", "USA", aa.C), new d("pol", "POL", aa.x), new d("deu", "DEU", aa.g), new d("fra", "FRA", aa.p), new d("fra", "CAN", aa.o), new d("ron", "ROU", aa.A), new d("cym", "GBR", aa.e), new d("ita", "ITA", aa.t), new d("isl", "ISL", aa.s), new d("prt", "BRA", aa.y), new d("dan", "DNK", aa.f)};

    @Override // android.app.Activity
    public void onCreate(Bundle bundle) {
        String str;
        int i = 0;
        super.onCreate(bundle);
        Intent intent = getIntent();
        if (intent.getExtras() != null) {
            String string = intent.getExtras().getString(TextToSpeechBeta.Engine.KEY_PARAM_LANGUAGE);
            String string2 = intent.getExtras().getString(TextToSpeechBeta.Engine.KEY_PARAM_COUNTRY);
            Locale locale = new Locale(string, string2);
            for (int i2 = 0; i2 < a.length; i2++) {
                d dVar = a[i2];
                if (dVar.a.equalsIgnoreCase(locale.getISO3Language()) && (string2 == null || string2.length() == 0 || dVar.b.equalsIgnoreCase(locale.getISO3Country()))) {
                    str = getString(dVar.c);
                    if (com.ivona.tts.commonlib.a.c) {
                        Log.d("GetSampleText", locale.getISO3Language() + "/" + locale.getISO3Country() + " == " + dVar.a + "/" + dVar.b);
                    }
                    Intent intent2 = new Intent();
                    intent2.putExtra("sampleText", str);
                    setResult(i, intent2);
                    finish();
                }
                if (com.ivona.tts.commonlib.a.c) {
                    Log.d("GetSampleText", locale.getISO3Language() + "/" + locale.getISO3Country() + " != " + dVar.a + "/" + dVar.b);
                }
            }
        }
        str = "";
        i = -2;
        Intent intent22 = new Intent();
        intent22.putExtra("sampleText", str);
        setResult(i, intent22);
        finish();
    }
}
