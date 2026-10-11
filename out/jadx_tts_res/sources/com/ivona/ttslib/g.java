package com.ivona.ttslib;

import android.content.DialogInterface;

/* compiled from: IvonaGui.java */
/* loaded from: classes.dex */
class g implements DialogInterface.OnDismissListener {
    final /* synthetic */ IvonaGui a;

    g(IvonaGui ivonaGui) {
        this.a = ivonaGui;
    }

    @Override // android.content.DialogInterface.OnDismissListener
    public void onDismiss(DialogInterface dialogInterface) {
        int i;
        int i2;
        this.a.a = 0;
        i = this.a.b;
        if (i != 0) {
            IvonaGui ivonaGui = this.a;
            i2 = this.a.b;
            ivonaGui.showDialog(i2);
            this.a.b = 0;
        }
    }
}
