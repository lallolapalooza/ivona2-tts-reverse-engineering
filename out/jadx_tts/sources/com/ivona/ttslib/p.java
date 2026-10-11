package com.ivona.ttslib;

import android.widget.SeekBar;
import android.widget.TextView;
import java.util.Locale;

/* compiled from: IvonaGui.java */
/* loaded from: classes.dex */
class p implements SeekBar.OnSeekBarChangeListener {
    final /* synthetic */ IvonaGui a;

    p(IvonaGui ivonaGui) {
        this.a = ivonaGui;
    }

    @Override // android.widget.SeekBar.OnSeekBarChangeListener
    public void onStopTrackingTouch(SeekBar seekBar) {
    }

    @Override // android.widget.SeekBar.OnSeekBarChangeListener
    public void onStartTrackingTouch(SeekBar seekBar) {
    }

    @Override // android.widget.SeekBar.OnSeekBarChangeListener
    public void onProgressChanged(SeekBar seekBar, int i, boolean z) {
        if (i > 100) {
            i = 100;
        }
        ((TextView) this.a.findViewById(y.k)).setText(String.format(Locale.US, "%.1f", Float.valueOf((seekBar.getMax() / 2) / (101 - i))));
    }
}
