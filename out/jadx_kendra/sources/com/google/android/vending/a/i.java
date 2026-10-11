package com.google.android.vending.a;

import android.os.IBinder;
import android.os.Parcel;

/* compiled from: ILicensingService.java */
/* loaded from: classes.dex */
class i implements g {
    private final IBinder a;

    i(IBinder iBinder) {
        this.a = iBinder;
    }

    @Override // android.os.IInterface
    public IBinder asBinder() {
        return this.a;
    }

    @Override // com.google.android.vending.a.g
    public void a(long j, String str, d dVar) {
        Parcel obtain = Parcel.obtain();
        try {
            obtain.writeInterfaceToken("com.android.vending.licensing.ILicensingService");
            obtain.writeLong(j);
            obtain.writeString(str);
            obtain.writeStrongBinder(dVar != null ? dVar.asBinder() : null);
            this.a.transact(1, obtain, null, 1);
        } finally {
            obtain.recycle();
        }
    }
}
