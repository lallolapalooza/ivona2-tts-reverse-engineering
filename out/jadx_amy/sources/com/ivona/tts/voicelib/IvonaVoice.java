package com.ivona.tts.voicelib;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Dialog;
import android.app.PendingIntent;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Messenger;
import android.text.Html;
import android.text.method.LinkMovementMethod;
import android.util.Log;
import android.view.View;
import android.webkit.WebView;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;
import com.google.android.vending.expansion.downloader.DownloadProgressInfo;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.Locale;

/* loaded from: classes.dex */
public abstract class IvonaVoice extends Activity implements com.google.android.vending.expansion.downloader.m {
    private SharedPreferences a;
    private WebView b;
    private boolean c;
    private com.google.android.vending.expansion.downloader.n d;
    private com.google.android.vending.expansion.downloader.o e;
    private ProgressBar f;
    private TextView g;
    private TextView h;
    private Button i;
    private int j;
    private View k;
    private View l;

    public abstract String a();

    public abstract String b();

    public abstract String c();

    public abstract String d();

    public abstract String e();

    public abstract int f();

    public String b(int i) {
        return getString(i).replace("%file_size%", String.valueOf(f()));
    }

    private void c(int i) {
        if (this.j != i) {
            this.j = i;
            ((TextView) findViewById(m.p)).setText(com.google.android.vending.expansion.downloader.l.a(i));
        }
    }

    private j h() {
        return this.a.getInt("agr_int_ver", 0) < getResources().getInteger(n.a) ? j.TO_ACCEPT : j.ACCEPTED;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void a(boolean z) {
        this.c = z;
        this.i.setText(z ? p.d : p.c);
    }

    @Override // android.app.Activity
    public void onCreate(Bundle bundle) {
        super.onCreate(bundle);
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("IvonaVoice", "onCreate");
        }
        setContentView(o.a);
        this.a = getSharedPreferences("ivona_package", 0);
        i();
        a((TextView) findViewById(m.k));
        this.e = com.google.android.vending.expansion.downloader.c.a(this, VoiceDownloaderService.class);
        this.f = (ProgressBar) findViewById(m.h);
        this.g = (TextView) findViewById(m.l);
        this.h = (TextView) findViewById(m.o);
        this.k = findViewById(m.g);
        this.l = findViewById(m.e);
        ((TextView) findViewById(m.i)).setText(b(p.q));
        ((Button) findViewById(m.b)).setOnClickListener(new b(this));
        ((Button) findViewById(m.c)).setOnClickListener(new c(this));
        this.i = (Button) findViewById(m.a);
        this.i.setOnClickListener(new d(this));
        if (h() != j.ACCEPTED) {
            this.b = new WebView(this);
            this.b.loadData(getString(p.i), "text/html; charset=UTF-8", "utf-8");
            this.b.setBackgroundColor(-1);
            this.b.getSettings().setDefaultTextEncodingName("utf-8");
            this.b.setWebViewClient(new e(this));
            return;
        }
        b(true);
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void b(boolean z) {
        if (z && !VoiceFiles.a(this)) {
            try {
                Intent intent = getIntent();
                Intent intent2 = new Intent(this, getClass());
                intent2.setFlags(335544320);
                intent2.setAction(intent.getAction());
                if (intent.getCategories() != null) {
                    Iterator<String> it = intent.getCategories().iterator();
                    while (it.hasNext()) {
                        intent2.addCategory(it.next());
                    }
                }
                int a = com.google.android.vending.expansion.downloader.c.a(this, PendingIntent.getActivity(this, 0, intent2, 134217728), VoiceDownloaderService.class);
                if (com.ivona.tts.commonlib.a.c) {
                    Log.w("IvonaVoice", "STARTDOWNLOADSERVICEIFREQUIRED RES:" + a);
                }
                if (a != 0) {
                    ((LinearLayout) findViewById(m.g)).setVisibility(0);
                    return;
                }
            } catch (PackageManager.NameNotFoundException e) {
                if (com.ivona.tts.commonlib.a.c) {
                    Log.e("IvonaVoice", "Cannot find own package!");
                }
                finish();
                return;
            }
        } else if (com.ivona.tts.commonlib.a.c) {
            Log.w("IvonaVoice", "EXPANSION FILES DOWNLOADED");
        }
        ActivityReceiver.a(getApplicationContext());
        j();
    }

    @Override // android.app.Activity
    protected Dialog onCreateDialog(int i) {
        if (i != 10) {
            return null;
        }
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setView(this.b).setCancelable(false).setPositiveButton("OK", new g(this)).setNegativeButton(getString(p.g), new f(this));
        return builder.create();
    }

    public static boolean g() {
        return Build.VERSION.SDK_INT < 8;
    }

    private void i() {
        ((TextView) findViewById(m.n)).setText(b());
        ((TextView) findViewById(m.m)).setText(c());
    }

    private void a(TextView textView) {
        Locale locale = textView.getResources().getConfiguration().locale;
        StringBuilder sb = new StringBuilder();
        sb.append("<a href=\"");
        Object[] objArr = new Object[1];
        objArr[0] = locale.getISO3Language().toLowerCase().equals("pol") ? "pl" : "en_US";
        sb.append(String.format("http://mobile.faq.ivona.com/pkb_mobile_i4m?l=%1$s#home/l:%1$s", objArr));
        sb.append("\">");
        sb.append(getString(p.j));
        sb.append("</a>");
        textView.setText(Html.fromHtml(sb.toString()));
        textView.setMovementMethod(LinkMovementMethod.getInstance());
    }

    private boolean j() {
        PackageInfo b;
        if (g()) {
            Intent intent = new Intent();
            intent.setClassName("com.google.tts", "com.google.tts.TextToSpeechSettings");
            if (!com.ivona.tts.commonlib.c.a(getApplicationContext(), intent)) {
                a(m.f, 0);
                TextView textView = (TextView) findViewById(m.j);
                if (k()) {
                    textView.setText(p.m);
                } else {
                    textView.setText(p.o);
                }
                Button button = (Button) findViewById(m.d);
                button.setText(p.b);
                button.setOnClickListener(new h(this));
                return false;
            }
        }
        ArrayList arrayList = new ArrayList();
        arrayList.add(a());
        Intent intent2 = new Intent();
        intent2.setClassName("com.ivona.tts", "com.ivona.ttslib.CheckVoiceData");
        intent2.putExtra("IvonaLibvoices", arrayList);
        int i = p.n;
        int i2 = p.e;
        boolean a = com.ivona.tts.commonlib.c.a(getApplicationContext(), intent2);
        if (a && (b = com.ivona.tts.commonlib.c.b(getApplicationContext())) != null && b.versionCode < 183) {
            i = p.p;
            i2 = p.f;
            a = false;
        }
        if (!a) {
            a(m.f, 0);
            ((TextView) findViewById(m.j)).setText(i);
            Button button2 = (Button) findViewById(m.d);
            button2.setText(i2);
            button2.setOnClickListener(new i(this));
            return false;
        }
        if (getIntent().getBooleanExtra("dont_return_to_gui", false)) {
            Toast.makeText(this, p.l, 1).show();
            finish();
            return true;
        }
        Intent intent3 = new Intent("android.intent.action.VIEW");
        intent3.setClassName("com.ivona.tts", "com.ivona.ttslib.IvonaGui");
        intent3.putExtra("VoicePackage", getApplicationContext().getPackageName());
        intent3.putExtra("welcome_text", d());
        intent3.putExtra("app_name", getString(p.a));
        intent3.putExtra("voice_info", c());
        intent3.putExtra("app_icon", e());
        intent3.putExtra("dont_return_to_gui", true);
        startActivity(intent3);
        finish();
        return true;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public boolean k() {
        return Build.MANUFACTURER.compareToIgnoreCase("Sony Ericsson") == 0 && Build.MODEL.compareToIgnoreCase("U20i") == 0;
    }

    @Override // android.app.Activity
    protected void onPause() {
        super.onPause();
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("IvonaVoice", "onPause");
        }
    }

    @Override // android.app.Activity
    protected void onResume() {
        super.onResume();
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("IvonaVoice", "onResume");
        }
    }

    @Override // android.app.Activity
    protected void onDestroy() {
        super.onDestroy();
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("IvonaVoice", "onDestroy");
        }
    }

    private void a(int i, int i2) {
        View findViewById = findViewById(i);
        if (findViewById != null) {
            findViewById.setVisibility(i2);
        }
    }

    @Override // com.google.android.vending.expansion.downloader.m
    public void a(Messenger messenger) {
        this.d = com.google.android.vending.expansion.downloader.h.a(messenger);
        this.d.a(this.e.a());
    }

    @Override // android.app.Activity
    protected void onStart() {
        if (this.e != null) {
            this.e.a(this);
        }
        super.onStart();
    }

    @Override // android.app.Activity
    protected void onStop() {
        if (this.e != null) {
            this.e.b(this);
        }
        super.onStop();
    }

    @Override // com.google.android.vending.expansion.downloader.m
    public void a(int i) {
        boolean z;
        boolean z2;
        boolean z3;
        boolean z4 = true;
        if (com.ivona.tts.commonlib.a.c) {
            Log.w("IvonaVoice", "ONDOWNLOADSTATECHANGED:" + i);
        }
        c(i);
        switch (i) {
            case 1:
                z = true;
                z2 = false;
                z3 = false;
                break;
            case 2:
            case 3:
                z = true;
                z2 = false;
                z3 = false;
                break;
            case 4:
                z = false;
                z2 = false;
                z3 = false;
                break;
            case 5:
                ((LinearLayout) findViewById(m.g)).setVisibility(8);
                b(false);
                return;
            case 6:
            case 10:
            case 11:
            case 13:
            case 17:
            default:
                z = true;
                z2 = true;
                z3 = false;
                break;
            case 7:
                z = false;
                z2 = true;
                z3 = false;
                break;
            case 8:
            case 9:
                z = false;
                z2 = true;
                z3 = true;
                z4 = false;
                break;
            case 12:
            case 14:
                z = false;
                z2 = true;
                z3 = false;
                break;
            case 15:
            case 16:
            case 18:
            case 19:
                z = false;
                z2 = true;
                z3 = false;
                break;
        }
        int i2 = z4 ? 0 : 8;
        if (this.k.getVisibility() != i2) {
            this.k.setVisibility(i2);
        }
        int i3 = z3 ? 0 : 8;
        if (this.l.getVisibility() != i3) {
            this.l.setVisibility(i3);
        }
        this.f.setIndeterminate(z);
        a(z2);
    }

    @Override // com.google.android.vending.expansion.downloader.m
    public void a(DownloadProgressInfo downloadProgressInfo) {
        this.f.setMax((int) (downloadProgressInfo.a >> 8));
        this.f.setProgress(((int) downloadProgressInfo.b) >> 8);
        this.g.setText(Long.toString((downloadProgressInfo.b * 100) / downloadProgressInfo.a) + "%");
        this.h.setText(com.google.android.vending.expansion.downloader.l.a(downloadProgressInfo.b, downloadProgressInfo.a));
    }
}
