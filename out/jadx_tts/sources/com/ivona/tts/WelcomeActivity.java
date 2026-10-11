package com.ivona.tts;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import com.google.tts.R;

/* loaded from: classes.dex */
public class WelcomeActivity extends Activity {
    private static final a[] a = {new a("com.ivona.tts.voicebeta.eng.usa.kendra", "P113_1"), new a("com.ivona.tts.voicebeta.pol.pol.maja", "P107_1"), new a("com.ivona.tts.voicebeta.eng.gbr.amy", "P109_1"), new a("com.ivona.tts.voicebeta.deu.deu.marlene", "P123_1"), new a("com.ivona.tts.voicebeta.spa.esp.conchita", "P119_1"), new a("com.ivona.tts.voicebeta.spa.usa.penelope", "122_1"), new a("com.ivona.tts.voicebeta.fra.fra.celine", "P125_1"), new a("com.ivona.tts.voicebeta.ron.rou.carmen", "P104_1"), new a("com.ivona.tts.voicebeta.cym.gbr.gwyneth", "P127_1"), new a("com.ivona.tts.voicebeta.eng.gbr.gwyneth", "P129_1")};

    @Override // android.app.Activity
    public void onCreate(Bundle bundle) {
        super.onCreate(bundle);
        String str = "http://mobile.ivona.com/?ap=EMBED&v=1&set_lang=" + getString(R.string.res_lang);
        String str2 = str;
        for (a aVar : a) {
            if (aVar.a(this)) {
                str2 = str2 + aVar.a();
            }
        }
        startActivity(new Intent("android.intent.action.VIEW", Uri.parse(str2)));
        finish();
    }
}
