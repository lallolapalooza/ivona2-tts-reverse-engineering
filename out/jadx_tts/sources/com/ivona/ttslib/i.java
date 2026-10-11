package com.ivona.ttslib;

import android.content.DialogInterface;
import android.content.Intent;
import android.net.Uri;

/* compiled from: IvonaGui.java */
/* loaded from: classes.dex */
class i implements DialogInterface.OnClickListener {
    final /* synthetic */ String a;
    final /* synthetic */ String b;
    final /* synthetic */ IvonaGui c;

    i(IvonaGui ivonaGui, String str, String str2) {
        this.c = ivonaGui;
        this.a = str;
        this.b = str2;
    }

    @Override // android.content.DialogInterface.OnClickListener
    public void onClick(DialogInterface dialogInterface, int i) {
        Intent intent = new Intent("android.intent.action.VIEW");
        if (this.a != null) {
            intent.setData(Uri.parse("market://details?id=" + this.a));
        } else if (this.b != null) {
            intent.setData(Uri.parse("market://" + this.b));
        }
        this.c.startActivity(intent);
        this.c.finish();
    }
}
