# IVONA 2 Android TTS — engine APK reverse-engineering spec (Java/Android layer)

**Target:** `IVONA Text-to-Speech HQ 1.6.55.617.apk`, package `com.ivona.tts`, `versionCode=617`, `versionName="1.6.55.617"`, `android:sharedUserId="com.ivona.ttsuser"`, `minSdkVersion=4`, `targetSdkVersion=14`, `maxSdkVersion=22`.

**Evidence sources used (all paths relative to the analysis workspace):**
- Decompiled Java: `out/jadx_tts/sources/**` (jadx 1.x output, 87 `.java` files).
- Decoded resources: `out/jadx_tts_res/resources/` (`AndroidManifest.xml`, `res/`, `classes.dex`).
- A second, *bad-code-tolerant* decompilation of `out/tts/classes.dex` was produced at `/tmp/ivona_bad/` with `~/tools/jadx/bin/jadx -d /tmp/ivona_bad --show-bad-code --no-res out/tts/classes.dex` to recover method bodies that the original output left as `Method dump skipped` (`com.ivona.ttslib.engine.f.doInBackground`, `IvonaGui.a(boolean)`). No file under `out/` was modified.
- Native cross-checks (JNI symbol names / string literals only, native behaviour itself is another agent's scope): `nm -D` and `strings -a` on `out/tts/lib/armeabi/libttsivona.so`.
- Voice APKs used only where the engine calls into them: `out/jadx_amy/`, `out/jadx_kendra/`.

---

## 1. Component map (decoded `AndroidManifest.xml`, 132 lines)

`<application android:label="@string/app_name" android:icon="@drawable/icon" android:name="com.ivona.tts.VoiceApp">`

Permissions requested (manifest lines 11–18):
`android.permission.WRITE_EXTERNAL_STORAGE`, `INTERNET`, `ACCESS_NETWORK_STATE`, `ACCESS_WIFI_STATE`, `READ_PHONE_STATE`, `RECEIVE_BOOT_COMPLETED`, `GET_ACCOUNTS`, `com.android.vending.BILLING`.

| # | Component (exact `android:name`) | Manifest attributes | Intent filter | Role |
|---|---|---|---|---|
| 1 | service `com.ivona.ttslib.ics.IVONATextToSpeechService` | `label=@string/app_name` | action `android.intent.action.TTS_SERVICE` + category `android.intent.category.DEFAULT`; meta-data `android.speech.tts` → `@xml/tts_engine` | The actual Android TTS engine service (see §3). |
| 2 | activity `com.ivona.ttslib.DownloadVoiceData` | `configChanges="orientation\|keyboardHidden"` | `android.speech.tts.engine.INSTALL_TTS_DATA` + DEFAULT | “Install voice data” screen (`PreferenceActivity`), see §7. |
| 3 | activity `com.ivona.ttslib.CheckVoiceData` | `theme=@android:style/Theme.Translucent.NoTitleBar` | `android.speech.tts.engine.CHECK_TTS_DATA` + DEFAULT | Returns available/unavailable voice list to the framework (see §5.4). |
| 4 | activity `com.ivona.ttslib.GetSampleText` | `theme=Theme.Translucent.NoTitleBar` | `android.speech.tts.engine.GET_SAMPLE_TEXT` + DEFAULT | Per-locale sample string for the settings UI (§5.5). |
| 5 | activity `com.ivona.tts.Ivona` | `theme=Theme.Translucent.NoTitleBar`, `enabled="true"` | action `android.intent.action.START_TTS_ENGINE` with categories `android.intent.category.tts_engine.IVONA`, `tts_lang.eng`, `tts_lang.eng.USA`, `tts_lang.eng.GBR`, `tts_lang.pol`, `tts_lang.deu`, `tts_lang.fra`, `tts_lang.spa`, `tts_lang.spa.ESP`, `tts_lang.spa.USA`, `tts_lang.ron` | Legacy (pre-KitKat) language/engine advertisement entry point; `onCreate()` only calls `finish()`. Exposes `public static final String a = Environment.getExternalStorageDirectory() + "/ivona"`. |
| 6 | activity `com.ivona.ttslib.IvonaGui` | `theme=Theme.NoTitleBar`, `screenOrientation=portrait` | none (no filter ⇒ not implicitly exported) | Interactive demo/GUI. Started *explicitly* by same-uid voice apps: `out/jadx_amy/sources/com/ivona/tts/voicelib/IvonaVoice.java:224` → `setClassName("com.ivona.tts", "com.ivona.ttslib.IvonaGui")`. |
| 7 | activity `com.ivona.tts.WelcomeActivity` | `noHistory="true"` | `android.intent.action.MAIN` + `android.intent.category.LAUNCHER` | First-run/browser hand-off (§8.2). |
| 8 | activity `com.ivona.tts.EngineSettings` | — | `android.speech.tts.engine.CONFIGURE_ENGINE` + DEFAULT | Preference screen; also declared as `android:settingsActivity` in `res/xml/tts_engine.xml`. |
| 9 | service `com.ivona.ttslib.engine.TTSServiceActivation` | no filter | — | Local activation/IPC service (§4.5). |
| 10 | receiver `com.ivona.ttslib.ActivityReceiver` | — | `android.intent.action.USER_PRESENT`, `android.intent.action.BOOT_COMPLETED` | `startService(new Intent(ctx, TTSServiceActivation.class))`. |
| 11 | receiver `com.ivona.ttslib.PackageMonitorReceiver` | — | `PACKAGE_ADDED`, `PACKAGE_CHANGED`, `PACKAGE_REMOVED`, `PACKAGE_RESTARTED`, `PACKAGE_FULLY_REMOVED`, `PACKAGE_REPLACED`, `<data android:scheme="package"/>` | Starts `TTSServiceActivation` and starts `CustomSettingsService` with extra `upkgmon=true` → voice-package cache rebuild (§5.3). |
| 12 | service `com.ivona.ttslib.CustomSettingsService` | no filter | — | `IntentService` handling extras `setEmail` / `upkgmon` (§7.3). |
| 13 | activity `com.ivona.ttslib.CustomSettings` | `theme=@android:style/Theme.NoDisplay` | `com.ivona.tts.intent.ACTION_CUSTOM_SETTINGS` + DEFAULT | Reads/answers `isEmailSet` from prefs `ivona_custom` (§7.3). |

`res/xml/tts_engine.xml` (whole file):
```xml
<tts-engine xmlns:android="http://schemas.android.com/apk/res/android" android:settingsActivity="com.ivona.tts.EngineSettings"/>
```

**Application class chain:** `com.ivona.tts.VoiceApp` → `com.ivona.ttslib.AppIvonaAndroidLib` → `com.ivona.tts.commonlib.AppLib` (extends `android.app.Application`, empty). `AppIvonaAndroidLib` holds `private final IvonaPackagesInfo a = new IvonaPackagesInfo(this)` exposed by `public IvonaPackagesInfo a()`. Every component obtains the shared package-info object via `((AppIvonaAndroidLib) getApplication()).a()` (or `getApplicationContext()`).

**Logging:** `com.ivona.tts.commonlib.a` = `IvonaLogLevel` with `public static int a = 0;` and derived `b = a>0`, `c = a>1`, `d = a>2`. Every `if (com.ivona.tts.commonlib.a.c) Log.d(...)` in the code base is gated on this static field (it is never written after `<clinit>`, so all logging is dead unless the field is patched).

---

## 2. Process / identity model

- `sharedUserId="com.ivona.ttsuser"` is the backbone of discovery: the engine and every voice APK run under one uid, so `PackageManager.getPackagesForUid(Process.myUid())` returns **the engine plus all installed voice packages** (§5.1).
- Native runtime dirs are pushed into the JNI layer once per service creation:
  `NativeIVONAEngine.setEnvRuntime(new File(getApplicationInfo().dataDir).getParent() + "/", Environment.getExternalStorageDirectory().getAbsolutePath() + "/")`
  i.e. `("/data/data/", "/sdcard/")` on a typical device (matches the literals `/data/data/` and `/sdcard/` inside `libttsivona.so`).
- Sibling apps explicitly reach into this package across class-loader boundaries (same uid ⇒ allowed): `com.ivona.ttslib.CheckVoiceData` (`IvonaVoice.java:200`), `com.ivona.ttslib.IvonaGui` (`:224`), `com.ivona.ttslib.engine.TTSServiceActivation` (`voicelib/ActivityReceiver.java:43`), `com.ivona.ttslib.CustomSettingsService` (`:49`).

---

## 3. `IVONATextToSpeechService` — lifecycle, threading, synthesis

File: `out/jadx_tts/sources/com/ivona/ttslib/ics/IVONATextToSpeechService.java` (382 lines), `extends android.speech.tts.TextToSpeechService`.

### 3.1 Static state

```java
private static final int MSG_INIT = 1;
private static final String TAG = "IVONATextToSpeechService";
private static CountDownLatch engineCreatedSignal;
private static volatile String[] currentLanguage = null;   // {iso3lang, iso3country, variant} actually loaded
private static volatile String[] initLanguage = null;      // deferred load captured while super.onCreate() runs
private static NativeIVONAEngineICS ivonaEngineInstance = null;
private static final NativeIVONAEngineICS ivonaEngine = new NativeIVONAEngineICS();  // one native engine per process
private static final Handler handlerInit = new a();        // com.ivona.ttslib.ics.a, created on the main looper
private final HeadsetPlugReceiver recvHeadset = new HeadsetPlugReceiver();
private ConfigXMLDataSet cfgXML = null;
private boolean createInProgress = false;
private boolean speaking = false;
public static void setContrast(boolean z) { if (ivonaEngineInstance != null) ivonaEngineInstance.setContrast(z ? 1 : 0); }
```

Note the static `ivonaEngine` is constructed at class-load ⇒ `System.loadLibrary("ttsivona")` (in `NativeIVONAEngine.<clinit>`) happens as soon as the service class is loaded.

### 3.2 `onCreate()` (order matters)

```java
engineCreatedSignal = new CountDownLatch(1);
ivonaEngineInstance = ivonaEngine;
NativeIVONAEngine.setEnvRuntime(parentOf(dataDir) + "/", externalStorageRoot + "/");
registerReceiver(this.recvHeadset, new IntentFilter("android.intent.action.HEADSET_PLUG"));
if (IvonaPackagesInfo.b()) {                 // native isoemn()==1 → OEM build
    try { this.cfgXML = new ConfigXMLDataSet(); } catch (Exception e) { ... }
}
bindToActivationSrv();                       // BEFORE super.onCreate()
this.createInProgress = true;
super.onCreate();
this.createInProgress = false;
```

`bindToActivationSrv()`:
```java
startService(new Intent(this, TTSServiceActivation.class));
if (engineCreatedSignal.getCount() > 0) new Thread(new WaitForActivationInit(this, null)).start();
```

`WaitForActivationInit.run()` — **infinite retry loop**, on a plain `java.lang.Thread`:
```java
LocalSocket s = new LocalSocket();
s.connect(new LocalSocketAddress(com.ivona.ttslib.engine.d.b(getApplicationContext())));
s.getOutputStream().write("exists".getBytes());
s.getInputStream().read(); s.getInputStream().read();   // consumes 0xBB then 0x38 (§9.3)
s.close();
handlerInit.sendMessage(Message.obtain(handlerInit, MSG_INIT));   // → create()
// on IOException: engineCreatedSignal.await(100, MILLISECONDS); loop again
```
Everything that touches the engine (`onGetLanguage`, `onLoadLanguage`, `onSynthesizeText`, `onStop`, `onDestroy`) blocks on `engineCreatedSignal.await()` until this handshake succeeds. If the activation socket never appears, synthesis blocks forever (no timeout, no error).

`handlerInit` = `com.ivona.ttslib.ics.a extends Handler` (main looper), `handleMessage` case `MSG_INIT`:
```java
ivonaEngine.create();                                  // native create()
if (initLanguage != null) { loadLanguage(initLanguage[0], initLanguage[1], initLanguage[2], /*force*/true); initLanguage = null; }
engineCreatedSignal.countDown();
```

`createInProgress` exists so that an `onLoadLanguage(...)` issued while `super.onCreate()` runs is *recorded* (`initLanguage = {lang, country, variant}`) instead of calling native `onLoadLanguage` before `create()`; the recorded triple is applied right after `create()`.

### 3.3 `onDestroy()`

```java
super.onDestroy();
unregisterReceiver(this.recvHeadset);
ivonaEngineInstance = null;
while (isSpeaking(false, false)) Thread.sleep(100);   // spin until onSynthesizeText finished
currentLanguage = null;
engineCreatedSignal.await();
ivonaEngine.destroy();
```
(`isSpeaking(boolean set, boolean val)` is a synchronized get/set of `this.speaking`.)

### 3.4 Language callbacks

- `onGetFeaturesForLanguage(lang, country, variant)` → always `HashSet{"embeddedTts"}`.
- `onGetLanguage()` → `ivonaEngine.onGetLanguage()` (native, returns `String[]`).
- `onIsLanguageAvailable(lang, country, variant)` → `((AppIvonaAndroidLib) getApplication()).a().a(lang, country, variant, this.cfgXML)` = `IvonaPackagesInfo.a(...)`; returns `-2 / 0 / 1 / 2` (§5.5). The 4th parameter `cfgXML` is accepted but **never used** inside `IvonaPackagesInfo.a`.
- `loadLanguage(String,String,String,boolean force)` — `public static synchronized` (assembly recovered verbatim in the jadx output):
  - `force==true && currentLanguage != null` → return `-2` (LANG_NOT_SUPPORTED), no reload.
  - else `int r = ivonaEngine.onLoadLanguage(l, c, v); if (r < 0) return -2; currentLanguage = {l,c,v}; return 0;`
- `onLoadLanguage(l, c, v)` (protected, decompiled from bytecode) does:
  1. `int res = ((AppIvonaAndroidLib)getApplication()).a().a(l, c, v, cfgXML);` (match level)
  2. `if (res < 0) return res;` (i.e. `-2`)
  3. computes the *effective* triple that will be stored in `initLanguage` from the match level `res` (bytecode registers `r9`=lang, `r10`=country, `r11`=variant):
     - `res == 0` → `{l, "", ""}` (language only; country and variant cleared),
     - `res == 1` → `{l, c, ""}` (country kept, variant cleared),
     - `res == 2` → `{l, c, v}` (both kept);
     (reconstructed from the jadx bytecode labels: `L96: r1 = r10` when `res>=1`, `L98: r0 = r11; r1 = r10` when `res>=2`, and the pre-seeded `r0 = ""` / `r1 = ""` otherwise),
  4. if `createInProgress` → store `initLanguage = {l, normalizedCountry, normalizedVariant}` and return `res`;
  5. else if `currentLanguage != null && Arrays.equals(currentLanguage, {l,c,v})` → return `res` (already loaded);
  6. else `int r = loadLanguage(l, c, v, false);` with the **original** triple → return `r` if `r < 0`, otherwise `res`.
- **`onGetSampleText` is NOT overridden** (verified by listing all `@Override` methods). Sample text is served by the `GetSampleText` activity (§5.5), the pre-KitKat path.

### 3.5 `onStop()`
```java
engineCreatedSignal.await();   // InterruptedException → printStackTrace
ivonaEngine.stop();
```

### 3.6 `onSynthesizeText(SynthesisRequest, SynthesisCallback)` — `protected synchronized`

```java
engineCreatedSignal.await();
if ((currentLanguage == null || !Arrays.equals(currentLanguage,
        new String[]{req.getLanguage(), req.getCountry(), req.getVariant()}))
        && loadLanguage(req.getLanguage(), req.getCountry(), req.getVariant(), false) < 0) {
    Log.e(TAG, "Failed to load language. Voice not updated?");
    synthesisCallback.error();
} else {
    AudioManager am = (AudioManager) getSystemService("audio");
    if (am.isBluetoothA2dpOn() || am.isWiredHeadsetOn()) ivonaEngine.setContrast(0);  // headphones
    else                                                    ivonaEngine.setContrast(1);  // speaker
    isSpeaking(true, true);
    ivonaEngine.speak(req, synthesisCallback);          // ← all PCM work, same thread
    isSpeaking(true, false);
}
```

**Threading model:** `android.speech.tts.TextToSpeechService` runs `onSynthesizeText` on its own worker `HandlerThread` (framework side); IVONA adds only:
- main-thread handler `handlerInit` (engine `create()` + deferred `loadLanguage`),
- one ad-hoc `Thread` for the activation socket probe,
- `AsyncTask` (`THREAD_POOL_EXECUTOR` when `SDK_INT > 12`) for the `LocalServerSocket` listener inside `TTSServiceActivation`,
- `com.ivona.ttslib.e` (`IvonaBackendThread`, a `Thread`) for the HTTP trial call,
- `IntentService` worker thread for `CustomSettingsService`.
No executor/pool in the synthesis path: one utterance at a time, synchronous, `speak()` returns only after `callback.done()`.

### 3.7 PCM production — `com.ivona.ttslib.ics.NativeIVONAEngineICS.speak(...)`

File: `out/jadx_tts/sources/com/ivona/ttslib/ics/NativeIVONAEngineICS.java` (120 lines).

```java
public void speak(SynthesisRequest req, SynthesisCallback cb) {
    this.callback = cb;
    cb.start(getSampleRate(), /*audioFormat*/ 2 /*ENCODING_PCM_16BIT*/, /*channels*/ 1);
    int max = cb.getMaxBufferSize();
    if (this.audioBufferSize < max) { this.audioBuffer = new byte[max]; this.audioBufferSize = max; }
    setProperty("rate",  String.valueOf(req.getSpeechRate()));
    setProperty("pitch", String.valueOf(req.getPitch()));
    int marks = Integer.parseInt(req.getParams().getString("com.ivona.tts.oem.GENERATE_MARKS")); // default 0, exception→0
    int contrast = Integer.parseInt(req.getParams().getString("com.ivona.tts.oem.SET_CONTRAST")); // default 1, exception→1
    Log.d(TAG, "setContrast: " + contrast);                    // value is logged, never applied here
    if (marks > 0) {
        try {
            this.audioAvailableWithMarks = cb.getClass().getMethod("audioAvailable",
                    byte[].class, int.class, int.class, List.class);
            if (this.marks == null) this.marks = new ArrayList();
            synthesizeText(req.getText(), this.audioBuffer, this.marks, marks);
        } catch (NoSuchMethodException e) {
            synthesizeText(req.getText(), this.audioBuffer);   // fallback: no marks
        }
    } else {
        synthesizeText(req.getText(), this.audioBuffer);
    }
    cb.done();
    this.callback = null;
}
```

- **Sample rate** comes from `NativeIVONAEngine.getSampleRate()` (native). No Java-side rate constant exists; the value is decided by the native/voice data (`libttsivona.so` contains `sample_rate` / `tts_voice_sample_rate` literals — see `scripts/engine_strings.txt`). Treat the actual Hz value as native-owned.
- **Buffer:** exactly `SynthesisCallback.getMaxBufferSize()` bytes (framework-typical 8192), allocated lazily, grown but never shrunk (`audioBufferSize` tracks capacity). The same `byte[]` is handed to native as the PCM sink for the whole utterance.
- **JNI → Java audio pump** — `public int audioAvailableClbk(int length, int status)` (called from native; the name appears as a `GetMethodID` string in `libttsivona.so`):
  ```java
  if (this.callback == null) return -1;
  if (status == TTS_SYNTH_DONE /* 0 */) return 1;      // "done" signal, no payload
  if (length > 0) {
      if (marks != null && audioAvailableWithMarks != null)
          audioAvailableWithMarks.invoke(callback, audioBuffer, 0, length, marks);  // List variant
      else
          callback.audioAvailable(audioBuffer, 0, length);                          // plain 3-arg
  }
  return 0;
  ```
  So: **native fills `audioBuffer` with 16-bit LE mono PCM and calls back with the number of valid bytes; Java immediately forwards that window to Android's `SynthesisCallback`.** `status==0` terminates. Return value is native's continuation signal (`-1` = no callback/abandon, `1` = done, `0` = ok).
- **`synthesizeText` overloads (private native, exact JNI symbols exported by `libttsivona.so`):**
  - `private native int synthesizeText(String text, byte[] pcmBuffer)` → `Java_com_ivona_ttslib_ics_NativeIVONAEngineICS_synthesizeText__Ljava_lang_String_2_3B`
  - `private native int synthesizeText(String text, byte[] pcmBuffer, List marks, int generateMarks)` → `..._synthesizeText__Ljava_lang_String_2_3BLjava_util_List_2I`
  - Meaning: `List marks` is an *out* parameter — Java allocates an empty `ArrayList`, native appends mark entries produced during synthesis (the native strings `TYPE_PHONEME`, `TYPE_WORD`, `TYPE_SENTENCE`, `TYPE_SSML`, `TYPE_VISEME` indicate mark kinds); `int generateMarks` is the flag copied from the `com.ivona.tts.oem.GENERATE_MARKS` bundle param (>0 ⇒ produce marks). Java never inspects the elements; it just forwards the `List` to the reflective `audioAvailable(byte[],int,int,List)` callback (available on newer `SynthesisCallback`s; otherwise it falls back to the 3-arg form and marks are dropped). Exact element type = native's concern. `[INFERENCE: element type]`
- `private native int setProperty(String, String)` → `Java_com_ivona_ttslib_ics_NativeIVONAEngineICS_setProperty`. Only ever called with `("rate", String.valueOf(speechRate))` and `("pitch", String.valueOf(pitch))`. Native accepts `rate`, `volume`, `pitch` (strings present in `.so`), plus `dur_stretch`, `pitch_stretch`.
- `setContrast(int)` (protected native) is driven from two places: `IVONATextToSpeechService.setContrast(boolean)` ← `HeadsetPlugReceiver` (`state==0` ⇒ unplugged ⇒ `setContrast(1)`; `state==1` ⇒ plugged ⇒ `setContrast(0)`) and the per-utterance headset check in `onSynthesizeText` (headphones ⇒ `0`, speaker ⇒ `1`).
- CPU benchmark (`com.ivona.ttslib.engine.a`, `CPUBenchmark`) is started in the `NativeIVONAEngineICS` constructor and bracketed around `synthesizeText` (`cpuBenchmark.b()` / `cpuBenchmark.a()`), but only when `com.ivona.tts.commonlib.a.d` (log level > 2) is true; it samples `/proc/stat` and `/proc/self/stat` every second and only logs.

### 3.8 Full JNI surface of the engine layer

`com.ivona.ttslib.ics.NativeIVONAEngine` (static init: `System.loadLibrary("ttsivona")`, plus a `java.library.path` dump split on `";"`):

| Java declaration | Exported symbol |
|---|---|
| `public static native void setEnvRuntime(String dataRoot, String sdRoot)` | `Java_com_ivona_ttslib_ics_NativeIVONAEngine_setEnvRuntime` |
| `public native void create()` | `..._create` |
| `public native void destroy()` | `..._destroy` |
| `public native int getSampleRate()` | `..._getSampleRate` |
| `public native String[] getVersion()` | `..._getVersion` |
| `public native String[] onGetLanguage()` | `..._onGetLanguage` |
| `public native int onLoadLanguage(String,String,String)` | `..._onLoadLanguage` |
| `protected native int setContrast(int)` | `..._setContrast` |
| `public native void stop()` | `..._stop` |
| `NativeIVONAEngineICS.setProperty(String,String)` | `Java_com_ivona_ttslib_ics_NativeIVONAEngineICS_setProperty` |
| `NativeIVONAEngineICS.synthesizeText(...)` ×2 | `Java_com_ivona_ttslib_ics_NativeIVONAEngineICS_synthesizeText__Ljava_lang_String_2_3B` / `..._3BLjava_util_List_2I` |
| `ConfigXMLDataSet.getSettingsCfg()` / `getPackagesCfg()` | `Java_com_ivona_ttslib_config_ConfigXMLDataSet_getSettingsCfg` / `_getPackagesCfg` |
| `IvonaPackagesInfo.getVoicesApiVersion(String[])` / `isoemn()` | `Java_com_ivona_ttslib_packages_IvonaPackagesInfo_getVoicesApiVersion` / `_isoemn` |

Native `dlopen` targets (strings in `.so`, relevant to reimplementation): `/lib/libttsivonavoice.so`, `/lib/libtiver.so`, `/lib/`, plus path fragments `ivona/`, `Android/obb/`, `com.ivona.tts/files/`, `com.ivona.tts`, `.voicebeta.`, `%s_%s`, `%s.%s`, `ivona_pkgs.csv`, `/etc/ivona/ivona_config.xml`.

---

## 4. Activation / IPC service (`TTSServiceActivation`)

### 4.1 Service
`out/jadx_tts/sources/com/ivona/ttslib/engine/TTSServiceActivation.java`:
- `onCreate()` → `Log.i("TTSServiceActivation","start")`; `this.a = d.a()` (singleton `TTSEngineConnector`); `new com.ivona.ttslib.e(this).start()` (**this is where the HTTP trial/telemetry thread is launched**, §8.1).
- `onStart(intent, i)` → `this.a.a(this)` → starts the socket listener task (§4.3); throws `RuntimeException("Connector not created!")` if `a == null`.
- `onBind()` returns `new com.ivona.ttslib.engine.j(this)` — a `Binder` whose only method `TTSServiceActivation a()` hands out the service instance (used by `IvonaGui`'s `ServiceConnection m`; see §10 note — that connection is never bound in this build).
- `onDestroy()` → `this.a.b()` → tells the listener to stop.

### 4.2 Socket name — `com.ivona.ttslib.engine.d.b(Context)`
```java
return com.ivona.tts.commonlib.b.e()   // SDK_INT >= 14
    ? context.getPackageName() + "." + context.getApplicationInfo().uid + ".log"   // "com.ivona.tts.<uid>.log"
    : context.getPackageName() + ".log";                                          // "com.ivona.tts.log"
```

### 4.3 Listener task — `com.ivona.ttslib.engine.f.doInBackground(String... args)` (recovered with `--show-bad-code`)
Loop-guard flag: static `d.a` (initially `true`; set to `false` by `d.b()`).

```java
this.e = new LocalServerSocket(args[0]);          // AF_LOCAL server, name above
b();                                              // signals "running" (lock+condition)
while (d.a) {
    LocalSocket s = this.e.accept();
    if (!d.a) break;
    OutputStream out = s.getOutputStream();
    out.write(187);                                // 0xBB, sent immediately on connect
    // read request: loop read() into 512-byte chunks, append while read()==512
    byte[] req = baos.toByteArray();
    if (req.length == 6 && new String(req).equals("exists")) {
        out.write(56);                             // 0x38 → health-probe reply
        s.close();
    } else {
        c msg = new i(new h(req).a().array()).a();  // XOR-decrypt, then parse (§9.4)
        boolean handled = a(msg, out);              // body is EMPTY in this build: if (msg.a()==2) {} → returns false
        Log.d(..., "elisten uid:" + s.getPeerCredentials().getUid());   // peer uid logged only
        out.write(732948);                          // 0x0B2F14 ack
        if (!handled) publishProgress(msg);
    }
}
```
`onProgressUpdate(c... arr)`: notifies `Observable` observers (`IvonaGui` registers as `Observer` *if* it ever binds) and shows a `Toast` for `msg.a()==1`:
- `msg.b()==1` → `Toast(getString(aa.n))` = `"engine_reload_required"` (`It is required to restart IVONA TTS HQ engine...`),
- `msg.b()==2` → `Toast(getString(aa.l))` = `"engine_activation_error"` (`There is a problem with IVONA voice activation.`).

`d.b()` (stop): sets `d.a=false`, connects to the socket name and writes `"close"`, then closes.

### 4.4 Who talks to it
- **Engine itself:** `"exists"` probe (§3.2) and `"close"` (stop).
- **Encrypted messages:** no code in the engine APK or in the two voice APKs (`jadx_amy`, `jadx_kendra` — grep for `LocalSocket`/`TTSMessageCipher` returns nothing) ever *sends* an encrypted message. The peer is some external agent not present in these packages. `[INFERENCE]`
- `TTSServiceActivation` is started from 5 places: `IVONATextToSpeechService.bindToActivationSrv()`, `ActivityReceiver` (BOOT/USER_PRESENT), `PackageMonitorReceiver`, `IvonaGui.onCreate()`, and the voice apps' `ActivityReceiver`.

---

## 5. Voice/package discovery

### 5.1 Primary enumeration — `com.ivona.ttslib.packages.IvonaPackagesInfo`
File: `out/jadx_tts/sources/com/ivona/ttslib/packages/IvonaPackagesInfo.java` (306 lines).

```java
public static final String a;      // = Environment.getExternalStorageDirectory() + "/ivona"   (SD root for voice data)
private final Context b;
private Map c;                     // packageName -> packages.a (IvonaPackage)
private final ReentrantLock d = new ReentrantLock();

private static native String[] getVoicesApiVersion(String[] packageNames);
private static native int isoemn();
static { System.loadLibrary("ttsivona"); a = Environment.getExternalStorageDirectory() + "/ivona"; }
```

**Public API (complete):**

| Method | Behaviour |
|---|---|
| `IvonaPackagesInfo(Context)` | ctor, stores context only. |
| `public Map a()` | Lazily builds the package map: `c = new HashMap(packages.c.a())` (53 hard-coded defaults, §5.2) then overlays the cached CSV `ivona_pkgs.csv` from the app's private files (`context.openFileInput("ivona_pkgs.csv")`). Each line is `split(";")`, requires `length >= 6`: `new a(split[0]/*pkg*/, split[4]/*name*/, Integer.parseInt(split[2])/*apiVer*/, split[5]/*sdk*/, Integer.parseInt(split[1])/*versionCode*/, packages.b.a(Integer.parseInt(split[3]))/*fstate*/)`. `FileNotFoundException`/`IOException` are swallowed (logged `Failed to read packages infromation file.`). Returns the map. |
| `public static boolean b()` | `return isoemn() == 1;` → **OEM mode flag** used to switch CheckVoiceData/DownloadVoiceData/onCreate behaviour. |
| `public boolean c()` | **Rebuild cache** (see §5.3). Guarded by `ReentrantLock`. |
| `public int a(String lang, String ctry, String variant, ConfigXMLDataSet cfg)` | `getVoiceByLocale`: returns `-2` if map not yet loaded; iterates `c.values()`, compares `Locale.getISO3Language()`/`getISO3Country()`/`getVariant()` against the request, keeping the best score: `0` = language match, `1` = +country, `2` = +variant; otherwise `-2`. The `cfg` parameter is unused. |
| `public Map d()` | Groups *usable* voices by `Locale(iso3lang, iso3country)` (`packages.a.f()`); only `fstate == FULL_INSTALLED || fstate == FILES_WITHOUT_APK` are included; returns `Map<Locale, List<packages.a>>`. |

**Package-name grammar** (`packages.a`, `compiled from: IvonaPackage.java`):
```java
static Locale a(String pkg) { String[] s = pkg.split("\\."); if (s.length < 7) throw new InvalidParameterException("Failed to parse package name"); return new Locale(s[4], s[5], s[6]); }
static String b(String pkg) { String[] s = pkg.split("\\."); if (s.length < 6) throw ...; return s[4] + "-" + s[5]; }   // ISO3 "eng-usa"
```
i.e. `com.ivona.tts.voicebeta.<iso3lang>.<iso3country>.<voice>` (7 dot-separated parts).
Accessors: `b()` versionCode, `c()` packageName, `d()` display name, `e()` full `Locale` (with variant), `f()` `Locale(iso3lang,iso3country)`, `g()` fstate, `h()` `iso3lang + "-" + iso3country`.

**Install-state enum** `packages.b` (`compiled from: IvonaPackage.java`):
```java
UNKNOWN(-1), FILES_WITHOUT_APK(2), APK_INSTALLED(1), FULL_INSTALLED(0);   // ordinal mapping via b.a(int)
```
The numeric value comes from native `getVoicesApiVersion`.

### 5.2 Static known-voice table — `com.ivona.ttslib.packages.c`
53 hard-coded entries `pkg → display name` (e.g. `"com.ivona.tts.voicebeta.eng.usa.kendra" → "IVONA Kendra"`, `"com.ivona.tts.voicebeta.eng.gbr.amy" → "IVONA Amy"`, ... `"com.ivona.tts.voicebeta.tur.tur.filiz" → "IVONA Filiz"`); the map is `Collections.unmodifiableMap`. It is the fallback so `CheckVoiceData`/`EngineSettings` work before any native report exists.

### 5.3 `c()` — cache rebuild (the only place `getVoicesApiVersion` is used)

```java
long ts = System.currentTimeMillis();
PackageManager pm = b.getPackageManager();
String[] pkgs = pm.getPackagesForUid(Process.myUid());          // engine + all voice APKs (sharedUserId)
// fast path: if every pkg is already in this.c with the same versionCode and counts match → return true (no I/O)
d.lock();
FileOutputStream fos = b.openFileOutput("ivona_pkgs.csv", 1);   // MODE_PRIVATE
NativeIVONAEngine.setEnvRuntime(parentOf(dataDir) + "/", externalStorage + "/");
String[] rep = getVoicesApiVersion(pkgs);                       // native, per package
out.write((Long.toString(ts) + "\n").getBytes());               // line 1: rebuild timestamp (ignored by reader: <6 fields)
for (int i = 0; i < pkgs.length; i++) {
    if (TextUtils.isEmpty(rep[i])) continue;                    // no voice in that package
    String[] f = rep[i].split(";");                             // f[0]=apiVer f[1]=fstate f[2]=name f[3]=sdk/stamp  (f[4] = data-location code, ignored by Java)
    PackageInfo pi = pm.getPackageInfo(pkgs[i], 0);
    c.put(pkgs[i], new a(pkgs[i], f[2], Integer.parseInt(f[0]), f[3], pi.versionCode, packages.b.a(Integer.parseInt(f[1]))));
    out.write((pkgs[i] + ";" + pi.versionCode + ";" + rep[i] + "\n").getBytes());
}
```
**CSV format (exact):**
```
<epochMillis>
<pkg>;<versionCode>;<apiVer>;<fstate>;<displayName>;<sdk>;<dataLocation>
...
```
(7 comma-free fields per data line; the reader only requires `length >= 6` and consumes indices 0–5, so the trailing `dataLocation` column written from `rep[i]` is ignored.)

**Exact per-element format produced by native `getVoicesApiVersion`** — verified in the Ghidra decompile `out/ghidra_dump/decompiled.c` (`Java_com_ivona_ttslib_packages_IvonaPackagesInfo_getVoicesApiVersion`, ELF `0x136fc`, lines ~10198–10290):
```c
snprintf(buf,0x20,"%d;%d;", struct[1], iVar10);   // apiVer ; fstate
append(out, buf);
append(out, namePtr->field_c);                     // display name (from a per-package lookup)
append(out, ";");                                  // DAT_0007cfa5
append(out, struct[2]);                            // build stamp, e.g. "20130201_150739"
snprintf(buf,0x20,";%d", local_6c);                // data-location code
append(out, buf);
```
⇒ `apiVer;fstate;name;stamp;dataLocation` (5 `;`-separated fields; Java uses the first four). Per package the native code:
1. builds a native-lib path and `dlopen`s it with `RTLD_LAZY` (`FUN_0004dfb0(&local_54, "/lib/libtiver.so")` after seeding the prefix from the `setEnvRuntime` globals `DAT_00084308`/`DAT_0008430c`);
2. `dlsym`s **`"v"`** and **`"h"`** (`DAT_0007cf5c`, `DAT_0007cf9c`) from that voice's `libtiver.so`;
3. gates on the returned struct: `0x13 < struct[0] && 0x2f < struct[3] && struct[1] < 3` (i.e. `struct[0] > 19`, `struct[3] > 47`, `struct[1] < 3`) — if any test fails, **no element is written** ⇒ Java's `TextUtils.isEmpty(rep[i])` path (package carries no voice);
4. probes data with `h(pkg, base1)` then, if that fails, `h(pkg, base2)`, the two bases being `<sdcard>/ivona/` and `<sdcard>/Android/obb/` (literals `ivona/` and `Android/obb/` in the `.so`; the base pointer comes from `setEnvRuntime`); `local_6c` (`dataLocation`) ends up `1` = found under `/ivona/`, `2` = found under `/Android/obb/`, `0` = neither (Ghidra-level reading, native agent's scope for full semantics);
5. `struct[1]` is the *apiVer* field (always `< 3`, so Java's `IvonaPackage.b()` apiVer is 0–2), the last `h()` result becomes the *fstate* fed to `packages.b.a(int)` (`0=FULL_INSTALLED, 1=APK_INSTALLED, 2=FILES_WITHOUT_APK, else null`), `struct[2]` is the build stamp surfaced as `IvonaPackage.c()` (logged as `SDK:`).

**Who triggers a rebuild:** `CheckVoiceData.onCreate()` (non-OEM branch, unconditionally `a.c()`), and `CustomSettingsService` when started with extra `upkgmon=true` (which `PackageMonitorReceiver` does on every package event, and the voice apps' `ActivityReceiver` also does).

### 5.4 `CheckVoiceData` (action `CHECK_TTS_DATA`)
`out/jadx_tts/sources/com/ivona/ttslib/CheckVoiceData.java`:
```java
a();                                   // writes private file ".android_version" = String.valueOf(Build.VERSION.SDK_INT)
ArrayList<String> available = new ArrayList<>(), unavailable = new ArrayList<>();
if (IvonaPackagesInfo.b()) {           // OEM mode
    for (String pkg : new ConfigXMLDataSet().a())          // packages cfg strings
        available.add(com.ivona.ttslib.packages.a.b(pkg)); // "…eng.usa.amy" → "eng-usa"
} else {
    IvonaPackagesInfo i = ((AppIvonaAndroidLib) getApplication()).a();
    i.c();                                          // force rebuild
    for (packages.a p : i.a().values())
        if (p.g() == FULL_INSTALLED) available.add(p.h());  // "eng-USA"
        else                        unavailable.add(p.h());
}
Intent res = new Intent();
res.putExtra("dataRoot", IvonaPackagesInfo.a);          // TextToSpeechBeta.Engine.EXTRA_VOICE_DATA_ROOT_DIRECTORY = "dataRoot"
res.putStringArrayListExtra("availableVoices", available);
res.putStringArrayListExtra("unavailableVoices", unavailable);
setResult(1, intent);                                   // 1 = CHECK_VOICE_DATA_PASS
finish();
```
Also writes `.android_version` (the framework/other engines use this file to detect a wiped dalvik-cache/SDK change).

### 5.5 `GetSampleText` (action `GET_SAMPLE_TEXT`)
Static table of 15 entries `d(iso3lang, iso3country, stringRes)`:
`eng/GBR→aa.j, eng/USA→aa.k, eng/AUS→aa.i, spa/ESP→aa.B, spa/USA→aa.C, pol/POL→aa.x, deu/DEU→aa.g, fra/FRA→aa.p, fra/CAN→aa.o, ron/ROU→aa.A, cym/GBR→aa.e, ita/ITA→aa.t, isl/ISL→aa.s, prt/BRA→aa.y, dan/DNK→aa.f`.
Resources (from `res/values/strings.xml` + `public.xml`; `aa` is the `R.string` table, id base `0x7f060000 = 2131099648`):
`eng_usa_sample = "I am American English IVONA voice"`, `eng_gbr_sample = "I am British English IVONA voice"`, `eng_aus_sample = "I am Australian English IVONA voice"`, `pol_pol_sample = "Jestem polskim głosem syntezatora mowy IVONA"`, `spa_esp_sample = spa_usa_sample = "Soy una voz en español de IVONA"`, `deu_deu_sample = "Ich bin die neue Deutsche Stimme von Ivona"`, `fra_fra_sample = "Je sui une voix française d'IVONA."`, `fra_can_sample = "Je sui une voix canadienne d'IVONA."`, `ita_ita_sample = "Io sono una voce italiana di IVONA."`, `ron_rou_sample = "Eu sunt o vocea românească de la Ivona"`, `cym_gbr_sample = "Rwy'n llais IVONA TTS Cymraeg."`, `prt_bra_sample = "Eu sou uma voz brasileira do sintetizador IVONA."`, `isl_isl_sample = "Ég er íslensk Ivona rödd."`, `dan_dnk_sample = "Jeg er en dansk IVONA-stemme."`.

Flow: read extras `language`/`country` (`TextToSpeechBeta.Engine.KEY_PARAM_LANGUAGE`/`KEY_PARAM_COUNTRY`), linear scan, `setResult(loopIndex, intent.putExtra("sampleText", str))` + `finish()` **without break**, and — as decompiled — after the `if (extras != null)` block the method unconditionally executes `str=""; i=-2; setResult(-2, new Intent().putExtra("sampleText","")); finish();`. Net observable result on the match path is therefore whatever the framework last received (jadx-reported structure; a `break`/`return` may have been lost). `[UNCERTAIN — treat the fallback result code -2 with empty sampleText as the literal reading of the bytecode]`.

### 5.6 What a voice pack must expose (engine-side requirements)

1. **Same `sharedUserId` `com.ivona.ttsuser`** and a package name `com.ivona.tts.voicebeta.<iso3lang>.<iso3country>.<voice>` (7 dot parts) — this is how locale and display name are derived, and how the engine finds it (`getPackagesForUid`).
2. **A native API version report** produced by `IvonaPackagesInfo.getVoicesApiVersion(String[])`: the engine `dlopen`s the pack's `<pkg>/lib/libtiver.so`, `dlsym`s `v()` and `h()`, validates the `v()` struct (`struct[0] > 0x13`, `struct[3] > 0x2f`, `struct[1] < 3`), and emits `apiVer;fstate;name;stamp;dataLocation` (§5.3). A pack that ships no `libtiver.so` (or fails the gate) yields an empty element and is treated as "no voice". The `.voicebeta.` infix in the package name is what gives the engine the locale (§5.1 grammar).
3. **Data files under one of two probed roots** — `<sdcard>/ivona/…` or `<sdcard>/Android/obb/…`: the engine's native `getVoicesApiVersion` calls `h(pkg, base)` against exactly those two bases (literals `ivona/` and `Android/obb/` in `libttsivona.so`, base pointer supplied by `setEnvRuntime`) and reports the winner in the `dataLocation` field (`1` = `/ivona/`, `2` = `/Android/obb/`, `0` = neither — Ghidra-level reading; full `h()` semantics are the native agent's scope). Java-side the root constant is `IvonaPackagesInfo.a` / `Ivona.a` = `<sdcard>/ivona`, which is what `CHECK_TTS_DATA` advertises as `dataRoot`, and no Java code touches OBB. The voice APK confirms the legacy layout: `jadx_amy/.../voicelib/VoiceFiles.java` deletes `<sdcard>/ivona/<vox>` / `<sdcard>/ivona/<lang.dat>` then calls native `checkFiles(pkgPrefix, "<sdcard>/")`.
4. **Launchable UI components** the engine starts explicitly: activity `<pkg>/.IvonaVoice` (preferred) or `<pkg>/.IvonaKendra` (fallback) with `MAIN`+`LAUNCHER` (see `ttslib/b.java`, `IvonaGui`), and `<pkg>.CheckVoiceInstalled` probed by `com.ivona.tts.a.a(Context)` (WelcomeActivity).
5. **Optional**: voice data APK must share the uid, else it is invisible to discovery.

### 5.7 How a voice is enabled/selected
Only `com.ivona.tts.EngineSettings` writes a selection (§7.1): one file per locale under the app's `files/` dir whose name is `"." + iso3lang.toLowerCase() + "_" + iso3country.toLowerCase()` and whose content is the chosen voice package name. Native cross-confirmation: `libttsivona.so` strings `com.ivona.tts/files/`, `%s.%s`, `%s_%s` (and it also reads `ivona_pkgs.csv`). Selection affects native voice loading; the Java layer never reads those files except to pre-select the `ListPreference` summary.

---

## 6. Config parsing — `com.ivona.ttslib.config.ConfigXMLDataSet`

File: `out/jadx_tts/sources/com/ivona/ttslib/config/ConfigXMLDataSet.java` (37 lines, whole body):
```java
private static String[] a;      // settingsCfg
private static String[] b;      // packagesCfg
private static native String[] getPackagesCfg();
private static native String[] getSettingsCfg();
static {
    Log.d("ConfigXMLDataSet", "loading XML config");   // if log level > 1
    System.loadLibrary("ttsivona");
    a = getSettingsCfg();
    b = getPackagesCfg();
    Log.d(..., "XML config loaded - settingsCfg:" + (a==null?0:a.length) + " packageCfg:" + (b==null?0:b.length));
}
public final String[] a() { return b; }        // packagesCfg is the only value consumed by Java
```

**Where the XML comes from:** entirely inside `libttsivona.so`. There is no Java-side XML parsing, no `res/xml` config, and no file written by Java. The relevant native string table (strings offsets ~1174–1181) is:

```
package
/etc/ivona/ivona_config.xml
ivona_config
global
packages
voice_data
voice_lib
lex_dir
```

So the OEM/root config lives at **`/etc/ivona/ivona_config.xml`**, root element `ivona_config`, sections `global` and `packages`, per-package attributes/keys `voice_data`, `voice_lib`, `lex_dir`. On a normal (non-OEM) device that file does not exist — which is consistent with `isoemn()` gating (`IvonaPackagesInfo.b()`): when `isoemn()==1` the engine trusts the XML (`CheckVoiceData` builds its "available" list from `getPackagesCfg()`, `DownloadVoiceData` immediately `finish()`es, and `IVONATextToSpeechService.onCreate` constructs `ConfigXMLDataSet`). `[INFERENCE: isoemn() == "is OEM N" test = presence of /etc/ivona/ivona_config.xml]`

Additional native-side property names relevant to config (`strings`): `rate`, `volume`, `pitch`, `dur_stretch`, `pitch_stretch`, `sampleOffset`, `set:quality`, `set:responsiveness`, `set:volume:max`, `voice_data`, `voice_lib`, `android_version`.

**Java-consumed settings keys — complete list** (there is no other preference storage in the APK):

| Store | Key | Type / default | Writer | Reader | Effect |
|---|---|---|---|---|---|
| internal file `files/<key>` | `"." + iso3lang_lc + "_" + iso3country_lc` (e.g. `.eng_usa`, `.deu_deu`) | UTF-8 string = voice package name; default = **first entry** of the locale's list when the file is absent | `EngineSettings.a(String,String)` via `onPreferenceChange` | `EngineSettings.a(Context,String)`; native (per §5.7) | Preferred voice for that locale |
| internal file `.android_version` | — | `String.valueOf(Build.VERSION.SDK_INT)` | `CheckVoiceData.a()` | (framework/other engines) | Detect SDK/dalvik change |
| SharedPreferences `ivona_custom` (mode 0) | `emailSet` | boolean, **default `false`** | `CustomSettingsService` on extra `setEmail` | `CustomSettings` on extra `isEmailSet` (returns `emailSet`) | OEM “email entered” flag only |
| SharedPreferences `ivona_referrer` (mode 0) | `referrer` | string, default absent | never written inside this APK | `DownloadVoiceData` | appended to the store URL |

---

## 7. Settings UI

### 7.1 `com.ivona.tts.EngineSettings` (`PreferenceActivity`, implements `Preference.OnPreferenceChangeListener`)
`onCreate`: creates the preference screen programmatically (no XML), adds a `PreferenceCategory` titled `R.string.preferred_voice` (“Preferred voice”), then for each `Locale` key of `IvonaPackagesInfo.d()` adds one `ListPreference`:

```java
ListPreference lp = new ListPreference(this);
lp.setKey(a(locale));                       // "." + iso3lang.toLowerCase() + "_" + iso3country.toLowerCase()
lp.setTitle(locale.getDisplayName());
lp.setDialogTitle(R.string.preferred_voice_dialog_title);   // "Select preferred voice"
lp.setPersistent(false);                    // NOT stored in SharedPreferences — file written manually
lp.setOnPreferenceChangeListener(this);
lp.setEntries(displayNames);                // packages.a.d() e.g. "IVONA Kendra"
lp.setEntryValues(packageNames);            // packages.a.c() e.g. "com.ivona.tts.voicebeta.eng.usa.kendra"
```
Default selection: `b(locale,list)` → voice whose package name equals the content of `files/<key>`; if absent/unmatched → `list.get(0)`. Summary = `aVar.d()` (display name).

`onPreferenceChange(p, newValue)`:
```java
packages.a v = ((AppIvonaAndroidLib)getApplication()).a().a().get(newValue.toString());
if (v != null) { a(p.getKey(), v.c()); p.setSummary(v.d()); }   // writes files/<key> = packageName
return true;
```
`a(Context,String)`/`a(String,String)` are plain `openFileInput`/`openFileOutput(name, 1 /*MODE_PRIVATE*/)` helpers with `delete()` first (4096-byte read buffer).

Static helpers: `EngineSettings.a(Locale)` (key format) and `EngineSettings.a(Context,String)` (read).

No other preference keys exist (grep for `getSharedPreferences(` in the whole dex yields only `ivona_custom` and `ivona_referrer`; `ListPreference`/`CheckBoxPreference` are only created here).

### 7.2 `com.ivona.ttslib.IvonaGui` (demo screen, 541 lines)
Intent extras it consumes (via `hasExtra`/`getStringExtra`): `engine`, `file`, `language`, `pitch`, `rate`, `text`, `ttsextended` (collectively set `g=true` ⇒ “scripted/demo mode”), plus `VoicePackage` (initial voice pkg, preserved in `onSaveInstanceState` as `useDefltVPkg`) and `dont_return_to_gui` (forwarded to the voice app).

Key behaviours: `startService(TTSServiceActivation)`; resolves `VoicePackage` in the package map; if not `FULL_INSTALLED`, launches `<pkg>/.IvonaVoice` (or shows update dialog when versionCodes differ); otherwise builds a `TextToSpeech`:
```java
if (e())                              d = new TextToSpeechBeta(this, new q(this));
else if (SDK==14 || SDK>=15)          d = new TextToSpeech(this, new r(this), "com.ivona.tts");   // explicit engine pkg
else                                   d = new TextToSpeech(this, new s(this));
```
`e()` = demo intent with `ttsextended=true`, else `SDK_INT < 8`.
Dialog ids: `10` progress `"Checking voice data. Please wait..."`, `11` `"The voice data installation is required..."` (positive `download`, negative `Cancel`), `13` `"IVONA Text-to-Speech is not currently set as the default..."` (positive `go_to_tts_settings`), `14` `updateIvonaVoice`, `15` `engine_reload_required`, `16` `engine_not_enabled`, `17` `updateIvonaHQ`.
Engine-state probe `a(boolean)` returns `v{a=defaultEngine, b=status}`: `b==3` → language missing (`setLanguage` returned -1) → dialog 15; `b==1` or `a()==0` → dialog 16; default engine ≠ own package → dialog 13; else enable the Speak button. `a()` inspects `Settings.Secure.getString(cr,"tts_enabled_plugins")` (space-separated) on pre-ICS devices.
Rate slider mapping (`f()`/`o`): `p = progress/(max/2) ∈ [0,2]`; `p<1 → 0.5p+0.5` else `(p-1)*2+1` ⇒ **rate ∈ [0.5, 3.0]**, default 1.0 at centre. Pitch (`g()`/`p`): `(max/2) / (101 - min(progress,100))` ⇒ ≈0.495…50, ≈1.0 near centre.
Dead code: `private final ServiceConnection k = new m(this)` is never passed to `bindService()` (grep: no `bindService` anywhere except `TextToSpeechBeta`/`TTS`), so `Observer.update()` is never invoked in this build.

### 7.3 `CustomSettings` / `CustomSettingsService`
```java
// activity com.ivona.ttslib.CustomSettings (Theme.NoDisplay, action com.ivona.tts.intent.ACTION_CUSTOM_SETTINGS)
SharedPreferences sp = getSharedPreferences("ivona_custom", 0);
if (getIntent().hasExtra("isEmailSet")) {
    Intent r = new Intent(); r.putExtra("emailSet", sp.getBoolean("emailSet", false)); setResult(0, r);
}
finish();

// service com.ivona.ttslib.CustomSettingsService (IntentService "CustomSettingsService")
if (intent.hasExtra("setEmail")) { sp.edit().putBoolean("emailSet", intent.getExtras().getBoolean("setEmail")).commit(); }
else if (intent.hasExtra("upkgmon")) { ((AppIvonaAndroidLib) getApplicationContext()).a().c(); }  // rebuild voice cache
```

### 7.4 Receivers
- `ActivityReceiver` (`USER_PRESENT`, `BOOT_COMPLETED`) → `startService(TTSServiceActivation)`.
- `PackageMonitorReceiver` (all `PACKAGE_*` with `scheme=package`) → `startService(TTSServiceActivation)` **and** `startService(CustomSettingsService{upkgmon=true})`.
- `HeadsetPlugReceiver` (registered dynamically in `onCreate` for `android.intent.action.HEADSET_PLUG`) → `IVONATextToSpeechService.setContrast(state == 0)`.

---

## 8. Data download / license / telemetry

### 8.1 `IvonaBackendThread` (`com.ivona.ttslib.e`, started from `TTSServiceActivation.onCreate`)
```java
while (!ok) {
    String d  = commonlib.b.b(this);              // device fingerprint (§8.4)
    String u  = a();                              // hashes of google accounts
    ArrayList v = b();                            // sibling packages in the same uid (excluding self)
    String vStr = b(v);                           // "lang_country_voice;..." 
    boolean flag = a(v);                          // always true
    int vc = commonlib.b.a(ctx).versionCode;      // PackageInfo("com.ivona.tts").versionCode
    if (b(d, u, vStr, flag, vc) == null) sleep(300000L);   // retry every 5 min
    else ok = true;                               // any non-null body → stop
}
```
`b(...)` does the POST:
```java
HttpPost post = new HttpPost("http://gw.ivona.com/android/trial");
params: d=<device hash>, u=<account hashes>, b=<0|1 (always 1)>, v=<voices>, vc=<versionCode>, c=<proof>
post.setEntity(new UrlEncodedFormEntity(list));   // default encoding (application/x-www-form-urlencoded)
body = readAll(defaultHttpClient.execute(post).getEntity().getContent());
```
**Proof `c`** = `commonlib.b.a(SHA256concat)` where `SHA256concat = sha256_hex(SALT + x)` with hard-coded salt
`069f69d25c5923cb2f72b5aacd143a19490a115b0675f0d52043c3fd9efbd4a4`, and
```java
x = charsOf(d)[{2,13,23,24,34,46,51,62}]                     // 8 fixed positions of the 64-hex device hash
  + every 6th char of u (indices 0,6,12,…)
  + ("y3s" if flag else "n0")                                 // flag is hard-coded true → "y3s"
  + vc
  + every 3rd char of v (indices 0,3,6,…);
```
`u` = each `com.google` account name replaced by `commonlib.b.a(name)` (same salted SHA-256), joined with `";"`; only when `SDK_INT >= 5` (`GET_ACCOUNTS` permission is declared).
`v` = for each sibling package (uid-shared, excluding `com.ivona.tts`) with exactly 7 dot parts: `s[4]+"_"+s[5]+"_"+s[6]` joined with `";"`.
`d` = `sha256_hex(SALT + firstGoogleAccount + Settings.Secure.ANDROID_ID + Build.SERIAL(SDK≥9) + TelephonyManager.getDeviceId())` (all components `""` when unavailable). `[recovered from the jadx bytecode dump of commonlib.b.b]`
The response body is **never parsed** in Java — success is “got a body”.
No TLS: plain `http://`, default `DefaultHttpClient`.

### 8.2 `DownloadVoiceData` (action `INSTALL_TTS_DATA`, a `PreferenceActivity`)
```java
if (IvonaPackagesInfo.b()) { finish(); return; }            // OEM build: nothing to download
for (packages.a v : ((AppIvonaAndroidLib) getApplication()).a().a().values()) {
    if (v.g() == UNKNOWN) continue;
    // one PreferenceCategory per Locale.toString() (key), one Preference per voice (key=displayName, persistent=false)
    switch (state) { case APK_INSTALLED: summary = aa.w /*"Click to download voice data"*/;
                     case FULL_INSTALLED: summary = aa.c /*"Activated"*/; }
    pref.setOnPreferenceClickListener(new b(this, v));      // → launch the voice app
    any = false;
}
if (any /*i.e. no known voice at all*/) {
    String url = "http://mobile.ivona.com/?set_lang=" + getString(aa.z /*"res_lang" → "us"*/);
    SharedPreferences ref = getSharedPreferences("ivona_referrer", 0);
    if (ref.contains("referrer")) url += "&referrer=" + ref.getString("referrer", "");
    startActivity(new Intent(ACTION_VIEW, Uri.parse(url))); finish();
}
```
Click handler `ttslib/b.java`: `Intent(ACTION_MAIN).setComponent(<pkg>/.IvonaVoice)` + category `LAUNCHER`; if `queryIntentActivities` is empty it retries with `<pkg>/.IvonaKendra`; then `startActivity` + `finish()`.

`com.ivona.tts.WelcomeActivity` (launcher): builds
`"http://mobile.ivona.com/?ap=EMBED&v=1&set_lang=" + getString(R.string.res_lang)` and appends `&<campaignId>=1` for each of 10 hard-coded `(packageName, campaignId)` pairs whose `<pkg>.CheckVoiceInstalled` activity resolves:
`kendra→P113_1, pol.pol.maja→P107_1, eng.gbr.amy→P109_1, deu.marlene→P123_1, spa.esp.conchita→P119_1, spa.usa.penelope→122_1, fra.fra.celine→P125_1, ron.rou.carmen→P104_1, cym.gbr.gwyneth→P127_1, eng.gbr.gwyneth→P129_1`; then `ACTION_VIEW` + `finish()`.

### 8.3 Billing
- Manifest declares `com.android.vending.BILLING` **only**; there is **no billing code in `classes.dex`** (grep for `vending|billing|purchase|sku|inapp|Iab` finds only the `market://` intents below and `com.android.vending.INSTALL_REFERRER` inside the vendored analytics receiver). Purchase/download of paid voices happens in the voice APKs (they declare `com.android.vending.CHECK_LICENSE`).
- Market intents present: `market://details?id=<pkg>` and `market://search?q=pub:"IVONA Text-to-Speech"` (`IvonaGui` `marketLink` extra, `ttslib/i.java`), `market://search?q=pname:com.google.tts` (`TTSVersionAlert`).

### 8.4 Common helpers `com.ivona.tts.commonlib.b` (`VUtils`)
`a(Context,String)`/`a(Context)` (PackageInfo lookups; own package hard-coded `"com.ivona.tts"`), SDK predicates `b()<8`, `c()>=15`, `d()==14`, `e()>=14`, `f()==11..13`, `g()` = “HTC One X” check, `a(Context,Intent)` query helper, `b(Context,Intent)` start-if-resolvable, `a(String)` = salted SHA-256 (§8.1), `b(Context)` = device fingerprint (§8.1).

---

## 9. Network endpoints, crypto, proprietary protocols

### 9.1 All HTTP endpoints in the engine APK
| URL | Site |
|---|---|
| `http://gw.ivona.com/android/trial` | POST (trial/licence telemetry), §8.1 — `com.ivona.ttslib/e.java:107` |
| `http://mobile.ivona.com/?set_lang=<res_lang>[&referrer=…]` | `DownloadVoiceData.java:63` |
| `http://mobile.ivona.com/?ap=EMBED&v=1&set_lang=<res_lang>[&<camp>=1…]` | `WelcomeActivity.java:16` |
| `http://mobile.faq.ivona.com/pkb_mobile_i4m?l=<pl\|en_US>#home/l:<same>` | FAQ link in `IvonaGui.a(TextView)` |
| `http://eyes-free.googlecode.com/svn/trunk/thirdparty/espeak-data.zip` | vendored `com.google.tts.ConfigurationManager` (eSpeak data downloader, unrelated to IVONA synthesis) |

No `https://` anywhere in the IVONA code. No other sockets: only `LocalSocket`/`LocalServerSocket` (§4).

### 9.2 Java-layer crypto
- **Salted SHA-256** (`commonlib.b.a`): `MessageDigest("SHA-256").digest((SALT + input).getBytes())`, hex-encoded with `Formatter("%02x")`, salt = `069f69d25c5923cb2f72b5aacd143a19490a115b0675f0d52043c3fd9efbd4a4`.
- **No** `javax.crypto`/`SecretKey`/`Cipher`/`AES`/`Base64` usage in the APK (grep over all 87 files: only the class comment `TTSMessageCipher`).

### 9.3 Activation socket protocol (in-process AF_LOCAL, name §4.2)
| Direction | Bytes | Meaning |
|---|---|---|
| server → client (immediately on accept) | `0xBB` = 187 | “hello” |
| client → server | ASCII `"exists"` (6 bytes) | health probe (engine service startup) |
| server → client | `0x38` = 56 | probe OK (client reads exactly 2 bytes) |
| client → server | ASCII `"close"` | stop listener (`d.b()`) |
| server → client | `0x0B2F14` = 732948 | ack after every non-probe request |

### 9.4 Encrypted message format (`engine/h`, `engine/i`, `engine/g`)
Cipher (`TTSMessageCipher.h(byte[])`, 64-byte key literal in `h.e`):
```java
byte[] e = {-91, 1, 110, 111, 81, 78, 77, 118, 47, -121, -7, -15, 101, -105, -109, -71,
            51, 105, -10, -101, -120, 3, 14, 107, -52, -104, 119, -34, -119, 65, 25, 62,
            113, 35, 75, -1, 48, -78, -61, 56, -77, -128, -116, 12, -46, -56, -111, -9,
            -94, -24, 44, 6, 34, 20, 40, 28, -36, -126, -80, -76, 69, 104, -87, -42};
// decrypt: keep last 48 bytes as (XOR) key material, then XOR whole buffer with repeating key:
//   out[i] = buf[i] ^ key[i % key.length]   (engine/i.a(ByteBuffer, byte[]))
```
`h.a()`: `tmp = i.a(buffer, e); c = tmp[capacity-48 .. capacity); return i.a(tmp[0 .. capacity-48), c)` — i.e. the **last 48 bytes of the decrypted stream are the actual XOR key** used to decrypt the body.

Parser (`TTSMessageParser i`), `ByteOrder.nativeOrder()`:
```
offset 0 : int32 type       (a)
offset 4 : int32 status     (b)
offset 8 : if byte == 2 → NUL-terminated UTF-8 string from offset 9 (else no string)
offset 9..: payload ByteBuffer (remainder)
```
`TTSMessage g` maps status codes for `type==1 && status==1`:
- string starts with `"Voice library version mismatch"` → `b()==1` → Toast `engine_reload_required`
- string starts with `"Voice not allowed by the certificate"` → `b()==2` → Toast `engine_activation_error`

---

## 10. `com.google.tts` — vendored third-party binder API layer

Complete class list (verified against the dex `class_defs`, 115 classes total): `ITTS`, `ITTS$Stub`, `ITTS$Stub$Proxy`, `ITTSCallback(+Stub/Proxy)`, `ITtsBeta(+Stub/Proxy)`, `ITtsCallbackBeta(+Stub/Proxy)`, `TTS`, `TextToSpeechBeta(+Engine, +$2,$3,$4)`, `ConfigurationManager(+dataDownloader)`, `MakeBagel(+1,+2)`, `SoundResource`, `TTSEarcon`, `TTSEngine`, `TTSParams`, `TTSVersionAlert(+1,+2)`, `R`, `a`,`b`,`c`,`d`,`e`.

### 10.1 AIDL-style interfaces exposed
**`com.google.tts.ITtsBeta`** — descriptor `"com.google.tts.ITtsBeta"`, 20 transactions:
`setSpeechRate(1)`, `setPitch(2)`, `speak(3)`, `isSpeaking(4)`, `stop(5)`, `addSpeech(6)`, `addSpeechFile(7)`, `getLanguage(8)`, `isLanguageAvailable(9)`, `setLanguage(10)`, `synthesizeToFile(11)`, `playEarcon(12)`, `addEarcon(13)`, `addEarconFile(14)`, `registerCallback(15)`, `unregisterCallback(16)`, `playSilence(17)`, `setEngineByPackageName(18)`, `getDefaultEngine(19)`, `areDefaultsEnforced(20)`.
Most calls are keyed by a `String` package-name first argument (multi-client session id).
**`com.google.tts.ITtsCallbackBeta`** — descriptor `"com.google.tts.ITtsCallbackBeta"`, one transaction `utteranceCompleted(String)`.
**`com.google.tts.ITTS`** — descriptor `"com.google.tts.ITTS"`, 15 transactions: `setEngine(1)`, `setSpeechRate(2)`, `speak(3)`, `isSpeaking(4)`, `stop(5)`, `addSpeech(6)`, `addSpeechFile(7)`, `getVersion(8)`, `setLanguage(9)`, `synthesizeToFile(10)`, `playEarcon(11)`, `addEarcon(12)`, `addEarconFile(13)`, `registerCallback(14)`, `unregisterCallback(15)`.
**`com.google.tts.ITTSCallback`** — descriptor `"com.google.tts.ITTSCallback"`, one transaction `markReached(String)`.

### 10.2 Who binds, and to what
- **Nothing in this APK implements these interfaces as a service.** There is no `extends ITtsBeta.Stub` / `ITTS.Stub` service class in the dex, and the manifest declares no service with the corresponding actions. They are *client* stubs.
- `TextToSpeechBeta.initTts()` binds:
  ```java
  Intent i = new Intent("com.google.intent.action.START_TTS_SERVICE_BETA");
  i.addCategory("com.google.intent.category.TTS_BETA");
  mContext.bindService(i, mServiceConnection, Context.BIND_AUTO_CREATE);
  ```
  `TextToSpeechBeta.isInstalled(ctx)` = `pm.resolveService(action+category) != null` → i.e. an external `com.google.tts` “beta” app must be installed. On connect: `mITts = ITtsBeta.Stub.asInterface(binder)`, `setEngineByPackageNameExtended(getDefaultEngineExtended())`, `setLanguage(getLanguage())`, then `mInitListener.a(0, pm.getPackageInfo("com.google.tts",0).versionCode)`.
- `TTS.initTts()` binds:
  ```java
  Intent i = new Intent("android.intent.action.USE_TTS");
  i.addCategory("android.intent.category.TTS");
  ```
  (the eyes-free/eSpeak plugin protocol), then `itts.getVersion()`; requires `MIN_VER = 10`, else shows `TTSVersionAlert`; registers an `ITTSCallback.Stub` whose `markReached` → `onSpeechCompleted()`.

### 10.3 How it reaches `IVONATextToSpeechService`
`TextToSpeechBeta extends android.speech.tts.TextToSpeech`. Every method follows the same pattern:
```java
if (!ttsBetaInstalled) { log("…defaulting to basic platform TextToSpeech…"); return super.<method>(...); }
// else: mITts.<transaction>(mPackageName, ...) over the beta binder
```
So the actual forwarding path to `com.ivona.ttslib.ics.IVONATextToSpeechService` is the **platform fallback**: `super(...)` uses `android.speech.tts.TextToSpeech`, which binds action `android.intent.action.TTS_SERVICE` — exactly the engine's manifest filter — and then all calls (`speak`, `setLanguage`, `setSpeechRate`, `synthesizeToFile`, …) arrive at `IVONATextToSpeechService` through the framework binder (`dispatchOnSynthesizeText`/`onSynthesizeText`, `onLoadLanguage`, …). Reflection shims `usePlatform_setEngineByPackageName` / `usePlatform_getDefaultEngine` / `usePlatform_areDefaultsEnforced` cover API levels where those methods don't exist (fallback default `Engine.DEFAULT_SYNTH = "com.svox.pico"`).
Also used directly by IVONA code (constants + optional client):
- `TextToSpeechBeta.Engine.*`: `ACTION_CHECK_TTS_DATA`, `ACTION_INSTALL_TTS_DATA`, `CHECK_VOICE_DATA_PASS=1 / MISSING_DATA=-2 / FAIL=0 / BAD_DATA=-1 / MISSING_VOLUME=-3`, `EXTRA_VOICE_DATA_ROOT_DIRECTORY="dataRoot"`, `KEY_PARAM_{RATE="rate",PITCH="pitch",LANGUAGE="language",COUNTRY="country",VARIANT="variant",ENGINE="engine",STREAM="streamType",UTTERANCE_ID="utteranceId"}`, `DEFAULT_RATE=100`, `DEFAULT_PITCH=100`, `DEFAULT_STREAM=3`.
- `LANG_AVAILABLE=0`, `LANG_COUNTRY_AVAILABLE=1`, `LANG_COUNTRY_VAR_AVAILABLE=2`, `LANG_MISSING_DATA=-1`, `LANG_NOT_SUPPORTED=-2` (these are the return codes of §3.4).
- `NativeIVONAEngineICS` reads the OEM bundle params `com.ivona.tts.oem.GENERATE_MARKS` / `com.ivona.tts.oem.SET_CONTRAST` (names are IVONA's own, not Google's).
- `IvonaGui` uses `setOnUtteranceCompletedListener(com.google.tts.e)` (line 872): beta-installed → `ITtsCallbackBeta.Stub.utteranceCompleted(String)` → `e.onUtteranceCompleted`; otherwise wraps a platform `TextToSpeech.OnUtteranceCompletedListener`.

Supporting pieces:
- `ConfigurationManager` (an `Activity`, `R.layout.main`): if `/sdcard/espeak-data/` is complete → `startActivityForResult(new Intent(this, TextToSpeechSettings.class), 42)`; else downloads `espeak-data.zip` to `/sdcard/espeak-data/data.zip` and unzips it (16 KiB buffers). **`com.google.tts.TextToSpeechSettings` is referenced (`TextToSpeechSettings.class`) but is *not* a class_def in `classes.dex`** (dex header parse: absent) ⇒ that branch would throw `NoClassDefFoundError`; effectively dead. `TTS.dataFilesCheck()` calls `ConfigurationManager.a()` and, if false, launches `com.google.tts.ConfigurationManager` via `createPackageContext("com.google.tts", 3)`.
- `MakeBagel`: sample activity that reads extras `message`/`language`/`country`/`variant`, builds `langRegionString = "ISO3-ISO3"`, and speaks via `TTS` (USE_TTS path). Never declared in the manifest.
- `TTSEngine` enum (`PRERECORDED_ONLY`, `PRERECORDED_WITH_TTS`, `TTS_ONLY`, `ESPEAK`, `PICO`), `TTSParams` (`VOICE_MALE`, `VOICE_FEMALE`, `VOICE_ROBOT`), `TTSEarcon` (`SILENCE`, `TICK`, `TOCK`, `CANCEL`), `SoundResource{sourcePackageName, resId, filename}` — all unused by IVONA classes.
- `com.google.tts.R` is the app's own generated `R` (e.g. `R.string.preferred_voice = 0x7f06001d`, `R.string.preferred_voice_dialog_title = 0x7f06001e`, `R.layout.main`/`R.layout.welcome` = `0x7f030000/0x7f030001`), imported by `EngineSettings` and `IvonaGui`. Note: the decompiled `R.array.*` entries (`tts_lang_entries`, `tts_rate_entries`, `tts_engine_entries`, `tts_demo_strings`) have **no** corresponding array resources in `res/values/public.xml` (no `type="array"` rows at all) — stale/dead R fields from the vendored library.

---

## 11. `com.google.android.apps.analytics` (vendored, effectively dead)

Three classes: `AnalyticsReceiver`, `a` (referrer writer), `b` (`SQLiteOpenHelper` creating DB `"google_analytics.db"` v2 with tables `events`, `session`, `custom_variables`, `custom_var_cache`, `install_referrer(referrer TEXT PRIMARY KEY NOT NULL)`).
- `AnalyticsReceiver.onReceive` handles **`com.android.vending.INSTALL_REFERRER`**, parses the `referrer` extra: requires `utm_campaign`, `utm_medium`, `utm_source`, re-encodes into GA v1 form `utmcid=…|utmcsr=…|utmgclid=…|utmccn=…|utmcmd=…|utmctr=…|utmccct=…` (values URL-escaped, `+`/space → `%20`), stores it in `install_referrer`.
- **No endpoint, no UA/tracking id, no dispatch loop exists in this APK** — grep for `google-analytics|/collect|utmwv|User-Agent|UA-` finds nothing. No `GoogleAnalyticsTracker`/`AnalyticsService` class is present.
- The receiver is **not registered in `AndroidManifest.xml`**, and no IVONA class references the package ⇒ the whole `com.google.android.apps.analytics` payload is unused in this build (a library dropped in by the shared code base; it is also present in the voice APKs).
- Separately, `DownloadVoiceData` reads SharedPreferences `ivona_referrer`/`referrer`, but nothing in this APK writes it (`AnalyticsReceiver` would have been the natural writer). `[INFERENCE: written by the voice app or a removed receiver]`

---

## 12. Reimplementation checklist (Java layer)

1. Manifest with the 13 components of §1 (including the exact `tts_lang.*` categories and `@xml/tts_engine` → `settingsActivity`).
2. `Application` subclass exposing a singleton `IvonaPackagesInfo`.
3. `IVONATextToSpeechService`: static engine + `CountDownLatch` gate, activation-socket handshake before `create()`, `createInProgress`/`initLanguage` deferral, language callbacks delegating to `IvonaPackagesInfo.a(...)`, `onSynthesizeText` with headset contrast + `speak()` = `start(rate,2,1)` → `setProperty(rate/pitch)` → native `synthesizeText` (buffer = `getMaxBufferSize()`) → `audioAvailable` pump → `done()`, `onStop` → native `stop()`.
4. `IvonaPackagesInfo`: uid-shared package enumeration, native `getVoicesApiVersion`/`isoemn`, CSV cache format of §5.3, static 53-voice table, state enum.
5. `ConfigXMLDataSet`: native-only config, packages cfg consumed by `CheckVoiceData` in OEM mode.
6. Settings: per-locale `ListPreference` writing `files/.<lang>_<ctry>` = package name; `ivona_custom.emailSet`; `.android_version`.
7. `TTSServiceActivation` + `LocalServerSocket` protocol of §9.3/§9.4 + `IvonaBackendThread` POST of §8.1.
8. Entry activities for the four standard TTS actions plus `START_TTS_ENGINE`, `CONFIGURE_ENGINE`, `ACTION_CUSTOM_SETTINGS`, launcher.
9. Vendored `com.google.tts` client layer as-is (§10); do **not** implement `ITtsBeta`/`ITTS` services — none exists here.

### Explicit uncertainty markers
- `[INFERENCE]` exact semantics of `isoemn()` (presence of `/etc/ivona/ivona_config.xml`).
- `[INFERENCE]` which concrete file names live under the two now-confirmed data roots (`<sdcard>/ivona/…`, `<sdcard>/Android/obb/…` — confirmed via the `h(pkg, base)` calls in `getVoicesApiVersion`, `out/ghidra_dump/decompiled.c:10198-10290`) and how the `com.ivona.tts/files/` + `%s.%s`/`%s_%s` strings are joined (read as `files/.<iso3lang>_<iso3country>` preference files, §5.7). Java never touches OBB.
- `[INFERENCE]` element type of the `marks` `List` passed to `synthesizeText(String,byte[],List,int)` and to `audioAvailable(byte[],int,int,List)`; kinds are implied by native strings `TYPE_PHONEME/WORD/SENTENCE/SSML/VISEME`.
- `[UNCERTAIN]` `GetSampleText` final `setResult(-2, sampleText="")` after an unconditional tail block (§5.5).
- `[INFERENCE]` who initiates the encrypted activation-socket messages (no sender exists in the engine or voice APKs).
- Sample rate returned by `getSampleRate()` is native-determined; no Java constant.
