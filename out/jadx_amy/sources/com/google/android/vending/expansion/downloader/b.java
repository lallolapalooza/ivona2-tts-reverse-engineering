package com.google.android.vending.expansion.downloader;

import android.os.Parcel;
import android.os.Parcelable;

/* compiled from: DownloadProgressInfo.java */
/* loaded from: classes.dex */
final class b implements Parcelable.Creator {
    b() {
    }

    @Override // android.os.Parcelable.Creator
    /* renamed from: a, reason: merged with bridge method [inline-methods] */
    public DownloadProgressInfo createFromParcel(Parcel parcel) {
        return new DownloadProgressInfo(parcel);
    }

    @Override // android.os.Parcelable.Creator
    /* renamed from: a, reason: merged with bridge method [inline-methods] */
    public DownloadProgressInfo[] newArray(int i) {
        return new DownloadProgressInfo[i];
    }
}
