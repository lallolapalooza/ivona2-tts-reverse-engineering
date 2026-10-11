package com.google.android.vending.a;

import android.os.Binder;
import android.os.IBinder;
import android.os.IInterface;
import android.os.Parcel;

/* compiled from: ILicenseResultListener.java */
/* loaded from: classes.dex */
public abstract class e extends Binder implements d {
    public e() {
        attachInterface(this, "com.android.vending.licensing.ILicenseResultListener");
    }

    public static d a(IBinder iBinder) {
        if (iBinder == null) {
            return null;
        }
        IInterface queryLocalInterface = iBinder.queryLocalInterface("com.android.vending.licensing.ILicenseResultListener");
        if (queryLocalInterface != null && (queryLocalInterface instanceof d)) {
            return (d) queryLocalInterface;
        }
        return new f(iBinder);
    }

    @Override // android.os.IInterface
    public IBinder asBinder() {
        return this;
    }

    @Override // android.os.Binder
    public boolean onTransact(int i, Parcel parcel, Parcel parcel2, int i2) {
        switch (i) {
            case 1:
                parcel.enforceInterface("com.android.vending.licensing.ILicenseResultListener");
                a(parcel.readInt(), parcel.readString(), parcel.readString());
                return true;
            case 1598968902:
                parcel2.writeString("com.android.vending.licensing.ILicenseResultListener");
                return true;
            default:
                return super.onTransact(i, parcel, parcel2, i2);
        }
    }
}
