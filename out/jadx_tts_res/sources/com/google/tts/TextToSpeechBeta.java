package com.google.tts;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.pm.PackageManager;
import android.os.IBinder;
import android.os.RemoteException;
import android.speech.tts.TextToSpeech;
import android.util.Log;
import com.google.tts.ITtsBeta;
import com.google.tts.ITtsCallbackBeta;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.HashMap;
import java.util.Locale;

/* loaded from: classes.dex */
public class TextToSpeechBeta extends TextToSpeech {
    public static final String ACTION_TTS_QUEUE_PROCESSING_COMPLETED = "android.speech.tts.TTS_QUEUE_PROCESSING_COMPLETED";
    public static final int ERROR = -1;
    public static final int LANG_AVAILABLE = 0;
    public static final int LANG_COUNTRY_AVAILABLE = 1;
    public static final int LANG_COUNTRY_VAR_AVAILABLE = 2;
    public static final int LANG_MISSING_DATA = -1;
    public static final int LANG_NOT_SUPPORTED = -2;
    public static final String NOT_ON_PLATFORM_TTS = "TextToSpeechBeta not installed - basic platform TextToSpeech does not support ";
    private static Method Platform_areDefaultsEnforced = null;
    private static Method Platform_getDefaultEngine = null;
    private static Method Platform_setEngineByPackageName = null;
    public static final int QUEUE_ADD = 1;
    public static final int QUEUE_FLUSH = 0;
    public static final int SUCCESS = 0;
    public static final String USING_PLATFORM_TTS = "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for ";
    private static d mInitListener;
    static TextToSpeech.OnInitListener platformOnInitListener;
    static boolean ttsBetaInstalled;
    private String[] mCachedParams;
    private Context mContext;
    private ITtsBeta mITts;
    private ITtsCallbackBeta mITtscallback;
    private String mPackageName;
    private ServiceConnection mServiceConnection;
    private final Object mStartLock;
    private boolean mStarted;

    static {
        initCompatibility();
        mInitListener = null;
        ttsBetaInstalled = false;
        platformOnInitListener = new c();
    }

    private static void initCompatibility() {
        try {
            Platform_areDefaultsEnforced = TextToSpeech.class.getMethod("areDefaultsEnforced", new Class[0]);
            Platform_getDefaultEngine = TextToSpeech.class.getMethod("getDefaultEngine", new Class[0]);
            Platform_setEngineByPackageName = TextToSpeech.class.getMethod("setEngineByPackageName", String.class);
        } catch (NoSuchMethodException e) {
        }
    }

    private static boolean usePlatform_areDefaultsEnforced(TextToSpeech textToSpeech) {
        try {
            return ((Boolean) Platform_areDefaultsEnforced.invoke(textToSpeech, new Object[0])).booleanValue();
        } catch (IllegalAccessException e) {
            System.err.println("unexpected " + e);
            return false;
        } catch (IllegalArgumentException e2) {
            e2.printStackTrace();
            return false;
        } catch (InvocationTargetException e3) {
            e3.printStackTrace();
            return false;
        }
    }

    private static String usePlatform_getDefaultEngine(TextToSpeech textToSpeech) {
        try {
            return (String) Platform_getDefaultEngine.invoke(textToSpeech, new Object[0]);
        } catch (IllegalAccessException e) {
            System.err.println("unexpected " + e);
            return Engine.DEFAULT_SYNTH;
        } catch (IllegalArgumentException e2) {
            e2.printStackTrace();
            return Engine.DEFAULT_SYNTH;
        } catch (InvocationTargetException e3) {
            e3.printStackTrace();
            return Engine.DEFAULT_SYNTH;
        }
    }

    private static int usePlatform_setEngineByPackageName(TextToSpeech textToSpeech, String str) {
        try {
            return ((Integer) Platform_setEngineByPackageName.invoke(textToSpeech, str)).intValue();
        } catch (IllegalAccessException e) {
            System.err.println("unexpected " + e);
            return -1;
        } catch (IllegalArgumentException e2) {
            e2.printStackTrace();
            return -1;
        } catch (InvocationTargetException e3) {
            e3.printStackTrace();
            return -1;
        }
    }

    public class Engine {
        public static final String ACTION_CHECK_TTS_DATA = "android.speech.tts.engine.CHECK_TTS_DATA";
        public static final String ACTION_INSTALL_TTS_DATA = "android.speech.tts.engine.INSTALL_TTS_DATA";
        public static final String ACTION_TTS_DATA_INSTALLED = "android.speech.tts.engine.TTS_DATA_INSTALLED";
        public static final int CHECK_VOICE_DATA_BAD_DATA = -1;
        public static final int CHECK_VOICE_DATA_FAIL = 0;
        public static final int CHECK_VOICE_DATA_MISSING_DATA = -2;
        public static final int CHECK_VOICE_DATA_MISSING_VOLUME = -3;
        public static final int CHECK_VOICE_DATA_PASS = 1;
        public static final int DEFAULT_PITCH = 100;
        public static final int DEFAULT_RATE = 100;
        public static final int DEFAULT_STREAM = 3;
        public static final String DEFAULT_SYNTH = "com.svox.pico";
        public static final String EXTRA_TTS_DATA_INSTALLED = "dataInstalled";
        public static final String EXTRA_VOICE_DATA_FILES = "dataFiles";
        public static final String EXTRA_VOICE_DATA_FILES_INFO = "dataFilesInfo";
        public static final String EXTRA_VOICE_DATA_ROOT_DIRECTORY = "dataRoot";
        public static final String KEY_PARAM_COUNTRY = "country";
        public static final String KEY_PARAM_ENGINE = "engine";
        public static final String KEY_PARAM_LANGUAGE = "language";
        public static final String KEY_PARAM_PITCH = "pitch";
        public static final String KEY_PARAM_RATE = "rate";
        public static final String KEY_PARAM_STREAM = "streamType";
        public static final String KEY_PARAM_UTTERANCE_ID = "utteranceId";
        public static final String KEY_PARAM_VARIANT = "variant";
        protected static final int NB_CACHED_PARAMS = 7;
        protected static final int PARAM_POSITION_COUNTRY = 4;
        protected static final int PARAM_POSITION_ENGINE = 12;
        protected static final int PARAM_POSITION_LANGUAGE = 2;
        protected static final int PARAM_POSITION_RATE = 0;
        protected static final int PARAM_POSITION_STREAM = 8;
        protected static final int PARAM_POSITION_UTTERANCE_ID = 10;
        protected static final int PARAM_POSITION_VARIANT = 6;
        public static final int USE_DEFAULTS = 0;

        public Engine() {
        }
    }

    public TextToSpeechBeta(Context context, d dVar) {
        super(context, platformOnInitListener);
        this.mITts = null;
        this.mITtscallback = null;
        this.mContext = null;
        this.mPackageName = "";
        this.mStarted = false;
        this.mStartLock = new Object();
        ttsBetaInstalled = isInstalled(context);
        mInitListener = dVar;
        if (ttsBetaInstalled) {
            super.shutdown();
            this.mContext = context;
            this.mPackageName = this.mContext.getPackageName();
            this.mCachedParams = new String[14];
            this.mCachedParams[0] = Engine.KEY_PARAM_RATE;
            this.mCachedParams[2] = Engine.KEY_PARAM_LANGUAGE;
            this.mCachedParams[4] = Engine.KEY_PARAM_COUNTRY;
            this.mCachedParams[6] = Engine.KEY_PARAM_VARIANT;
            this.mCachedParams[8] = Engine.KEY_PARAM_STREAM;
            this.mCachedParams[10] = Engine.KEY_PARAM_UTTERANCE_ID;
            this.mCachedParams[12] = Engine.KEY_PARAM_ENGINE;
            this.mCachedParams[1] = String.valueOf(100);
            Locale locale = Locale.getDefault();
            this.mCachedParams[3] = locale.getISO3Language();
            this.mCachedParams[5] = locale.getISO3Country();
            this.mCachedParams[7] = locale.getVariant();
            this.mCachedParams[9] = String.valueOf(3);
            this.mCachedParams[11] = "";
            this.mCachedParams[13] = "";
            initTts();
        }
    }

    private void initTts() {
        this.mStarted = false;
        this.mServiceConnection = new ServiceConnection() { // from class: com.google.tts.TextToSpeechBeta.2
            @Override // android.content.ServiceConnection
            public void onServiceConnected(ComponentName componentName, IBinder iBinder) {
                synchronized (TextToSpeechBeta.this.mStartLock) {
                    TextToSpeechBeta.this.mITts = ITtsBeta.Stub.asInterface(iBinder);
                    TextToSpeechBeta.this.mStarted = true;
                    TextToSpeechBeta.this.setEngineByPackageNameExtended(TextToSpeechBeta.this.getDefaultEngineExtended());
                    TextToSpeechBeta.this.setLanguage(TextToSpeechBeta.this.getLanguage());
                    if (TextToSpeechBeta.mInitListener != null) {
                        try {
                            TextToSpeechBeta.mInitListener.a(0, TextToSpeechBeta.this.mContext.getPackageManager().getPackageInfo("com.google.tts", 0).versionCode);
                        } catch (PackageManager.NameNotFoundException e) {
                            e.printStackTrace();
                        }
                    }
                }
            }

            @Override // android.content.ServiceConnection
            public void onServiceDisconnected(ComponentName componentName) {
                synchronized (TextToSpeechBeta.this.mStartLock) {
                    TextToSpeechBeta.this.mITts = null;
                    TextToSpeechBeta.mInitListener = null;
                    TextToSpeechBeta.this.mStarted = false;
                }
            }
        };
        Intent intent = new Intent("com.google.intent.action.START_TTS_SERVICE_BETA");
        intent.addCategory("com.google.intent.category.TTS_BETA");
        this.mContext.bindService(intent, this.mServiceConnection, 1);
    }

    @Override // android.speech.tts.TextToSpeech
    public void shutdown() {
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for shutdown");
            super.shutdown();
        } else {
            try {
                this.mContext.unbindService(this.mServiceConnection);
            } catch (IllegalArgumentException e) {
            }
        }
    }

    @Override // android.speech.tts.TextToSpeech
    public int addSpeech(String str, String str2, int i) {
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for addSpeech");
            return super.addSpeech(str, str2, i);
        }
        synchronized (this.mStartLock) {
            if (!this.mStarted) {
                return -1;
            }
            try {
                try {
                    this.mITts.addSpeech(this.mPackageName, str, str2, i);
                    return 0;
                } catch (IllegalStateException e) {
                    Log.e("TextToSpeech.java - addSpeech", "IllegalStateException");
                    e.printStackTrace();
                    this.mStarted = false;
                    initTts();
                    return -1;
                }
            } catch (RemoteException e2) {
                Log.e("TextToSpeech.java - addSpeech", "RemoteException");
                e2.printStackTrace();
                this.mStarted = false;
                initTts();
                return -1;
            } catch (NullPointerException e3) {
                Log.e("TextToSpeech.java - addSpeech", "NullPointerException");
                e3.printStackTrace();
                this.mStarted = false;
                initTts();
                return -1;
            }
        }
    }

    @Override // android.speech.tts.TextToSpeech
    public int addSpeech(String str, String str2) {
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for addSpeech");
            return super.addSpeech(str, str2);
        }
        synchronized (this.mStartLock) {
            if (!this.mStarted) {
                return -1;
            }
            try {
                try {
                    this.mITts.addSpeechFile(this.mPackageName, str, str2);
                    return 0;
                } catch (IllegalStateException e) {
                    Log.e("TextToSpeech.java - addSpeech", "IllegalStateException");
                    e.printStackTrace();
                    this.mStarted = false;
                    initTts();
                    return -1;
                }
            } catch (RemoteException e2) {
                Log.e("TextToSpeech.java - addSpeech", "RemoteException");
                e2.printStackTrace();
                this.mStarted = false;
                initTts();
                return -1;
            } catch (NullPointerException e3) {
                Log.e("TextToSpeech.java - addSpeech", "NullPointerException");
                e3.printStackTrace();
                this.mStarted = false;
                initTts();
                return -1;
            }
        }
    }

    @Override // android.speech.tts.TextToSpeech
    public int addEarcon(String str, String str2, int i) {
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for addEarcon");
            return super.addEarcon(str, str2, i);
        }
        synchronized (this.mStartLock) {
            if (!this.mStarted) {
                return -1;
            }
            try {
                try {
                    this.mITts.addEarcon(this.mPackageName, str, str2, i);
                    return 0;
                } catch (IllegalStateException e) {
                    Log.e("TextToSpeech.java - addEarcon", "IllegalStateException");
                    e.printStackTrace();
                    this.mStarted = false;
                    initTts();
                    return -1;
                }
            } catch (RemoteException e2) {
                Log.e("TextToSpeech.java - addEarcon", "RemoteException");
                e2.printStackTrace();
                this.mStarted = false;
                initTts();
                return -1;
            } catch (NullPointerException e3) {
                Log.e("TextToSpeech.java - addEarcon", "NullPointerException");
                e3.printStackTrace();
                this.mStarted = false;
                initTts();
                return -1;
            }
        }
    }

    @Override // android.speech.tts.TextToSpeech
    public int addEarcon(String str, String str2) {
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for addEarcon");
            return super.addEarcon(str, str2);
        }
        synchronized (this.mStartLock) {
            if (!this.mStarted) {
                return -1;
            }
            try {
                try {
                    this.mITts.addEarconFile(this.mPackageName, str, str2);
                    return 0;
                } catch (IllegalStateException e) {
                    Log.e("TextToSpeech.java - addEarcon", "IllegalStateException");
                    e.printStackTrace();
                    this.mStarted = false;
                    initTts();
                    return -1;
                }
            } catch (RemoteException e2) {
                Log.e("TextToSpeech.java - addEarcon", "RemoteException");
                e2.printStackTrace();
                this.mStarted = false;
                initTts();
                return -1;
            } catch (NullPointerException e3) {
                Log.e("TextToSpeech.java - addEarcon", "NullPointerException");
                e3.printStackTrace();
                this.mStarted = false;
                initTts();
                return -1;
            }
        }
    }

    @Override // android.speech.tts.TextToSpeech
    public int speak(String str, int i, HashMap hashMap) {
        int i2;
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for speak");
            return super.speak(str, i, hashMap);
        }
        synchronized (this.mStartLock) {
            Log.i("TTS received: ", str);
            if (!this.mStarted) {
                i2 = -1;
            } else {
                try {
                    if (hashMap != null) {
                        try {
                            try {
                                if (!hashMap.isEmpty()) {
                                    String str2 = (String) hashMap.get(Engine.KEY_PARAM_STREAM);
                                    if (str2 != null) {
                                        this.mCachedParams[9] = str2;
                                    }
                                    String str3 = (String) hashMap.get(Engine.KEY_PARAM_UTTERANCE_ID);
                                    if (str3 != null) {
                                        this.mCachedParams[11] = str3;
                                    }
                                    String str4 = (String) hashMap.get(Engine.KEY_PARAM_ENGINE);
                                    if (str4 != null) {
                                        this.mCachedParams[13] = str4;
                                    }
                                }
                            } catch (RemoteException e) {
                                Log.e("TextToSpeech.java - speak", "RemoteException");
                                e.printStackTrace();
                                this.mStarted = false;
                                initTts();
                                i2 = -1;
                            }
                        } catch (IllegalStateException e2) {
                            Log.e("TextToSpeech.java - speak", "IllegalStateException");
                            e2.printStackTrace();
                            this.mStarted = false;
                            initTts();
                            i2 = -1;
                        } catch (NullPointerException e3) {
                            Log.e("TextToSpeech.java - speak", "NullPointerException");
                            e3.printStackTrace();
                            this.mStarted = false;
                            initTts();
                            i2 = -1;
                        }
                    }
                    i2 = this.mITts.speak(this.mPackageName, str, i, this.mCachedParams);
                } catch (Throwable th) {
                    i2 = -1;
                }
                resetCachedParams();
            }
        }
        return i2;
    }

    @Override // android.speech.tts.TextToSpeech
    public int playEarcon(String str, int i, HashMap hashMap) {
        int i2;
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for playEarcon");
            return super.playEarcon(str, i, hashMap);
        }
        synchronized (this.mStartLock) {
            if (!this.mStarted) {
                i2 = -1;
            } else {
                try {
                    if (hashMap != null) {
                        try {
                            try {
                                if (!hashMap.isEmpty()) {
                                    String str2 = (String) hashMap.get(Engine.KEY_PARAM_STREAM);
                                    if (str2 != null) {
                                        this.mCachedParams[9] = str2;
                                    }
                                    String str3 = (String) hashMap.get(Engine.KEY_PARAM_UTTERANCE_ID);
                                    if (str3 != null) {
                                        this.mCachedParams[11] = str3;
                                    }
                                }
                            } catch (NullPointerException e) {
                                Log.e("TextToSpeech.java - playEarcon", "NullPointerException");
                                e.printStackTrace();
                                this.mStarted = false;
                                initTts();
                                i2 = -1;
                            }
                        } catch (RemoteException e2) {
                            Log.e("TextToSpeech.java - playEarcon", "RemoteException");
                            e2.printStackTrace();
                            this.mStarted = false;
                            initTts();
                            i2 = -1;
                        } catch (IllegalStateException e3) {
                            Log.e("TextToSpeech.java - playEarcon", "IllegalStateException");
                            e3.printStackTrace();
                            this.mStarted = false;
                            initTts();
                            i2 = -1;
                        }
                    }
                    i2 = this.mITts.playEarcon(this.mPackageName, str, i, null);
                } catch (Throwable th) {
                    i2 = -1;
                }
                resetCachedParams();
            }
        }
        return i2;
    }

    @Override // android.speech.tts.TextToSpeech
    public int playSilence(long j, int i, HashMap hashMap) {
        int i2;
        String str;
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for playSilence");
            return super.playSilence(j, i, hashMap);
        }
        synchronized (this.mStartLock) {
            if (!this.mStarted) {
                i2 = -1;
            } else {
                try {
                    if (hashMap != null) {
                        try {
                            try {
                                if (!hashMap.isEmpty() && (str = (String) hashMap.get(Engine.KEY_PARAM_UTTERANCE_ID)) != null) {
                                    this.mCachedParams[11] = str;
                                }
                            } catch (NullPointerException e) {
                                Log.e("TextToSpeech.java - playSilence", "NullPointerException");
                                e.printStackTrace();
                                this.mStarted = false;
                                initTts();
                                i2 = -1;
                            }
                        } catch (RemoteException e2) {
                            Log.e("TextToSpeech.java - playSilence", "RemoteException");
                            e2.printStackTrace();
                            this.mStarted = false;
                            initTts();
                            i2 = -1;
                        } catch (IllegalStateException e3) {
                            Log.e("TextToSpeech.java - playSilence", "IllegalStateException");
                            e3.printStackTrace();
                            this.mStarted = false;
                            initTts();
                            i2 = -1;
                        }
                    }
                    i2 = this.mITts.playSilence(this.mPackageName, j, i, this.mCachedParams);
                } catch (Throwable th) {
                    i2 = -1;
                }
            }
        }
        return i2;
    }

    @Override // android.speech.tts.TextToSpeech
    public boolean isSpeaking() {
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for isSpeaking");
            return super.isSpeaking();
        }
        synchronized (this.mStartLock) {
            if (!this.mStarted) {
                return false;
            }
            try {
                try {
                    try {
                        return this.mITts.isSpeaking();
                    } catch (IllegalStateException e) {
                        Log.e("TextToSpeech.java - isSpeaking", "IllegalStateException");
                        e.printStackTrace();
                        this.mStarted = false;
                        initTts();
                        return false;
                    }
                } catch (RemoteException e2) {
                    Log.e("TextToSpeech.java - isSpeaking", "RemoteException");
                    e2.printStackTrace();
                    this.mStarted = false;
                    initTts();
                    return false;
                }
            } catch (NullPointerException e3) {
                Log.e("TextToSpeech.java - isSpeaking", "NullPointerException");
                e3.printStackTrace();
                this.mStarted = false;
                initTts();
                return false;
            }
        }
    }

    @Override // android.speech.tts.TextToSpeech
    public int stop() {
        int i;
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for stop");
            return super.stop();
        }
        synchronized (this.mStartLock) {
            i = -1;
            if (this.mStarted) {
                try {
                    try {
                        i = this.mITts.stop(this.mPackageName);
                    } catch (IllegalStateException e) {
                        Log.e("TextToSpeech.java - stop", "IllegalStateException");
                        e.printStackTrace();
                        this.mStarted = false;
                        initTts();
                    }
                } catch (RemoteException e2) {
                    Log.e("TextToSpeech.java - stop", "RemoteException");
                    e2.printStackTrace();
                    this.mStarted = false;
                    initTts();
                } catch (NullPointerException e3) {
                    Log.e("TextToSpeech.java - stop", "NullPointerException");
                    e3.printStackTrace();
                    this.mStarted = false;
                    initTts();
                }
            }
        }
        return i;
    }

    @Override // android.speech.tts.TextToSpeech
    public int setSpeechRate(float f) {
        int i = -1;
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech");
            return super.setSpeechRate(f);
        }
        synchronized (this.mStartLock) {
            if (this.mStarted) {
                if (f > 0.0f) {
                    try {
                        try {
                            try {
                                this.mCachedParams[1] = String.valueOf((int) (100.0f * f));
                                if (f > 0.0f) {
                                    i = 0;
                                }
                            } catch (IllegalStateException e) {
                                Log.e("TextToSpeech.java - setSpeechRate", "IllegalStateException");
                                e.printStackTrace();
                                this.mStarted = false;
                                initTts();
                            }
                        } catch (NullPointerException e2) {
                            Log.e("TextToSpeech.java - setSpeechRate", "NullPointerException");
                            e2.printStackTrace();
                            this.mStarted = false;
                            initTts();
                        }
                    } catch (Throwable th) {
                    }
                }
            }
        }
        return i;
    }

    @Override // android.speech.tts.TextToSpeech
    public int setPitch(float f) {
        int i;
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech");
            return super.setPitch(f);
        }
        synchronized (this.mStartLock) {
            i = -1;
            if (this.mStarted) {
                try {
                    if (f > 0.0f) {
                        try {
                            try {
                                i = this.mITts.setPitch(this.mPackageName, (int) (100.0f * f));
                            } catch (NullPointerException e) {
                                Log.e("TextToSpeech.java - setPitch", "NullPointerException");
                                e.printStackTrace();
                                this.mStarted = false;
                                initTts();
                            }
                        } catch (RemoteException e2) {
                            Log.e("TextToSpeech.java - setPitch", "RemoteException");
                            e2.printStackTrace();
                            this.mStarted = false;
                            initTts();
                        } catch (IllegalStateException e3) {
                            Log.e("TextToSpeech.java - setPitch", "IllegalStateException");
                            e3.printStackTrace();
                            this.mStarted = false;
                            initTts();
                        }
                    }
                } catch (Throwable th) {
                }
            }
        }
        return i;
    }

    @Override // android.speech.tts.TextToSpeech
    public int setLanguage(Locale locale) {
        int i;
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for setLanguage");
            return super.setLanguage(locale);
        }
        synchronized (this.mStartLock) {
            i = -2;
            if (this.mStarted) {
                try {
                    try {
                        this.mCachedParams[3] = locale.getISO3Language();
                        this.mCachedParams[5] = locale.getISO3Country();
                        this.mCachedParams[7] = locale.getVariant();
                        i = this.mITts.isLanguageAvailable(this.mCachedParams[3], this.mCachedParams[5], this.mCachedParams[7], this.mCachedParams);
                    } catch (NullPointerException e) {
                        Log.e("TextToSpeech.java - setLanguage", "NullPointerException");
                        e.printStackTrace();
                        this.mStarted = false;
                        initTts();
                    }
                } catch (RemoteException e2) {
                    Log.e("TextToSpeech.java - setLanguage", "RemoteException");
                    e2.printStackTrace();
                    this.mStarted = false;
                    initTts();
                } catch (IllegalStateException e3) {
                    Log.e("TextToSpeech.java - setLanguage", "IllegalStateException");
                    e3.printStackTrace();
                    this.mStarted = false;
                    initTts();
                }
            }
        }
        return i;
    }

    @Override // android.speech.tts.TextToSpeech
    public Locale getLanguage() {
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for getLanguage");
            return super.getLanguage();
        }
        synchronized (this.mStartLock) {
            if (!this.mStarted) {
                return null;
            }
            try {
                String[] language = this.mITts.getLanguage();
                if (language == null || language.length != 3) {
                    return null;
                }
                return new Locale(language[0], language[1], language[2]);
            } catch (RemoteException e) {
                Log.e("TextToSpeech.java - getLanguage", "RemoteException");
                e.printStackTrace();
                this.mStarted = false;
                initTts();
                return null;
            } catch (IllegalStateException e2) {
                Log.e("TextToSpeech.java - getLanguage", "IllegalStateException");
                e2.printStackTrace();
                this.mStarted = false;
                initTts();
                return null;
            } catch (NullPointerException e3) {
                Log.e("TextToSpeech.java - getLanguage", "NullPointerException");
                e3.printStackTrace();
                this.mStarted = false;
                initTts();
                return null;
            }
        }
    }

    @Override // android.speech.tts.TextToSpeech
    public int isLanguageAvailable(Locale locale) {
        int i;
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for isLanguageAvailable");
            return super.isLanguageAvailable(locale);
        }
        synchronized (this.mStartLock) {
            i = -2;
            if (this.mStarted) {
                try {
                    try {
                        i = this.mITts.isLanguageAvailable(locale.getISO3Language(), locale.getISO3Country(), locale.getVariant(), this.mCachedParams);
                    } catch (NullPointerException e) {
                        Log.e("TextToSpeech.java - isLanguageAvailable", "NullPointerException");
                        e.printStackTrace();
                        this.mStarted = false;
                        initTts();
                    }
                } catch (RemoteException e2) {
                    Log.e("TextToSpeech.java - isLanguageAvailable", "RemoteException");
                    e2.printStackTrace();
                    this.mStarted = false;
                    initTts();
                } catch (IllegalStateException e3) {
                    Log.e("TextToSpeech.java - isLanguageAvailable", "IllegalStateException");
                    e3.printStackTrace();
                    this.mStarted = false;
                    initTts();
                }
            }
        }
        return i;
    }

    @Override // android.speech.tts.TextToSpeech
    public int synthesizeToFile(String str, HashMap hashMap, String str2) {
        int i;
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for synthesizeToFile");
            return super.synthesizeToFile(str, hashMap, str2);
        }
        synchronized (this.mStartLock) {
            if (!this.mStarted) {
                i = -1;
            } else {
                try {
                    if (hashMap != null) {
                        try {
                            try {
                                if (!hashMap.isEmpty()) {
                                    String str3 = (String) hashMap.get(Engine.KEY_PARAM_UTTERANCE_ID);
                                    if (str3 != null) {
                                        this.mCachedParams[11] = str3;
                                    }
                                    String str4 = (String) hashMap.get(Engine.KEY_PARAM_ENGINE);
                                    if (str4 != null) {
                                        this.mCachedParams[13] = str4;
                                    }
                                }
                            } catch (RemoteException e) {
                                Log.e("TextToSpeech.java - synthesizeToFile", "RemoteException");
                                e.printStackTrace();
                                this.mStarted = false;
                                initTts();
                                i = -1;
                            }
                        } catch (IllegalStateException e2) {
                            Log.e("TextToSpeech.java - synthesizeToFile", "IllegalStateException");
                            e2.printStackTrace();
                            this.mStarted = false;
                            initTts();
                            i = -1;
                        } catch (NullPointerException e3) {
                            Log.e("TextToSpeech.java - synthesizeToFile", "NullPointerException");
                            e3.printStackTrace();
                            this.mStarted = false;
                            initTts();
                            i = -1;
                        }
                    }
                } catch (Throwable th) {
                }
                if (this.mITts.synthesizeToFile(this.mPackageName, str, this.mCachedParams, str2)) {
                    i = 0;
                    resetCachedParams();
                }
                i = -1;
                resetCachedParams();
            }
        }
        return i;
    }

    private void resetCachedParams() {
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - basic platform TextToSpeech does not support resetCachedParams");
        } else {
            this.mCachedParams[9] = String.valueOf(3);
            this.mCachedParams[11] = "";
        }
    }

    public int setOnUtteranceCompletedListener(final e eVar) {
        int i;
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for setOnUtteranceCompletedListener");
            return super.setOnUtteranceCompletedListener(new TextToSpeech.OnUtteranceCompletedListener() { // from class: com.google.tts.TextToSpeechBeta.3
                @Override // android.speech.tts.TextToSpeech.OnUtteranceCompletedListener
                public void onUtteranceCompleted(String str) {
                    eVar.onUtteranceCompleted(str);
                }
            });
        }
        synchronized (this.mStartLock) {
            i = -1;
            if (this.mStarted) {
                this.mITtscallback = new ITtsCallbackBeta.Stub() { // from class: com.google.tts.TextToSpeechBeta.4
                    @Override // com.google.tts.ITtsCallbackBeta
                    public void utteranceCompleted(String str) {
                        if (eVar != null) {
                            eVar.onUtteranceCompleted(str);
                        }
                    }
                };
                try {
                    try {
                        try {
                            try {
                                i = this.mITts.registerCallback(this.mPackageName, this.mITtscallback);
                            } catch (RemoteException e) {
                                Log.e("TextToSpeech.java - registerCallback", "RemoteException");
                                e.printStackTrace();
                                this.mStarted = false;
                                initTts();
                            }
                        } catch (IllegalStateException e2) {
                            Log.e("TextToSpeech.java - registerCallback", "IllegalStateException");
                            e2.printStackTrace();
                            this.mStarted = false;
                            initTts();
                        }
                    } catch (NullPointerException e3) {
                        Log.e("TextToSpeech.java - registerCallback", "NullPointerException");
                        e3.printStackTrace();
                        this.mStarted = false;
                        initTts();
                    }
                } catch (Throwable th) {
                }
            }
        }
        return i;
    }

    /* JADX WARN: Multi-variable type inference failed */
    /* JADX WARN: Type inference failed for: r1v14 */
    /* JADX WARN: Type inference failed for: r1v17 */
    /* JADX WARN: Type inference failed for: r1v18 */
    /* JADX WARN: Type inference failed for: r1v19 */
    /* JADX WARN: Type inference failed for: r1v20 */
    public int setEngineByPackageNameExtended(String str) {
        int i;
        NullPointerException e;
        IllegalStateException e2;
        RemoteException e3;
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for setEngineByPackageName");
            return usePlatform_setEngineByPackageName(this, str);
        }
        synchronized (this.mStartLock) {
            i = -1;
            int i2 = this.mStarted;
            if (i2 != 0) {
                try {
                    i2 = this.mITts.setEngineByPackageName(str);
                } catch (RemoteException e4) {
                    i2 = -1;
                    e3 = e4;
                } catch (IllegalStateException e5) {
                    i2 = -1;
                    e2 = e5;
                } catch (NullPointerException e6) {
                    i2 = -1;
                    e = e6;
                } catch (Throwable th) {
                    i2 = -1;
                }
                if (i2 == 0) {
                    try {
                        this.mCachedParams[13] = str;
                        i = i2;
                        i2 = i2;
                    } catch (RemoteException e7) {
                        e3 = e7;
                        Log.e("TextToSpeech.java - setEngineByPackageName", "RemoteException");
                        e3.printStackTrace();
                        this.mStarted = false;
                        initTts();
                        i = i2;
                        i2 = i2;
                        return i;
                    } catch (IllegalStateException e8) {
                        e2 = e8;
                        Log.e("TextToSpeech.java - setEngineByPackageName", "IllegalStateException");
                        e2.printStackTrace();
                        this.mStarted = false;
                        initTts();
                        i = i2;
                        i2 = i2;
                        return i;
                    } catch (NullPointerException e9) {
                        e = e9;
                        Log.e("TextToSpeech.java - setEngineByPackageName", "NullPointerException");
                        e.printStackTrace();
                        this.mStarted = false;
                        initTts();
                        i = i2;
                        i2 = i2;
                        return i;
                    }
                }
                i = i2;
            }
        }
        return i;
    }

    public String getDefaultEngineExtended() {
        String str;
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for getDefaultEngine");
            return usePlatform_getDefaultEngine(this);
        }
        synchronized (this.mStartLock) {
            str = "";
            if (this.mStarted) {
                try {
                    try {
                        try {
                            str = this.mITts.getDefaultEngine();
                        } catch (NullPointerException e) {
                            Log.e("TextToSpeech.java - setEngineByPackageName", "NullPointerException");
                            e.printStackTrace();
                            this.mStarted = false;
                            initTts();
                        }
                    } catch (IllegalStateException e2) {
                        Log.e("TextToSpeech.java - setEngineByPackageName", "IllegalStateException");
                        e2.printStackTrace();
                        this.mStarted = false;
                        initTts();
                    }
                } catch (RemoteException e3) {
                    Log.e("TextToSpeech.java - setEngineByPackageName", "RemoteException");
                    e3.printStackTrace();
                    this.mStarted = false;
                    initTts();
                }
            }
        }
        return str;
    }

    public boolean areDefaultsEnforcedExtended() {
        boolean z = false;
        if (!ttsBetaInstalled) {
            Log.d("TextToSpeechBeta", "TextToSpeechBeta not installed - defaulting to basic platform TextToSpeech for setOnUtteranceCompletedListener");
            return usePlatform_areDefaultsEnforced(this);
        }
        synchronized (this.mStartLock) {
            if (this.mStarted) {
                try {
                    try {
                        try {
                            z = this.mITts.areDefaultsEnforced();
                        } catch (RemoteException e) {
                            Log.e("TextToSpeech.java - areDefaultsEnforced", "RemoteException");
                            e.printStackTrace();
                            this.mStarted = false;
                            initTts();
                        }
                    } catch (IllegalStateException e2) {
                        Log.e("TextToSpeech.java - areDefaultsEnforced", "IllegalStateException");
                        e2.printStackTrace();
                        this.mStarted = false;
                        initTts();
                    }
                } catch (NullPointerException e3) {
                    Log.e("TextToSpeech.java - areDefaultsEnforced", "NullPointerException");
                    e3.printStackTrace();
                    this.mStarted = false;
                    initTts();
                }
            }
        }
        return z;
    }

    public static boolean isInstalled(Context context) {
        PackageManager packageManager = context.getPackageManager();
        Intent intent = new Intent("com.google.intent.action.START_TTS_SERVICE_BETA");
        intent.addCategory("com.google.intent.category.TTS_BETA");
        return packageManager.resolveService(intent, 0) != null;
    }
}
