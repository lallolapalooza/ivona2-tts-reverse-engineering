package com.ivona.ttslib;

import android.content.ComponentName;
import android.content.ServiceConnection;
import android.os.IBinder;
import android.util.Log;
import com.ivona.ttslib.engine.TTSServiceActivation;

/* compiled from: IvonaGui.java */
/* loaded from: classes.dex */
class m implements ServiceConnection {
    final /* synthetic */ IvonaGui a;

    m(IvonaGui ivonaGui) {
        this.a = ivonaGui;
    }

    @Override // android.content.ServiceConnection
    public void onServiceConnected(ComponentName componentName, IBinder iBinder) {
        TTSServiceActivation tTSServiceActivation;
        TTSServiceActivation tTSServiceActivation2;
        this.a.j = ((com.ivona.ttslib.engine.j) iBinder).a();
        tTSServiceActivation = this.a.j;
        if (tTSServiceActivation != null) {
            tTSServiceActivation2 = this.a.j;
            tTSServiceActivation2.a().addObserver(this.a);
        } else {
            Log.e("IvonaGui", "Error on connection with activation service.");
        }
    }

    @Override // android.content.ServiceConnection
    public void onServiceDisconnected(ComponentName componentName) {
        TTSServiceActivation tTSServiceActivation;
        tTSServiceActivation = this.a.j;
        tTSServiceActivation.a().deleteObserver(this.a);
        this.a.j = null;
    }
}
