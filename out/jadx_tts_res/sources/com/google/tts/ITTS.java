package com.google.tts;

import android.os.Binder;
import android.os.IBinder;
import android.os.IInterface;
import android.os.Parcel;
import com.google.tts.ITTSCallback;

/* loaded from: classes.dex */
public interface ITTS extends IInterface {
    void addEarcon(String str, String str2, int i);

    void addEarconFile(String str, String str2);

    void addSpeech(String str, String str2, int i);

    void addSpeechFile(String str, String str2);

    int getVersion();

    boolean isSpeaking();

    void playEarcon(String str, int i, String[] strArr);

    void registerCallback(ITTSCallback iTTSCallback);

    void setEngine(String str);

    void setLanguage(String str);

    void setSpeechRate(int i);

    void speak(String str, int i, String[] strArr);

    void stop();

    boolean synthesizeToFile(String str, String[] strArr, String str2);

    void unregisterCallback(ITTSCallback iTTSCallback);

    public abstract class Stub extends Binder implements ITTS {
        private static final String DESCRIPTOR = "com.google.tts.ITTS";
        static final int TRANSACTION_addEarcon = 12;
        static final int TRANSACTION_addEarconFile = 13;
        static final int TRANSACTION_addSpeech = 6;
        static final int TRANSACTION_addSpeechFile = 7;
        static final int TRANSACTION_getVersion = 8;
        static final int TRANSACTION_isSpeaking = 4;
        static final int TRANSACTION_playEarcon = 11;
        static final int TRANSACTION_registerCallback = 14;
        static final int TRANSACTION_setEngine = 1;
        static final int TRANSACTION_setLanguage = 9;
        static final int TRANSACTION_setSpeechRate = 2;
        static final int TRANSACTION_speak = 3;
        static final int TRANSACTION_stop = 5;
        static final int TRANSACTION_synthesizeToFile = 10;
        static final int TRANSACTION_unregisterCallback = 15;

        public Stub() {
            attachInterface(this, DESCRIPTOR);
        }

        public static ITTS asInterface(IBinder iBinder) {
            if (iBinder == null) {
                return null;
            }
            IInterface queryLocalInterface = iBinder.queryLocalInterface(DESCRIPTOR);
            if (queryLocalInterface != null && (queryLocalInterface instanceof ITTS)) {
                return (ITTS) queryLocalInterface;
            }
            return new Proxy(iBinder);
        }

        @Override // android.os.IInterface
        public IBinder asBinder() {
            return this;
        }

        @Override // android.os.Binder
        public boolean onTransact(int i, Parcel parcel, Parcel parcel2, int i2) {
            switch (i) {
                case 1:
                    parcel.enforceInterface(DESCRIPTOR);
                    setEngine(parcel.readString());
                    parcel2.writeNoException();
                    return true;
                case 2:
                    parcel.enforceInterface(DESCRIPTOR);
                    setSpeechRate(parcel.readInt());
                    parcel2.writeNoException();
                    return true;
                case 3:
                    parcel.enforceInterface(DESCRIPTOR);
                    speak(parcel.readString(), parcel.readInt(), parcel.createStringArray());
                    parcel2.writeNoException();
                    return true;
                case TRANSACTION_isSpeaking /* 4 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    boolean isSpeaking = isSpeaking();
                    parcel2.writeNoException();
                    parcel2.writeInt(isSpeaking ? 1 : 0);
                    return true;
                case TRANSACTION_stop /* 5 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    stop();
                    parcel2.writeNoException();
                    return true;
                case TRANSACTION_addSpeech /* 6 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    addSpeech(parcel.readString(), parcel.readString(), parcel.readInt());
                    parcel2.writeNoException();
                    return true;
                case TRANSACTION_addSpeechFile /* 7 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    addSpeechFile(parcel.readString(), parcel.readString());
                    parcel2.writeNoException();
                    return true;
                case TRANSACTION_getVersion /* 8 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    int version = getVersion();
                    parcel2.writeNoException();
                    parcel2.writeInt(version);
                    return true;
                case TRANSACTION_setLanguage /* 9 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    setLanguage(parcel.readString());
                    parcel2.writeNoException();
                    return true;
                case TRANSACTION_synthesizeToFile /* 10 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    boolean synthesizeToFile = synthesizeToFile(parcel.readString(), parcel.createStringArray(), parcel.readString());
                    parcel2.writeNoException();
                    parcel2.writeInt(synthesizeToFile ? 1 : 0);
                    return true;
                case TRANSACTION_playEarcon /* 11 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    playEarcon(parcel.readString(), parcel.readInt(), parcel.createStringArray());
                    parcel2.writeNoException();
                    return true;
                case TRANSACTION_addEarcon /* 12 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    addEarcon(parcel.readString(), parcel.readString(), parcel.readInt());
                    parcel2.writeNoException();
                    return true;
                case TRANSACTION_addEarconFile /* 13 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    addEarconFile(parcel.readString(), parcel.readString());
                    parcel2.writeNoException();
                    return true;
                case TRANSACTION_registerCallback /* 14 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    registerCallback(ITTSCallback.Stub.asInterface(parcel.readStrongBinder()));
                    parcel2.writeNoException();
                    return true;
                case TRANSACTION_unregisterCallback /* 15 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    unregisterCallback(ITTSCallback.Stub.asInterface(parcel.readStrongBinder()));
                    parcel2.writeNoException();
                    return true;
                case 1598968902:
                    parcel2.writeString(DESCRIPTOR);
                    return true;
                default:
                    return super.onTransact(i, parcel, parcel2, i2);
            }
        }

        class Proxy implements ITTS {
            private IBinder mRemote;

            Proxy(IBinder iBinder) {
                this.mRemote = iBinder;
            }

            @Override // android.os.IInterface
            public IBinder asBinder() {
                return this.mRemote;
            }

            public String getInterfaceDescriptor() {
                return Stub.DESCRIPTOR;
            }

            @Override // com.google.tts.ITTS
            public void setEngine(String str) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    this.mRemote.transact(1, obtain, obtain2, 0);
                    obtain2.readException();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITTS
            public void setSpeechRate(int i) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeInt(i);
                    this.mRemote.transact(2, obtain, obtain2, 0);
                    obtain2.readException();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITTS
            public void speak(String str, int i, String[] strArr) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeInt(i);
                    obtain.writeStringArray(strArr);
                    this.mRemote.transact(3, obtain, obtain2, 0);
                    obtain2.readException();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITTS
            public boolean isSpeaking() {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    this.mRemote.transact(Stub.TRANSACTION_isSpeaking, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readInt() != 0;
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITTS
            public void stop() {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    this.mRemote.transact(Stub.TRANSACTION_stop, obtain, obtain2, 0);
                    obtain2.readException();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITTS
            public void addSpeech(String str, String str2, int i) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeString(str2);
                    obtain.writeInt(i);
                    this.mRemote.transact(Stub.TRANSACTION_addSpeech, obtain, obtain2, 0);
                    obtain2.readException();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITTS
            public void addSpeechFile(String str, String str2) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeString(str2);
                    this.mRemote.transact(Stub.TRANSACTION_addSpeechFile, obtain, obtain2, 0);
                    obtain2.readException();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITTS
            public int getVersion() {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    this.mRemote.transact(Stub.TRANSACTION_getVersion, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readInt();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITTS
            public void setLanguage(String str) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    this.mRemote.transact(Stub.TRANSACTION_setLanguage, obtain, obtain2, 0);
                    obtain2.readException();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITTS
            public boolean synthesizeToFile(String str, String[] strArr, String str2) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeStringArray(strArr);
                    obtain.writeString(str2);
                    this.mRemote.transact(Stub.TRANSACTION_synthesizeToFile, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readInt() != 0;
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITTS
            public void playEarcon(String str, int i, String[] strArr) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeInt(i);
                    obtain.writeStringArray(strArr);
                    this.mRemote.transact(Stub.TRANSACTION_playEarcon, obtain, obtain2, 0);
                    obtain2.readException();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITTS
            public void addEarcon(String str, String str2, int i) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeString(str2);
                    obtain.writeInt(i);
                    this.mRemote.transact(Stub.TRANSACTION_addEarcon, obtain, obtain2, 0);
                    obtain2.readException();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITTS
            public void addEarconFile(String str, String str2) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeString(str2);
                    this.mRemote.transact(Stub.TRANSACTION_addEarconFile, obtain, obtain2, 0);
                    obtain2.readException();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITTS
            public void registerCallback(ITTSCallback iTTSCallback) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeStrongBinder(iTTSCallback != null ? iTTSCallback.asBinder() : null);
                    this.mRemote.transact(Stub.TRANSACTION_registerCallback, obtain, obtain2, 0);
                    obtain2.readException();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITTS
            public void unregisterCallback(ITTSCallback iTTSCallback) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeStrongBinder(iTTSCallback != null ? iTTSCallback.asBinder() : null);
                    this.mRemote.transact(Stub.TRANSACTION_unregisterCallback, obtain, obtain2, 0);
                    obtain2.readException();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }
        }
    }
}
