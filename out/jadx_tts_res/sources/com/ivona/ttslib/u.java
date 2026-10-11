package com.ivona.ttslib;

import android.content.ComponentName;
import android.content.DialogInterface;
import android.content.Intent;

/* compiled from: IvonaGui.java */
/* loaded from: classes.dex */
class u implements DialogInterface.OnClickListener {
    final /* synthetic */ IvonaGui a;

    u(IvonaGui ivonaGui) {
        this.a = ivonaGui;
    }

    @Override // android.content.DialogInterface.OnClickListener
    public void onClick(DialogInterface dialogInterface, int i) {
        String str;
        Intent intent = new Intent("android.intent.action.MAIN");
        StringBuilder sb = new StringBuilder();
        str = this.a.h;
        intent.setComponent(ComponentName.unflattenFromString(sb.append(str).append("/.IvonaKendra").toString()));
        intent.addCategory("android.intent.category.LAUNCHER");
        this.a.startActivity(intent);
    }
}
