package com.google.android.vending.a;

import android.os.IBinder;
import android.os.Parcel;

/* compiled from: ILicenseResultListener.java */
/* loaded from: classes.dex */
class f implements d {
    private final IBinder a;

    f(IBinder iBinder) {
        this.a = iBinder;
    }

    @Override // android.os.IInterface
    public IBinder asBinder() {
        return this.a;
    }

    @Override // com.google.android.vending.a.d
    public void a(int i, String str, String str2) {
        Parcel obtain = Parcel.obtain();
        try {
            obtain.writeInterfaceToken("com.android.vending.licensing.ILicenseResultListener");
            obtain.writeInt(i);
            obtain.writeString(str);
            obtain.writeString(str2);
            this.a.transact(1, obtain, null, 1);
        } finally {
            obtain.recycle();
        }
    }
}
