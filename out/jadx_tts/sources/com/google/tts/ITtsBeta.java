package com.google.tts;

import android.os.Binder;
import android.os.IBinder;
import android.os.IInterface;
import android.os.Parcel;
import com.google.tts.ITtsCallbackBeta;

/* loaded from: classes.dex */
public interface ITtsBeta extends IInterface {
    void addEarcon(String str, String str2, String str3, int i);

    void addEarconFile(String str, String str2, String str3);

    void addSpeech(String str, String str2, String str3, int i);

    void addSpeechFile(String str, String str2, String str3);

    boolean areDefaultsEnforced();

    String getDefaultEngine();

    String[] getLanguage();

    int isLanguageAvailable(String str, String str2, String str3, String[] strArr);

    boolean isSpeaking();

    int playEarcon(String str, String str2, int i, String[] strArr);

    int playSilence(String str, long j, int i, String[] strArr);

    int registerCallback(String str, ITtsCallbackBeta iTtsCallbackBeta);

    int setEngineByPackageName(String str);

    int setLanguage(String str, String str2, String str3, String str4);

    int setPitch(String str, int i);

    int setSpeechRate(String str, int i);

    int speak(String str, String str2, int i, String[] strArr);

    int stop(String str);

    boolean synthesizeToFile(String str, String str2, String[] strArr, String str3);

    int unregisterCallback(String str, ITtsCallbackBeta iTtsCallbackBeta);

    public abstract class Stub extends Binder implements ITtsBeta {
        private static final String DESCRIPTOR = "com.google.tts.ITtsBeta";
        static final int TRANSACTION_addEarcon = 13;
        static final int TRANSACTION_addEarconFile = 14;
        static final int TRANSACTION_addSpeech = 6;
        static final int TRANSACTION_addSpeechFile = 7;
        static final int TRANSACTION_areDefaultsEnforced = 20;
        static final int TRANSACTION_getDefaultEngine = 19;
        static final int TRANSACTION_getLanguage = 8;
        static final int TRANSACTION_isLanguageAvailable = 9;
        static final int TRANSACTION_isSpeaking = 4;
        static final int TRANSACTION_playEarcon = 12;
        static final int TRANSACTION_playSilence = 17;
        static final int TRANSACTION_registerCallback = 15;
        static final int TRANSACTION_setEngineByPackageName = 18;
        static final int TRANSACTION_setLanguage = 10;
        static final int TRANSACTION_setPitch = 2;
        static final int TRANSACTION_setSpeechRate = 1;
        static final int TRANSACTION_speak = 3;
        static final int TRANSACTION_stop = 5;
        static final int TRANSACTION_synthesizeToFile = 11;
        static final int TRANSACTION_unregisterCallback = 16;

        public Stub() {
            attachInterface(this, DESCRIPTOR);
        }

        public static ITtsBeta asInterface(IBinder iBinder) {
            if (iBinder == null) {
                return null;
            }
            IInterface queryLocalInterface = iBinder.queryLocalInterface(DESCRIPTOR);
            if (queryLocalInterface != null && (queryLocalInterface instanceof ITtsBeta)) {
                return (ITtsBeta) queryLocalInterface;
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
                    int speechRate = setSpeechRate(parcel.readString(), parcel.readInt());
                    parcel2.writeNoException();
                    parcel2.writeInt(speechRate);
                    return true;
                case 2:
                    parcel.enforceInterface(DESCRIPTOR);
                    int pitch = setPitch(parcel.readString(), parcel.readInt());
                    parcel2.writeNoException();
                    parcel2.writeInt(pitch);
                    return true;
                case 3:
                    parcel.enforceInterface(DESCRIPTOR);
                    int speak = speak(parcel.readString(), parcel.readString(), parcel.readInt(), parcel.createStringArray());
                    parcel2.writeNoException();
                    parcel2.writeInt(speak);
                    return true;
                case TRANSACTION_isSpeaking /* 4 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    boolean isSpeaking = isSpeaking();
                    parcel2.writeNoException();
                    parcel2.writeInt(isSpeaking ? 1 : 0);
                    return true;
                case TRANSACTION_stop /* 5 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    int stop = stop(parcel.readString());
                    parcel2.writeNoException();
                    parcel2.writeInt(stop);
                    return true;
                case TRANSACTION_addSpeech /* 6 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    addSpeech(parcel.readString(), parcel.readString(), parcel.readString(), parcel.readInt());
                    parcel2.writeNoException();
                    return true;
                case TRANSACTION_addSpeechFile /* 7 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    addSpeechFile(parcel.readString(), parcel.readString(), parcel.readString());
                    parcel2.writeNoException();
                    return true;
                case TRANSACTION_getLanguage /* 8 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    String[] language = getLanguage();
                    parcel2.writeNoException();
                    parcel2.writeStringArray(language);
                    return true;
                case TRANSACTION_isLanguageAvailable /* 9 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    int isLanguageAvailable = isLanguageAvailable(parcel.readString(), parcel.readString(), parcel.readString(), parcel.createStringArray());
                    parcel2.writeNoException();
                    parcel2.writeInt(isLanguageAvailable);
                    return true;
                case TRANSACTION_setLanguage /* 10 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    int language2 = setLanguage(parcel.readString(), parcel.readString(), parcel.readString(), parcel.readString());
                    parcel2.writeNoException();
                    parcel2.writeInt(language2);
                    return true;
                case TRANSACTION_synthesizeToFile /* 11 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    boolean synthesizeToFile = synthesizeToFile(parcel.readString(), parcel.readString(), parcel.createStringArray(), parcel.readString());
                    parcel2.writeNoException();
                    parcel2.writeInt(synthesizeToFile ? 1 : 0);
                    return true;
                case TRANSACTION_playEarcon /* 12 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    int playEarcon = playEarcon(parcel.readString(), parcel.readString(), parcel.readInt(), parcel.createStringArray());
                    parcel2.writeNoException();
                    parcel2.writeInt(playEarcon);
                    return true;
                case TRANSACTION_addEarcon /* 13 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    addEarcon(parcel.readString(), parcel.readString(), parcel.readString(), parcel.readInt());
                    parcel2.writeNoException();
                    return true;
                case TRANSACTION_addEarconFile /* 14 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    addEarconFile(parcel.readString(), parcel.readString(), parcel.readString());
                    parcel2.writeNoException();
                    return true;
                case TRANSACTION_registerCallback /* 15 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    int registerCallback = registerCallback(parcel.readString(), ITtsCallbackBeta.Stub.asInterface(parcel.readStrongBinder()));
                    parcel2.writeNoException();
                    parcel2.writeInt(registerCallback);
                    return true;
                case TRANSACTION_unregisterCallback /* 16 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    int unregisterCallback = unregisterCallback(parcel.readString(), ITtsCallbackBeta.Stub.asInterface(parcel.readStrongBinder()));
                    parcel2.writeNoException();
                    parcel2.writeInt(unregisterCallback);
                    return true;
                case TRANSACTION_playSilence /* 17 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    int playSilence = playSilence(parcel.readString(), parcel.readLong(), parcel.readInt(), parcel.createStringArray());
                    parcel2.writeNoException();
                    parcel2.writeInt(playSilence);
                    return true;
                case TRANSACTION_setEngineByPackageName /* 18 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    int engineByPackageName = setEngineByPackageName(parcel.readString());
                    parcel2.writeNoException();
                    parcel2.writeInt(engineByPackageName);
                    return true;
                case TRANSACTION_getDefaultEngine /* 19 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    String defaultEngine = getDefaultEngine();
                    parcel2.writeNoException();
                    parcel2.writeString(defaultEngine);
                    return true;
                case TRANSACTION_areDefaultsEnforced /* 20 */:
                    parcel.enforceInterface(DESCRIPTOR);
                    boolean areDefaultsEnforced = areDefaultsEnforced();
                    parcel2.writeNoException();
                    parcel2.writeInt(areDefaultsEnforced ? 1 : 0);
                    return true;
                case 1598968902:
                    parcel2.writeString(DESCRIPTOR);
                    return true;
                default:
                    return super.onTransact(i, parcel, parcel2, i2);
            }
        }

        class Proxy implements ITtsBeta {
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

            @Override // com.google.tts.ITtsBeta
            public int setSpeechRate(String str, int i) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeInt(i);
                    this.mRemote.transact(1, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readInt();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public int setPitch(String str, int i) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeInt(i);
                    this.mRemote.transact(2, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readInt();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public int speak(String str, String str2, int i, String[] strArr) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeString(str2);
                    obtain.writeInt(i);
                    obtain.writeStringArray(strArr);
                    this.mRemote.transact(3, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readInt();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
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

            @Override // com.google.tts.ITtsBeta
            public int stop(String str) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    this.mRemote.transact(Stub.TRANSACTION_stop, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readInt();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public void addSpeech(String str, String str2, String str3, int i) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeString(str2);
                    obtain.writeString(str3);
                    obtain.writeInt(i);
                    this.mRemote.transact(Stub.TRANSACTION_addSpeech, obtain, obtain2, 0);
                    obtain2.readException();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public void addSpeechFile(String str, String str2, String str3) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeString(str2);
                    obtain.writeString(str3);
                    this.mRemote.transact(Stub.TRANSACTION_addSpeechFile, obtain, obtain2, 0);
                    obtain2.readException();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public String[] getLanguage() {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    this.mRemote.transact(Stub.TRANSACTION_getLanguage, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.createStringArray();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public int isLanguageAvailable(String str, String str2, String str3, String[] strArr) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeString(str2);
                    obtain.writeString(str3);
                    obtain.writeStringArray(strArr);
                    this.mRemote.transact(Stub.TRANSACTION_isLanguageAvailable, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readInt();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public int setLanguage(String str, String str2, String str3, String str4) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeString(str2);
                    obtain.writeString(str3);
                    obtain.writeString(str4);
                    this.mRemote.transact(Stub.TRANSACTION_setLanguage, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readInt();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public boolean synthesizeToFile(String str, String str2, String[] strArr, String str3) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeString(str2);
                    obtain.writeStringArray(strArr);
                    obtain.writeString(str3);
                    this.mRemote.transact(Stub.TRANSACTION_synthesizeToFile, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readInt() != 0;
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public int playEarcon(String str, String str2, int i, String[] strArr) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeString(str2);
                    obtain.writeInt(i);
                    obtain.writeStringArray(strArr);
                    this.mRemote.transact(Stub.TRANSACTION_playEarcon, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readInt();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public void addEarcon(String str, String str2, String str3, int i) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeString(str2);
                    obtain.writeString(str3);
                    obtain.writeInt(i);
                    this.mRemote.transact(Stub.TRANSACTION_addEarcon, obtain, obtain2, 0);
                    obtain2.readException();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public void addEarconFile(String str, String str2, String str3) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeString(str2);
                    obtain.writeString(str3);
                    this.mRemote.transact(Stub.TRANSACTION_addEarconFile, obtain, obtain2, 0);
                    obtain2.readException();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public int registerCallback(String str, ITtsCallbackBeta iTtsCallbackBeta) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeStrongBinder(iTtsCallbackBeta != null ? iTtsCallbackBeta.asBinder() : null);
                    this.mRemote.transact(Stub.TRANSACTION_registerCallback, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readInt();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public int unregisterCallback(String str, ITtsCallbackBeta iTtsCallbackBeta) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeStrongBinder(iTtsCallbackBeta != null ? iTtsCallbackBeta.asBinder() : null);
                    this.mRemote.transact(Stub.TRANSACTION_unregisterCallback, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readInt();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public int playSilence(String str, long j, int i, String[] strArr) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    obtain.writeLong(j);
                    obtain.writeInt(i);
                    obtain.writeStringArray(strArr);
                    this.mRemote.transact(Stub.TRANSACTION_playSilence, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readInt();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public int setEngineByPackageName(String str) {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    obtain.writeString(str);
                    this.mRemote.transact(Stub.TRANSACTION_setEngineByPackageName, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readInt();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public String getDefaultEngine() {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    this.mRemote.transact(Stub.TRANSACTION_getDefaultEngine, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readString();
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }

            @Override // com.google.tts.ITtsBeta
            public boolean areDefaultsEnforced() {
                Parcel obtain = Parcel.obtain();
                Parcel obtain2 = Parcel.obtain();
                try {
                    obtain.writeInterfaceToken(Stub.DESCRIPTOR);
                    this.mRemote.transact(Stub.TRANSACTION_areDefaultsEnforced, obtain, obtain2, 0);
                    obtain2.readException();
                    return obtain2.readInt() != 0;
                } finally {
                    obtain2.recycle();
                    obtain.recycle();
                }
            }
        }
    }
}
