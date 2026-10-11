package com.ivona.ttslib;

import android.widget.SeekBar;
import android.widget.TextView;
import java.util.Locale;

/* compiled from: IvonaGui.java */
/* loaded from: classes.dex */
class o implements SeekBar.OnSeekBarChangeListener {
    final /* synthetic */ IvonaGui a;

    o(IvonaGui ivonaGui) {
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
        float f;
        float max = i / (seekBar.getMax() / 2);
        if (max < 1.0f) {
            f = (max * 0.5f) + 0.5f;
        } else {
            f = ((max - 1.0f) * 2.0f) + 1.0f;
        }
        ((TextView) this.a.findViewById(y.l)).setText(String.format(Locale.US, "%.1f", Float.valueOf(f)));
    }
}
