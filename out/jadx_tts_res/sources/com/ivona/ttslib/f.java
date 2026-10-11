package com.ivona.ttslib;

import android.widget.ImageView;
import android.widget.SlidingDrawer;

/* compiled from: IvonaGui.java */
/* loaded from: classes.dex */
class f implements SlidingDrawer.OnDrawerOpenListener {
    final /* synthetic */ IvonaGui a;

    f(IvonaGui ivonaGui) {
        this.a = ivonaGui;
    }

    @Override // android.widget.SlidingDrawer.OnDrawerOpenListener
    public void onDrawerOpened() {
        ImageView imageView;
        imageView = this.a.i;
        imageView.setBackgroundResource(x.o);
    }
}
