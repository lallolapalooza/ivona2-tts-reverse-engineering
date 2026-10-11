package com.ivona.ttslib;

import android.content.DialogInterface;

/* compiled from: IvonaGui.java */
/* loaded from: classes.dex */
class h implements DialogInterface.OnClickListener {
    final /* synthetic */ IvonaGui a;

    h(IvonaGui ivonaGui) {
        this.a = ivonaGui;
    }

    @Override // android.content.DialogInterface.OnClickListener
    public void onClick(DialogInterface dialogInterface, int i) {
        this.a.finish();
    }
}
