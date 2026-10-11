package com.ivona.ttslib;

import android.content.DialogInterface;

/* compiled from: IvonaGui.java */
/* loaded from: classes.dex */
class j implements DialogInterface.OnClickListener {
    final /* synthetic */ boolean a;
    final /* synthetic */ IvonaGui b;

    j(IvonaGui ivonaGui, boolean z) {
        this.b = ivonaGui;
        this.a = z;
    }

    @Override // android.content.DialogInterface.OnClickListener
    public void onClick(DialogInterface dialogInterface, int i) {
        if (this.a) {
            this.b.finish();
        }
    }
}
