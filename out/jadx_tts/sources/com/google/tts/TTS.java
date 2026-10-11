package com.google.tts;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.pm.PackageManager;
import android.os.IBinder;
import android.os.RemoteException;
import android.util.Log;
import com.google.tts.ITTS;
import com.google.tts.ITTSCallback;

/* loaded from: classes.dex */
public class TTS {
    private static final int MIN_VER = 10;
    private a cb;
    private Context ctx;
    private ITTS itts;
    private ITTSCallback ittscallback;
    private ServiceConnection serviceConnection;
    private boolean showInstaller;
    private b speechCompletedCallback;
    private boolean started;
    private int version;
    private TTSVersionAlert versionAlert;

    public TTS(Context context, a aVar, boolean z) {
        this.cb = null;
        this.version = -1;
        this.started = false;
        this.showInstaller = false;
        this.versionAlert = null;
        this.speechCompletedCallback = null;
        this.showInstaller = z;
        this.ctx = context;
        this.cb = aVar;
        if (dataFilesCheck()) {
            initTts();
        }
    }

    public TTS(Context context, a aVar, TTSVersionAlert tTSVersionAlert) {
        this.cb = null;
        this.version = -1;
        this.started = false;
        this.showInstaller = false;
        this.versionAlert = null;
        this.speechCompletedCallback = null;
        this.showInstaller = true;
        this.versionAlert = tTSVersionAlert;
        this.ctx = context;
        this.cb = aVar;
        if (dataFilesCheck()) {
            initTts();
        }
    }

    public void setOnSpeechCompletedListener(b bVar) {
        this.speechCompletedCallback = bVar;
    }

    private boolean dataFilesCheck() {
        if (!ConfigurationManager.a()) {
            if (!this.showInstaller) {
                return false;
            }
            try {
                Context createPackageContext = this.ctx.createPackageContext("com.google.tts", 3);
                this.ctx.startActivity(new Intent(createPackageContext, createPackageContext.getClassLoader().loadClass("com.google.tts.ConfigurationManager")));
                return false;
            } catch (PackageManager.NameNotFoundException e) {
                e.printStackTrace();
            } catch (ClassNotFoundException e2) {
                e2.printStackTrace();
            }
        }
        return true;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void initTts() {
        this.started = false;
        this.serviceConnection = new ServiceConnection() { // from class: com.google.tts.TTS.1
            @Override // android.content.ServiceConnection
            public void onServiceConnected(ComponentName componentName, IBinder iBinder) {
                TTS.this.itts = ITTS.Stub.asInterface(iBinder);
                try {
                    TTS.this.version = TTS.this.itts.getVersion();
                    if (TTS.this.version < TTS.MIN_VER) {
                        if (TTS.this.showInstaller) {
                            if (TTS.this.versionAlert != null) {
                                TTS.this.versionAlert.show();
                            } else {
                                new TTSVersionAlert(TTS.this.ctx, null, null, null).show();
                            }
                        }
                    } else {
                        TTS.this.ittscallback = new ITTSCallback.Stub() { // from class: com.google.tts.TTS.1.1
                            @Override // com.google.tts.ITTSCallback
                            public void markReached(String str) {
                                if (TTS.this.speechCompletedCallback != null) {
                                    TTS.this.speechCompletedCallback.onSpeechCompleted();
                                }
                            }
                        };
                        TTS.this.itts.registerCallback(TTS.this.ittscallback);
                        TTS.this.started = true;
                        if (TTS.this.cb != null) {
                            TTS.this.cb.onInit(TTS.this.version);
                        }
                    }
                } catch (RemoteException e) {
                    TTS.this.initTts();
                }
            }

            @Override // android.content.ServiceConnection
            public void onServiceDisconnected(ComponentName componentName) {
                TTS.this.itts = null;
                TTS.this.cb = null;
                TTS.this.started = false;
            }
        };
        Intent intent = new Intent("android.intent.action.USE_TTS");
        intent.addCategory("android.intent.category.TTS");
        if (!this.ctx.bindService(intent, this.serviceConnection, 1) && this.showInstaller) {
            if (this.versionAlert != null) {
                this.versionAlert.show();
            } else {
                new TTSVersionAlert(this.ctx, null, null, null).show();
            }
        }
    }

    public void shutdown() {
        try {
            this.ctx.unbindService(this.serviceConnection);
        } catch (IllegalArgumentException e) {
        }
    }

    public void addSpeech(String str, String str2, int i) {
        if (this.started) {
            try {
                this.itts.addSpeech(str, str2, i);
            } catch (RemoteException e) {
                this.started = false;
                initTts();
            } catch (IllegalStateException e2) {
                this.started = false;
                initTts();
            } catch (NullPointerException e3) {
                this.started = false;
                initTts();
            }
        }
    }

    public void addSpeech(String str, String str2) {
        if (this.started) {
            try {
                this.itts.addSpeechFile(str, str2);
            } catch (RemoteException e) {
                this.started = false;
                initTts();
            } catch (IllegalStateException e2) {
                this.started = false;
                initTts();
            } catch (NullPointerException e3) {
                this.started = false;
                initTts();
            }
        }
    }

    public void speak(String str, int i, String[] strArr) {
        Log.i("TTS received: ", str);
        if (this.started) {
            try {
                this.itts.speak(str, i, strArr);
            } catch (RemoteException e) {
                Log.e("TTS", "RemoteException error.");
                this.started = false;
                initTts();
            } catch (IllegalStateException e2) {
                Log.e("TTS", "IllegalStateException error.");
                this.started = false;
                initTts();
            } catch (NullPointerException e3) {
                Log.e("TTS", "NullPointerException error.");
                this.started = false;
                initTts();
            }
        }
    }

    public void playEarcon(String str, int i, String[] strArr) {
        if (this.started) {
            try {
                this.itts.playEarcon(str, i, strArr);
            } catch (RemoteException e) {
                this.started = false;
                initTts();
            } catch (IllegalStateException e2) {
                this.started = false;
                initTts();
            } catch (NullPointerException e3) {
                this.started = false;
                initTts();
            }
        }
    }

    public void playEarcon(TTSEarcon tTSEarcon, int i, String[] strArr) {
        playEarcon(tTSEarcon.name(), i, strArr);
    }

    public boolean isSpeaking() {
        if (!this.started) {
            return false;
        }
        try {
            return this.itts.isSpeaking();
        } catch (RemoteException e) {
            this.started = false;
            initTts();
            return false;
        } catch (IllegalStateException e2) {
            this.started = false;
            initTts();
            return false;
        } catch (NullPointerException e3) {
            this.started = false;
            initTts();
            return false;
        }
    }

    public void stop() {
        if (this.started) {
            try {
                this.itts.stop();
            } catch (RemoteException e) {
                this.started = false;
                initTts();
            } catch (IllegalStateException e2) {
                this.started = false;
                initTts();
            } catch (NullPointerException e3) {
                this.started = false;
                initTts();
            }
        }
    }

    public int getVersion() {
        return this.version;
    }

    public void setEngine(TTSEngine tTSEngine) {
        if (this.started) {
            try {
                this.itts.setEngine(tTSEngine.toString());
            } catch (RemoteException e) {
                this.started = false;
                initTts();
            }
        }
    }

    public void setEngine(String str) {
        if (this.started) {
            try {
                this.itts.setEngine(str);
            } catch (RemoteException e) {
                this.started = false;
                initTts();
            }
        }
    }

    public void setSpeechRate(int i) {
        if (this.started) {
            try {
                this.itts.setSpeechRate(i);
            } catch (RemoteException e) {
                this.started = false;
                initTts();
            }
        }
    }

    public void setLanguage(String str) {
        if (this.started) {
            try {
                this.itts.setLanguage(str);
            } catch (RemoteException e) {
                this.started = false;
                initTts();
            }
        }
    }

    public boolean synthesizeToFile(String str, String[] strArr, String str2) {
        if (!this.started) {
            return false;
        }
        try {
            return this.itts.synthesizeToFile(str, strArr, str2);
        } catch (RemoteException e) {
            this.started = false;
            initTts();
            return false;
        } catch (IllegalStateException e2) {
            this.started = false;
            initTts();
            return false;
        } catch (NullPointerException e3) {
            this.started = false;
            initTts();
            return false;
        }
    }

    public void showVersionAlert() {
        if (this.started) {
            if (this.versionAlert != null) {
                this.versionAlert.show();
            } else {
                new TTSVersionAlert(this.ctx, null, null, null).show();
            }
        }
    }

    public static boolean isInstalled(Context context) {
        PackageManager packageManager = context.getPackageManager();
        Intent intent = new Intent("android.intent.action.USE_TTS");
        intent.addCategory("android.intent.category.TTS");
        return packageManager.resolveService(intent, 0) != null;
    }
}
