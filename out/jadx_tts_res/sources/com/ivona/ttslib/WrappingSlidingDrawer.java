package com.ivona.ttslib;

import android.content.Context;
import android.util.AttributeSet;
import android.view.View;
import android.widget.SlidingDrawer;

/* loaded from: classes.dex */
public class WrappingSlidingDrawer extends SlidingDrawer {
    private final int mTopOffset;
    private final boolean mVertical;

    public WrappingSlidingDrawer(Context context, AttributeSet attributeSet, int i) {
        super(context, attributeSet, i);
        this.mTopOffset = attributeSet.getAttributeIntValue("android", "topOffset", 0);
        this.mVertical = false;
    }

    public WrappingSlidingDrawer(Context context, AttributeSet attributeSet) {
        super(context, attributeSet);
        this.mTopOffset = attributeSet.getAttributeIntValue("android", "topOffset", 0);
        this.mVertical = false;
    }

    @Override // android.widget.SlidingDrawer, android.view.View
    protected void onMeasure(int i, int i2) {
        int measuredWidth;
        int measuredHeight;
        int mode = View.MeasureSpec.getMode(i);
        int size = View.MeasureSpec.getSize(i);
        int mode2 = View.MeasureSpec.getMode(i2);
        int size2 = View.MeasureSpec.getSize(i2);
        if (mode == 0 || mode2 == 0) {
            throw new RuntimeException("SlidingDrawer cannot have UNSPECIFIED dimensions");
        }
        View handle = getHandle();
        View content = getContent();
        measureChild(handle, i, i2);
        if (this.mVertical) {
            content.measure(i, View.MeasureSpec.makeMeasureSpec((size2 - handle.getMeasuredHeight()) - this.mTopOffset, mode2));
            int measuredHeight2 = content.getMeasuredHeight() + handle.getMeasuredHeight() + this.mTopOffset;
            int measuredWidth2 = content.getMeasuredWidth();
            if (handle.getMeasuredWidth() > measuredWidth2) {
                measuredWidth2 = handle.getMeasuredWidth();
            }
            measuredWidth = measuredWidth2;
            measuredHeight = measuredHeight2;
        } else {
            getContent().measure(View.MeasureSpec.makeMeasureSpec((size - handle.getMeasuredWidth()) - this.mTopOffset, mode), i2);
            measuredWidth = content.getMeasuredWidth() + handle.getMeasuredWidth() + this.mTopOffset;
            measuredHeight = content.getMeasuredHeight();
            if (handle.getMeasuredHeight() > measuredHeight) {
                measuredHeight = handle.getMeasuredHeight();
            }
        }
        setMeasuredDimension(measuredWidth, measuredHeight);
    }
}
