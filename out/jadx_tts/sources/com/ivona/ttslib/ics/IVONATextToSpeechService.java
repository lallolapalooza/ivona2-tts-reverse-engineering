package com.ivona.ttslib.ics;

import android.content.Intent;
import android.content.IntentFilter;
import android.media.AudioManager;
import android.net.LocalSocket;
import android.net.LocalSocketAddress;
import android.os.Environment;
import android.os.Handler;
import android.os.Message;
import android.speech.tts.SynthesisCallback;
import android.speech.tts.SynthesisRequest;
import android.speech.tts.TextToSpeechService;
import android.util.Log;
import com.ivona.ttslib.AppIvonaAndroidLib;
import com.ivona.ttslib.HeadsetPlugReceiver;
import com.ivona.ttslib.config.ConfigXMLDataSet;
import com.ivona.ttslib.engine.TTSServiceActivation;
import com.ivona.ttslib.engine.d;
import com.ivona.ttslib.packages.IvonaPackagesInfo;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/* loaded from: classes.dex */
public class IVONATextToSpeechService extends TextToSpeechService {
    private static final int MSG_INIT = 1;
    private static final String TAG = "IVONATextToSpeechService";
    private static CountDownLatch engineCreatedSignal;
    private static volatile String[] currentLanguage = null;
    private static volatile String[] initLanguage = null;
    private static NativeIVONAEngineICS ivonaEngineInstance = null;
    private static final NativeIVONAEngineICS ivonaEngine = new NativeIVONAEngineICS();
    private static final Handler handlerInit = new a();
    private final HeadsetPlugReceiver recvHeadset = new HeadsetPlugReceiver();
    private ConfigXMLDataSet cfgXML = null;
    private boolean createInProgress = false;
    private boolean speaking = false;

    public static void setContrast(boolean z) {
        if (ivonaEngineInstance != null) {
            ivonaEngineInstance.setContrast(z ? 1 : 0);
        }
    }

    class WaitForActivationInit implements Runnable {
        private WaitForActivationInit() {
        }

        /* synthetic */ WaitForActivationInit(IVONATextToSpeechService iVONATextToSpeechService, a aVar) {
            this();
        }

        @Override // java.lang.Runnable
        public void run() {
            while (true) {
                if (com.ivona.tts.commonlib.a.c) {
                    Log.d(IVONATextToSpeechService.TAG, "waiting for socket");
                }
                LocalSocket localSocket = new LocalSocket();
                try {
                    localSocket.connect(new LocalSocketAddress(d.b(IVONATextToSpeechService.this.getApplicationContext())));
                    OutputStream outputStream = localSocket.getOutputStream();
                    InputStream inputStream = localSocket.getInputStream();
                    outputStream.write("exists".getBytes());
                    inputStream.read();
                    inputStream.read();
                    localSocket.close();
                    if (com.ivona.tts.commonlib.a.c) {
                        Log.d(IVONATextToSpeechService.TAG, "socket is ok");
                    }
                    IVONATextToSpeechService.handlerInit.sendMessage(Message.obtain(IVONATextToSpeechService.handlerInit, 1));
                    return;
                } catch (IOException e) {
                    try {
                        IVONATextToSpeechService.engineCreatedSignal.await(100L, TimeUnit.MILLISECONDS);
                    } catch (InterruptedException e2) {
                    }
                }
            }
        }
    }

    private void bindToActivationSrv() {
        startService(new Intent(this, (Class<?>) TTSServiceActivation.class));
        if (engineCreatedSignal.getCount() > 0) {
            new Thread(new WaitForActivationInit(this, null)).start();
        }
    }

    @Override // android.speech.tts.TextToSpeechService, android.app.Service
    public void onCreate() {
        if (com.ivona.tts.commonlib.a.c) {
            Log.d(TAG, "onCreate");
        }
        engineCreatedSignal = new CountDownLatch(1);
        ivonaEngineInstance = ivonaEngine;
        NativeIVONAEngine.setEnvRuntime(new File(getApplicationInfo().dataDir).getParent() + "/", Environment.getExternalStorageDirectory().getAbsolutePath() + "/");
        registerReceiver(this.recvHeadset, new IntentFilter("android.intent.action.HEADSET_PLUG"));
        if (IvonaPackagesInfo.b()) {
            try {
                this.cfgXML = new ConfigXMLDataSet();
            } catch (Exception e) {
                if (com.ivona.tts.commonlib.a.c) {
                    e.printStackTrace();
                }
            }
        }
        bindToActivationSrv();
        this.createInProgress = true;
        super.onCreate();
        this.createInProgress = false;
    }

    @Override // android.speech.tts.TextToSpeechService, android.app.Service
    public void onDestroy() {
        super.onDestroy();
        if (com.ivona.tts.commonlib.a.c) {
            Log.d(TAG, "onDestroy");
        }
        unregisterReceiver(this.recvHeadset);
        ivonaEngineInstance = null;
        while (isSpeaking(false, false)) {
            try {
                Thread.sleep(100L);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
        currentLanguage = null;
        try {
            engineCreatedSignal.await();
            ivonaEngine.destroy();
        } catch (InterruptedException e2) {
            e2.printStackTrace();
        }
        if (com.ivona.tts.commonlib.a.c) {
            Log.d(TAG, "onDestroy - done");
        }
    }

    @Override // android.speech.tts.TextToSpeechService
    protected Set onGetFeaturesForLanguage(String str, String str2, String str3) {
        if (com.ivona.tts.commonlib.a.c) {
            Log.d(TAG, "onGetFeaturesForLanguage " + str + "/" + str2 + "/" + str3);
        }
        HashSet hashSet = new HashSet();
        hashSet.add("embeddedTts");
        return hashSet;
    }

    @Override // android.speech.tts.TextToSpeechService
    protected String[] onGetLanguage() {
        String[] onGetLanguage = ivonaEngine.onGetLanguage();
        if (com.ivona.tts.commonlib.a.c) {
            if (onGetLanguage == null) {
                Log.d(TAG, "onGetLanguage: null");
            } else {
                String str = "";
                for (String str2 : onGetLanguage) {
                    str = str + str2 + " ";
                }
                Log.d(TAG, "onGetLanguage: " + str);
            }
        }
        return onGetLanguage;
    }

    @Override // android.speech.tts.TextToSpeechService
    protected int onIsLanguageAvailable(String str, String str2, String str3) {
        if (com.ivona.tts.commonlib.a.c) {
            Log.d(TAG, "onIsLanguageAvailable: " + str + "/" + str2 + "/" + str3);
        }
        int a = ((AppIvonaAndroidLib) getApplication()).a().a(str, str2, str3, this.cfgXML);
        if (com.ivona.tts.commonlib.a.c) {
            Log.d(TAG, "onIsLanguageAvailable res:" + a);
        }
        return a;
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* JADX WARN: Code restructure failed: missing block: B:16:0x0009, code lost:
    
        if (com.ivona.ttslib.ics.IVONATextToSpeechService.currentLanguage != null) goto L7;
     */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static synchronized int loadLanguage(java.lang.String r4, java.lang.String r5, java.lang.String r6, boolean r7) {
        /*
            r1 = 0
            r0 = -2
            java.lang.Class<com.ivona.ttslib.ics.IVONATextToSpeechService> r2 = com.ivona.ttslib.ics.IVONATextToSpeechService.class
            monitor-enter(r2)
            if (r7 == 0) goto Ld
            java.lang.String[] r3 = com.ivona.ttslib.ics.IVONATextToSpeechService.currentLanguage     // Catch: java.lang.Throwable -> L25
            if (r3 == 0) goto Ld
        Lb:
            monitor-exit(r2)
            return r0
        Ld:
            com.ivona.ttslib.ics.NativeIVONAEngineICS r3 = com.ivona.ttslib.ics.IVONATextToSpeechService.ivonaEngine     // Catch: java.lang.Throwable -> L25
            int r3 = r3.onLoadLanguage(r4, r5, r6)     // Catch: java.lang.Throwable -> L25
            if (r3 < 0) goto Lb
            r0 = 3
            java.lang.String[] r0 = new java.lang.String[r0]     // Catch: java.lang.Throwable -> L25
            r3 = 0
            r0[r3] = r4     // Catch: java.lang.Throwable -> L25
            r3 = 1
            r0[r3] = r5     // Catch: java.lang.Throwable -> L25
            r3 = 2
            r0[r3] = r6     // Catch: java.lang.Throwable -> L25
            com.ivona.ttslib.ics.IVONATextToSpeechService.currentLanguage = r0     // Catch: java.lang.Throwable -> L25
            r0 = r1
            goto Lb
        L25:
            r0 = move-exception
            monitor-exit(r2)
            throw r0
        */
        throw new UnsupportedOperationException("Method not decompiled: com.ivona.ttslib.ics.IVONATextToSpeechService.loadLanguage(java.lang.String, java.lang.String, java.lang.String, boolean):int");
    }

    /* JADX WARN: Code restructure failed: missing block: B:21:0x008c, code lost:
    
        if (java.util.Arrays.equals(com.ivona.ttslib.ics.IVONATextToSpeechService.currentLanguage, new java.lang.String[]{r9, r10, r11}) != false) goto L24;
     */
    /* JADX WARN: Code restructure failed: missing block: B:23:0x0092, code lost:
    
        if (r0 >= 0) goto L24;
     */
    /* JADX WARN: Removed duplicated region for block: B:15:0x0061  */
    @Override // android.speech.tts.TextToSpeechService
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    protected int onLoadLanguage(java.lang.String r9, java.lang.String r10, java.lang.String r11) {
        /*
            r8 = this;
            r7 = 3
            r6 = 2
            r5 = 1
            r4 = 0
            boolean r0 = com.ivona.tts.commonlib.a.c
            if (r0 == 0) goto L34
            java.lang.String r0 = "IVONATextToSpeechService"
            java.lang.StringBuilder r1 = new java.lang.StringBuilder
            r1.<init>()
            java.lang.String r2 = "onLoadLanguage: "
            java.lang.StringBuilder r1 = r1.append(r2)
            java.lang.StringBuilder r1 = r1.append(r9)
            java.lang.String r2 = "/"
            java.lang.StringBuilder r1 = r1.append(r2)
            java.lang.StringBuilder r1 = r1.append(r10)
            java.lang.String r2 = "/"
            java.lang.StringBuilder r1 = r1.append(r2)
            java.lang.StringBuilder r1 = r1.append(r11)
            java.lang.String r1 = r1.toString()
            android.util.Log.d(r0, r1)
        L34:
            android.app.Application r0 = r8.getApplication()
            com.ivona.ttslib.AppIvonaAndroidLib r0 = (com.ivona.ttslib.AppIvonaAndroidLib) r0
            com.ivona.ttslib.packages.IvonaPackagesInfo r0 = r0.a()
            com.ivona.ttslib.config.ConfigXMLDataSet r1 = r8.cfgXML
            int r2 = r0.a(r9, r10, r11, r1)
            if (r2 < 0) goto L94
            if (r2 >= r6) goto L98
            java.lang.String r0 = ""
            if (r2 >= r5) goto L96
            java.lang.String r1 = ""
        L4e:
            boolean r3 = r8.createInProgress
            if (r3 == 0) goto L7a
            java.lang.String[] r3 = new java.lang.String[r7]
            r3[r4] = r9
            r3[r5] = r1
            r3[r6] = r0
            com.ivona.ttslib.ics.IVONATextToSpeechService.initLanguage = r3
            r0 = r2
        L5d:
            boolean r1 = com.ivona.tts.commonlib.a.c
            if (r1 == 0) goto L79
            java.lang.String r1 = "IVONATextToSpeechService"
            java.lang.StringBuilder r2 = new java.lang.StringBuilder
            r2.<init>()
            java.lang.String r3 = "onLoadLanguage res: "
            java.lang.StringBuilder r2 = r2.append(r3)
            java.lang.StringBuilder r2 = r2.append(r0)
            java.lang.String r2 = r2.toString()
            android.util.Log.d(r1, r2)
        L79:
            return r0
        L7a:
            java.lang.String[] r0 = com.ivona.ttslib.ics.IVONATextToSpeechService.currentLanguage
            if (r0 == 0) goto L8e
            java.lang.String[] r0 = com.ivona.ttslib.ics.IVONATextToSpeechService.currentLanguage
            java.lang.String[] r1 = new java.lang.String[r7]
            r1[r4] = r9
            r1[r5] = r10
            r1[r6] = r11
            boolean r0 = java.util.Arrays.equals(r0, r1)
            if (r0 != 0) goto L94
        L8e:
            int r0 = loadLanguage(r9, r10, r11, r4)
            if (r0 < 0) goto L5d
        L94:
            r0 = r2
            goto L5d
        L96:
            r1 = r10
            goto L4e
        L98:
            r0 = r11
            r1 = r10
            goto L4e
        */
        throw new UnsupportedOperationException("Method not decompiled: com.ivona.ttslib.ics.IVONATextToSpeechService.onLoadLanguage(java.lang.String, java.lang.String, java.lang.String):int");
    }

    @Override // android.speech.tts.TextToSpeechService
    protected void onStop() {
        if (com.ivona.tts.commonlib.a.c) {
            Log.d(TAG, "onStop");
        }
        try {
            engineCreatedSignal.await();
            ivonaEngine.stop();
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
    }

    private synchronized boolean isSpeaking(boolean z, boolean z2) {
        if (z) {
            this.speaking = z2;
        }
        return this.speaking;
    }

    @Override // android.speech.tts.TextToSpeechService
    protected synchronized void onSynthesizeText(SynthesisRequest synthesisRequest, SynthesisCallback synthesisCallback) {
        if (com.ivona.tts.commonlib.a.c) {
            Log.d(TAG, "onSynthesizeText (" + synthesisRequest.getLanguage() + "/" + synthesisRequest.getCountry() + "/" + synthesisRequest.getVariant() + ")");
        }
        try {
            engineCreatedSignal.await();
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
        if ((currentLanguage == null || !Arrays.equals(currentLanguage, new String[]{synthesisRequest.getLanguage(), synthesisRequest.getCountry(), synthesisRequest.getVariant()})) && loadLanguage(synthesisRequest.getLanguage(), synthesisRequest.getCountry(), synthesisRequest.getVariant(), false) < 0) {
            Log.e(TAG, "Failed to load language. Voice not updated?");
            synthesisCallback.error();
        } else {
            AudioManager audioManager = (AudioManager) getSystemService("audio");
            if (audioManager.isBluetoothA2dpOn() || audioManager.isWiredHeadsetOn()) {
                if (com.ivona.tts.commonlib.a.c) {
                    Log.d(TAG, "speak with headphones");
                }
                ivonaEngine.setContrast(0);
            } else {
                if (com.ivona.tts.commonlib.a.c) {
                    Log.d(TAG, "speak without headphones");
                }
                ivonaEngine.setContrast(1);
            }
            isSpeaking(true, true);
            ivonaEngine.speak(synthesisRequest, synthesisCallback);
            isSpeaking(true, false);
            if (com.ivona.tts.commonlib.a.c) {
                Log.d(TAG, "onSynthesizeText - done");
            }
        }
    }
}
