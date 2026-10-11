package com.google.tts;

import android.app.Activity;
import android.content.Context;
import com.google.tts.TextToSpeechBeta;
import java.util.Locale;

/* loaded from: classes.dex */
public class MakeBagel extends Activity {
    b completionListener = new b() { // from class: com.google.tts.MakeBagel.1
        @Override // com.google.tts.b
        public void onSpeechCompleted() {
            MakeBagel.this.mTts.shutdown();
            MakeBagel.this.self.setResult(-1);
            MakeBagel.this.finish();
        }
    };
    private String langRegionString;
    private TTS mTts;
    private String message;
    private MakeBagel self;

    @Override // android.app.Activity
    protected void onResume() {
        super.onResume();
        this.self = this;
        this.self.setResult(0);
        this.message = getIntent().getStringExtra("message");
        Locale locale = new Locale(new StringBuilder(String.valueOf(getIntent().getStringExtra(TextToSpeechBeta.Engine.KEY_PARAM_LANGUAGE))).toString(), new StringBuilder(String.valueOf(getIntent().getStringExtra(TextToSpeechBeta.Engine.KEY_PARAM_COUNTRY))).toString(), new StringBuilder(String.valueOf(getIntent().getStringExtra(TextToSpeechBeta.Engine.KEY_PARAM_VARIANT))).toString());
        String iSO3Language = locale.getISO3Language();
        String iSO3Country = locale.getISO3Country();
        this.langRegionString = "";
        if (iSO3Language.length() == 3) {
            if (iSO3Country.length() == 3) {
                this.langRegionString = String.valueOf(iSO3Language) + "-" + iSO3Country;
            } else {
                this.langRegionString = iSO3Language;
            }
        }
        this.mTts = new TTS((Context) this, new a() { // from class: com.google.tts.MakeBagel.2
            @Override // com.google.tts.a
            public void onInit(int i) {
                MakeBagel.this.mTts.setOnSpeechCompletedListener(MakeBagel.this.completionListener);
                if (MakeBagel.this.langRegionString.length() > 0) {
                    MakeBagel.this.mTts.setLanguage(MakeBagel.this.langRegionString);
                }
                MakeBagel.this.mTts.speak(MakeBagel.this.message, 0, null);
            }
        }, true);
    }

    @Override // android.app.Activity
    protected void onDestroy() {
        super.onDestroy();
        if (this.mTts != null) {
            this.mTts.shutdown();
        }
    }
}
