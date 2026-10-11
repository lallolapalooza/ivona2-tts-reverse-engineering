package com.ivona.ttslib.engine;

import android.content.Context;
import android.net.LocalServerSocket;
import android.os.AsyncTask;
import android.widget.Toast;
import com.google.tts.TextToSpeechBeta;
import com.ivona.ttslib.aa;
import java.io.OutputStream;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.ReentrantLock;

/* compiled from: TTSEngineConnector.java */
/* loaded from: classes.dex */
class f extends AsyncTask {
    final /* synthetic */ d a;
    private boolean b;
    private final ReentrantLock c;
    private final Condition d;
    private LocalServerSocket e;
    private final BlockingQueue f;

    private f(d dVar) {
        this.a = dVar;
        this.b = false;
        this.c = new ReentrantLock();
        this.d = this.c.newCondition();
        this.e = null;
        this.f = new LinkedBlockingQueue();
    }

    private void b() {
        this.c.lock();
        this.b = true;
        this.d.signalAll();
        this.c.unlock();
    }

    public boolean a() {
        return this.b;
    }

    private boolean a(c cVar, OutputStream outputStream) {
        try {
            if (cVar.a() == 2) {
            }
        } catch (Exception e) {
            if (com.ivona.tts.commonlib.a.c) {
                e.printStackTrace();
            }
        }
        return false;
    }

    /* JADX INFO: Access modifiers changed from: protected */
    /* JADX WARN: Code restructure failed: missing block: B:59:0x002c, code lost:
    
        r9.e.close();
     */
    /* JADX WARN: Removed duplicated region for block: B:71:0x00bf  */
    @Override // android.os.AsyncTask
    /* renamed from: a, reason: merged with bridge method [inline-methods] */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public java.lang.Integer doInBackground(java.lang.String... r10) {
        /*
            Method dump skipped, instructions count: 277
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: com.ivona.ttslib.engine.f.doInBackground(java.lang.String[]):java.lang.Integer");
    }

    /* JADX INFO: Access modifiers changed from: protected */
    @Override // android.os.AsyncTask
    /* renamed from: a, reason: merged with bridge method [inline-methods] */
    public void onProgressUpdate(c... cVarArr) {
        Context context;
        Context context2;
        Context context3;
        Context context4;
        if (cVarArr[0] != null) {
            c cVar = cVarArr[0];
            if (this.a.countObservers() > 0) {
                this.a.setChanged();
                this.a.notifyObservers(cVar);
            }
            if (cVar.a() == 1) {
                switch (cVar.b()) {
                    case 1:
                        context3 = this.a.c;
                        context4 = this.a.c;
                        Toast.makeText(context3, context4.getString(aa.n), 1).show();
                        break;
                    case TextToSpeechBeta.LANG_COUNTRY_VAR_AVAILABLE /* 2 */:
                        context = this.a.c;
                        context2 = this.a.c;
                        Toast.makeText(context, context2.getString(aa.l), 1).show();
                        break;
                }
            }
        }
    }

    /* JADX INFO: Access modifiers changed from: protected */
    @Override // android.os.AsyncTask
    /* renamed from: a, reason: merged with bridge method [inline-methods] */
    public void onPostExecute(Integer num) {
    }
}
