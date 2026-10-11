package com.ivona.ttslib;

import android.widget.ImageView;
import android.widget.SlidingDrawer;

/* compiled from: IvonaGui.java */
/* loaded from: classes.dex */
class n implements SlidingDrawer.OnDrawerCloseListener {
    final /* synthetic */ IvonaGui a;

    n(IvonaGui ivonaGui) {
        this.a = ivonaGui;
    }

    @Override // android.widget.SlidingDrawer.OnDrawerCloseListener
    public void onDrawerClosed() {
        ImageView imageView;
        imageView = this.a.i;
        imageView.setBackgroundResource(x.n);
    }
}
