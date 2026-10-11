package com.google.android.vending.expansion.downloader;

import android.os.Parcel;
import android.os.Parcelable;

/* loaded from: classes.dex */
public class DownloadProgressInfo implements Parcelable {
    public static final Parcelable.Creator CREATOR = new b();
    public long a;
    public long b;
    public long c;
    public float d;

    @Override // android.os.Parcelable
    public int describeContents() {
        return 0;
    }

    @Override // android.os.Parcelable
    public void writeToParcel(Parcel parcel, int i) {
        parcel.writeLong(this.a);
        parcel.writeLong(this.b);
        parcel.writeLong(this.c);
        parcel.writeFloat(this.d);
    }

    public DownloadProgressInfo(Parcel parcel) {
        this.a = parcel.readLong();
        this.b = parcel.readLong();
        this.c = parcel.readLong();
        this.d = parcel.readFloat();
    }

    public DownloadProgressInfo(long j, long j2, long j3, float f) {
        this.a = j;
        this.b = j2;
        this.c = j3;
        this.d = f;
    }
}
