package com.ivona.ttslib;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Dialog;
import android.app.ProgressDialog;
import android.content.ComponentName;
import android.content.ContentResolver;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.pm.PackageInfo;
import android.os.Bundle;
import android.provider.Settings;
import android.speech.tts.TextToSpeech;
import android.text.Html;
import android.text.method.LinkMovementMethod;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.SeekBar;
import android.widget.SlidingDrawer;
import android.widget.TextView;
import com.google.tts.TextToSpeechBeta;
import com.ivona.ttslib.engine.TTSServiceActivation;
import java.util.Locale;
import java.util.Map;
import java.util.Observable;
import java.util.Observer;

/* loaded from: classes.dex */
public class IvonaGui extends Activity implements TextToSpeech.OnUtteranceCompletedListener, View.OnClickListener, com.google.tts.e, Observer {
    private ImageView i;
    private TTSServiceActivation j;
    private int a = 0;
    private int b = 0;
    private Bundle c = null;
    private TextToSpeech d = null;
    private boolean e = false;
    private int f = -1;
    private boolean g = false;
    private String h = null;
    private final ServiceConnection k = new m(this);

    private void a(TextView textView) {
        Locale locale = textView.getResources().getConfiguration().locale;
        StringBuilder sb = new StringBuilder();
        sb.append("<a href=\"");
        Object[] objArr = new Object[1];
        objArr[0] = locale.getISO3Language().toLowerCase().equals("pol") ? "pl" : "en_US";
        sb.append(String.format("http://mobile.faq.ivona.com/pkb_mobile_i4m?l=%1$s#home/l:%1$s", objArr));
        sb.append("\">");
        sb.append(getString(aa.v));
        sb.append("</a>");
        textView.setText(Html.fromHtml(sb.toString()));
        textView.setMovementMethod(LinkMovementMethod.getInstance());
    }

    @Override // android.app.Activity
    public void onCreate(Bundle bundle) {
        super.onCreate(bundle);
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("IvonaGui", "onCreate");
        }
        setContentView(z.a);
        SlidingDrawer slidingDrawer = (SlidingDrawer) findViewById(y.g);
        this.i = (ImageView) findViewById(y.e);
        slidingDrawer.setOnDrawerOpenListener(new f(this));
        slidingDrawer.setOnDrawerCloseListener(new n(this));
        a((TextView) findViewById(y.h));
        String[] strArr = {TextToSpeechBeta.Engine.KEY_PARAM_ENGINE, "file", TextToSpeechBeta.Engine.KEY_PARAM_LANGUAGE, TextToSpeechBeta.Engine.KEY_PARAM_PITCH, TextToSpeechBeta.Engine.KEY_PARAM_RATE, "text", "ttsextended"};
        int length = strArr.length;
        int i = 0;
        while (true) {
            if (i >= length) {
                break;
            }
            if (!b(strArr[i])) {
                i++;
            } else {
                this.g = true;
                break;
            }
        }
        EditText k = k();
        k.setEnabled(false);
        String c = c("welcome_text");
        if (c != null) {
            k.setText(c);
        }
        String c2 = c("app_name");
        if (c2 != null) {
            ((TextView) findViewById(y.j)).setText(c2);
        }
        String c3 = c("voice_info");
        if (c3 != null) {
            ((TextView) findViewById(y.i)).setText(c3);
        }
        a(c("app_icon"));
        Button h = h();
        h.setOnClickListener(this);
        h.setClickable(false);
        h.setEnabled(false);
        SeekBar i2 = i();
        i2.setOnSeekBarChangeListener(new o(this));
        i2.setMax(100);
        i2.setProgress(i2.getMax() / 2);
        SeekBar j = j();
        j.setOnSeekBarChangeListener(new p(this));
        j.setMax(100);
        j.setProgress(j.getMax() / 2);
        String c4 = c("VoicePackage");
        if (bundle != null && bundle.containsKey("useDefltVPkg")) {
            this.h = bundle.getString("useDefltVPkg");
        } else if (c4 != null) {
            this.h = c4;
        } else {
            this.h = null;
        }
        startService(new Intent(this, (Class<?>) TTSServiceActivation.class));
        if (this.h == null) {
            this.c = new Bundle();
            this.c.putInt("dlg", 14);
            this.c.putString("marketLink", "search?q=pub:\"IVONA Text-to-Speech\"");
            showDialog(14);
            return;
        }
        com.ivona.ttslib.packages.a aVar = (com.ivona.ttslib.packages.a) ((AppIvonaAndroidLib) getApplication()).a().a().get(this.h);
        if (aVar == null) {
            Log.e("IvonaGui", "Failed to get voice data");
            finish();
            return;
        }
        if (aVar.g() != com.ivona.ttslib.packages.b.FULL_INSTALLED) {
            Intent intent = new Intent("android.intent.action.MAIN");
            intent.setComponent(ComponentName.unflattenFromString(this.h + "/.IvonaVoice"));
            intent.addCategory("android.intent.category.LAUNCHER");
            PackageInfo a = com.ivona.tts.commonlib.b.a(this, this.h);
            PackageInfo a2 = com.ivona.tts.commonlib.b.a(this);
            if (a == null || a2 == null) {
                Log.e("IvonaGui", "Failed to read packages data");
                finish();
                return;
            }
            if (a.versionCode == a2.versionCode) {
                intent.putExtra("dont_return_to_gui", getIntent().getBooleanExtra("dont_return_to_gui", false));
                startActivity(intent);
                finish();
                return;
            }
            this.c = new Bundle();
            if (a.versionCode < a2.versionCode) {
                this.c.putInt("dlg", 14);
                this.c.putString("app_package", this.h);
            } else {
                this.c.putInt("dlg", 17);
                this.c.putString("app_package", a2.packageName);
            }
            showDialog(14);
            return;
        }
        b();
    }

    private void a(String str) {
        if (str != null) {
            ImageView imageView = (ImageView) findViewById(y.f);
            if (str.equalsIgnoreCase("en_us")) {
                imageView.setImageResource(x.e);
                return;
            }
            if (str.equalsIgnoreCase("en_gb")) {
                imageView.setImageResource(x.d);
                return;
            }
            if (str.equalsIgnoreCase("pl")) {
                imageView.setImageResource(x.l);
                return;
            }
            if (str.equalsIgnoreCase("de")) {
                imageView.setImageResource(x.b);
                return;
            }
            if (str.equalsIgnoreCase("es")) {
                imageView.setImageResource(x.g);
                return;
            }
            if (str.equalsIgnoreCase("es_us")) {
                imageView.setImageResource(x.h);
                return;
            }
            if (str.equalsIgnoreCase("fr")) {
                imageView.setImageResource(x.i);
                return;
            }
            if (str.equalsIgnoreCase("ro")) {
                imageView.setImageResource(x.m);
                return;
            }
            if (str.equalsIgnoreCase("cy")) {
                imageView.setImageResource(x.a);
                return;
            }
            if (str.equalsIgnoreCase("en_wls")) {
                imageView.setImageResource(x.f);
                return;
            }
            if (str.equalsIgnoreCase("en_au")) {
                imageView.setImageResource(x.c);
            } else if (str.equalsIgnoreCase("it")) {
                imageView.setImageResource(x.k);
            } else if (str.equalsIgnoreCase("is")) {
                imageView.setImageResource(x.j);
            }
        }
    }

    @Override // android.app.Activity
    protected void onResume() {
        super.onResume();
        if (this.a != 0) {
            showDialog(this.a);
        }
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("IvonaGui", "onResume");
        }
        if (!k().isEnabled()) {
            d();
        }
    }

    @Override // android.app.Activity
    protected void onPause() {
        super.onPause();
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("IvonaGui", "onPause");
        }
        if (this.a != 0) {
            removeDialog(this.a);
        }
    }

    @Override // android.app.Activity
    protected void onSaveInstanceState(Bundle bundle) {
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("IvonaGui", "onSavedInstanceState");
        }
        bundle.putString("useDefltVPkg", this.h);
        super.onSaveInstanceState(bundle);
    }

    private void b() {
        if (this.d == null) {
            if (e()) {
                this.d = new TextToSpeechBeta(this, new q(this));
            } else if (com.ivona.tts.commonlib.b.c() || com.ivona.tts.commonlib.b.d()) {
                this.d = new TextToSpeech(this, new r(this), "com.ivona.tts");
            } else {
                this.d = new TextToSpeech(this, new s(this));
            }
        }
    }

    @Override // android.app.Activity
    public void onDestroy() {
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("IvonaGui", "onDestroy");
        }
        if (this.d != null) {
            this.d.shutdown();
        }
        super.onDestroy();
    }

    @Override // android.app.Activity
    protected Dialog onCreateDialog(int i) {
        Dialog dialog = null;
        if (this.a != 0) {
            this.b = i;
        } else {
            switch (i) {
                case 10:
                    dialog = ProgressDialog.show(this, "", getString(aa.F));
                    break;
                case 11:
                    AlertDialog.Builder builder = new AlertDialog.Builder(this);
                    builder.setMessage(getString(aa.r)).setCancelable(false).setPositiveButton(getString(aa.h), new u(this)).setNegativeButton(getString(aa.d), new t(this));
                    dialog = builder.create();
                    break;
                case 13:
                    dialog = a(aa.u, false);
                    break;
                case 14:
                    dialog = a(aa.E, this.c.getString("app_package"), this.c.getString("marketLink"));
                    break;
                case 15:
                    dialog = a(aa.n, true);
                    break;
                case 16:
                    dialog = a(aa.m, true);
                    break;
                case 17:
                    dialog = a(aa.D, this.c.getString("app_package"), this.c.getString("marketLink"));
                    break;
            }
            if (dialog != null) {
                this.a = i;
                dialog.setOnDismissListener(new g(this));
            }
        }
        return dialog;
    }

    public Dialog a(int i, String str, String str2) {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setMessage(getString(i)).setCancelable(false).setPositiveButton("OK", new i(this, str, str2)).setNegativeButton(getString(aa.d), new h(this));
        return builder.create();
    }

    public Dialog a(int i, boolean z) {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setMessage(i).setCancelable(false).setPositiveButton(getString(aa.q), new k(this)).setNegativeButton(getString(aa.d), new j(this, z));
        return builder.create();
    }

    private boolean c() {
        return this.g;
    }

    private boolean b(String str) {
        return getIntent().hasExtra(str);
    }

    private String c(String str) {
        return getIntent().getStringExtra(str);
    }

    private boolean d(String str) {
        return "true".equalsIgnoreCase(c(str));
    }

    private float e(String str) {
        String c = c(str);
        try {
            return Float.parseFloat(c);
        } catch (NumberFormatException e) {
            Log.e("IvonaGui", "Invalid value " + c);
            return 1.0f;
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void d() {
        int onUtteranceCompletedListener;
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("IvonaGui", "tts:" + (this.d != null ? "ok" : "null") + " ttsInitStatus:" + this.f);
        }
        if (this.d != null && this.f == 0) {
            v a = a(true);
            if (a.b == 3) {
                Log.e("IvonaGui", "Old engine is loaded. It is required to reload it.");
                if (this.a == 0) {
                    showDialog(15);
                    return;
                }
                return;
            }
            if (a.b == 1 || a() == 0) {
                showDialog(16);
                return;
            }
            if (a.a != null && !a.a.equalsIgnoreCase(getPackageName())) {
                showDialog(13);
            }
            k().setEnabled(true);
            Button h = h();
            h.setClickable(true);
            h.setEnabled(true);
            if (this.d instanceof TextToSpeechBeta) {
                onUtteranceCompletedListener = ((TextToSpeechBeta) this.d).setOnUtteranceCompletedListener((com.google.tts.e) this);
            } else {
                onUtteranceCompletedListener = this.d.setOnUtteranceCompletedListener(this);
            }
            if (onUtteranceCompletedListener != 0) {
                Log.e("IvonaGui", "Could not install the OnUtteranceCompletedListener");
            }
            if (c()) {
                a(false);
                return;
            }
            return;
        }
        Log.e("IvonaGui", "Could not initialize TextToSpeech");
    }

    public int a() {
        if (com.ivona.tts.commonlib.b.d() || com.ivona.tts.commonlib.b.c()) {
            return 1;
        }
        if (e()) {
            return -1;
        }
        ContentResolver contentResolver = getContentResolver();
        if (Settings.Secure.getString(contentResolver, "tts_enabled_plugins") == null) {
            return 0;
        }
        String[] split = Settings.Secure.getString(contentResolver, "tts_enabled_plugins").split(" ");
        for (String str : split) {
            if (str.equals(getPackageName())) {
                return 1;
            }
        }
        return 0;
    }

    private boolean e() {
        return (c() && b("ttsextended")) ? d("ttsextended") : com.ivona.tts.commonlib.b.b();
    }

    private float f() {
        if (c() && b(TextToSpeechBeta.Engine.KEY_PARAM_RATE)) {
            return e(TextToSpeechBeta.Engine.KEY_PARAM_RATE);
        }
        SeekBar i = i();
        float progress = i.getProgress() / (i.getMax() / 2);
        if (progress < 1.0f) {
            return (progress * 0.5f) + 0.5f;
        }
        return ((progress - 1.0f) * 2.0f) + 1.0f;
    }

    private float g() {
        if (c() && b(TextToSpeechBeta.Engine.KEY_PARAM_PITCH)) {
            return e(TextToSpeechBeta.Engine.KEY_PARAM_PITCH);
        }
        return (r2.getMax() / 2) / (101 - (j().getProgress() <= 100 ? r1 : 100));
    }

    private Button h() {
        return (Button) findViewById(y.a);
    }

    private SeekBar i() {
        return (SeekBar) findViewById(y.d);
    }

    private SeekBar j() {
        return (SeekBar) findViewById(y.c);
    }

    private EditText k() {
        return (EditText) findViewById(y.b);
    }

    private String l() {
        if (c() && b("text")) {
            return c("text");
        }
        return k().getText().toString();
    }

    private String m() {
        return (c() && b(TextToSpeechBeta.Engine.KEY_PARAM_ENGINE)) ? c(TextToSpeechBeta.Engine.KEY_PARAM_ENGINE) : getApplication().getPackageName();
    }

    private Locale n() {
        if (c() && b(TextToSpeechBeta.Engine.KEY_PARAM_LANGUAGE)) {
            String[] split = c(TextToSpeechBeta.Engine.KEY_PARAM_LANGUAGE).split("[-_]", 3);
            return new Locale(split.length > 0 ? split[0] : "", split.length > 1 ? split[1] : "", split.length > 2 ? split[2] : "");
        }
        if (this.h != null) {
            Map a = ((AppIvonaAndroidLib) getApplication()).a().a();
            if (a.containsKey(this.h)) {
                return ((com.ivona.ttslib.packages.a) a.get(this.h)).e();
            }
        }
        return null;
    }

    /* JADX WARN: Removed duplicated region for block: B:12:0x0032  */
    /* JADX WARN: Removed duplicated region for block: B:32:0x0050  */
    /* JADX WARN: Removed duplicated region for block: B:41:0x0083  */
    /* JADX WARN: Removed duplicated region for block: B:44:0x00a7  */
    /* JADX WARN: Removed duplicated region for block: B:47:0x00ce  */
    /* JADX WARN: Removed duplicated region for block: B:49:0x00d2  */
    /* JADX WARN: Removed duplicated region for block: B:52:0x0153  */
    /* JADX WARN: Removed duplicated region for block: B:53:0x014a  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    private com.ivona.ttslib.v a(boolean r11) {
        /*
            Method dump skipped, instructions count: 349
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: com.ivona.ttslib.IvonaGui.a(boolean):com.ivona.ttslib.v");
    }

    @Override // android.view.View.OnClickListener
    public synchronized void onClick(View view) {
        Button h = h();
        SeekBar i = i();
        SeekBar j = j();
        if (this.e) {
            this.d.stop();
            o();
        } else if (a(false).b == 3) {
            if (this.a == 0) {
                showDialog(15);
            }
        } else {
            h.setText(aa.b);
            i.setEnabled(false);
            j.setEnabled(false);
            this.e = true;
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public synchronized void o() {
        h().setText(aa.a);
        i().setEnabled(true);
        j().setEnabled(true);
        this.e = false;
    }

    @Override // android.speech.tts.TextToSpeech.OnUtteranceCompletedListener, com.google.tts.e
    public void onUtteranceCompleted(String str) {
        runOnUiThread(new l(this));
    }

    @Override // java.util.Observer
    public void update(Observable observable, Object obj) {
    }
}
