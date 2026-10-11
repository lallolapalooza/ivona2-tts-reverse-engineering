package com.google.android.vending.a;

import android.os.Binder;
import android.os.IBinder;
import android.os.IInterface;
import android.os.Parcel;

/* compiled from: ILicensingService.java */
/* loaded from: classes.dex */
public abstract class h extends Binder implements g {
    public static g a(IBinder iBinder) {
        if (iBinder == null) {
            return null;
        }
        IInterface queryLocalInterface = iBinder.queryLocalInterface("com.android.vending.licensing.ILicensingService");
        if (queryLocalInterface != null && (queryLocalInterface instanceof g)) {
            return (g) queryLocalInterface;
        }
        return new i(iBinder);
    }

    @Override // android.os.Binder
    public boolean onTransact(int i, Parcel parcel, Parcel parcel2, int i2) {
        switch (i) {
            case 1:
                parcel.enforceInterface("com.android.vending.licensing.ILicensingService");
                a(parcel.readLong(), parcel.readString(), e.a(parcel.readStrongBinder()));
                return true;
            case 1598968902:
                parcel2.writeString("com.android.vending.licensing.ILicensingService");
                return true;
            default:
                return super.onTransact(i, parcel, parcel2, i2);
        }
    }
}
